# Base de Conhecimento — PizzaApp
> Documento técnico completo: telas, funcionalidades, banco de dados, endpoints e integrações.
> Gerado em: 2026-04-13 | **Atualizado em: 2026-05-03** | Versao: 2.7.0

---

## Índice

1. [Visão Geral da Arquitetura](#1-visão-geral-da-arquitetura)
2. [Stack Tecnológica](#2-stack-tecnológica)
3. [Estrutura de Diretórios](#3-estrutura-de-diretórios)
4. [Front-end — Tela por Tela](#4-front-end--tela-por-tela)
   - 4.1 [App Cliente](#41-app-cliente)
   - 4.2 [Painel Administrativo](#42-painel-administrativo)
5. [Estado Global — AppContext](#5-estado-global--appcontext)
6. [Banco de Dados](#6-banco-de-dados)
   - 6.1 [Tabelas e Colunas](#61-tabelas-e-colunas)
   - 6.2 [Relacionamentos](#62-relacionamentos)
   - 6.3 [Seed de Dados Iniciais](#63-seed-de-dados-iniciais)
7. [Backend — Endpoints da API](#7-backend--endpoints-da-api)
8. [Camada de Serviços](#8-camada-de-serviços)
   - 8.1 [OrderService](#81-orderservice)
   - 8.2 [PaymentService](#82-paymentservice)
   - 8.3 [ShippingService](#83-shippingservice)
   - 8.4 [DeliveryService](#84-deliveryservice)
   - 8.5 [CouponService](#85-couponservice)
   - 8.6 [LoyaltyService](#86-loyaltyservice)
9. [Core — Infraestrutura de Domínio](#9-core--infraestrutura-de-domínio)
   - 9.1 [Máquina de Estados](#91-máquina-de-estados)
   - 9.2 [Bus de Eventos](#92-bus-de-eventos)
   - 9.3 [Exceções de Domínio](#93-exceções-de-domínio)
10. [Integrações Externas](#10-integrações-externas)
11. [Sistema de Multi-Sabor](#11-sistema-de-multi-sabor)
12. [Regras de Negócio Críticas](#12-regras-de-negócio-críticas)
13. [Fluxo Completo de um Pedido](#13-fluxo-completo-de-um-pedido)
14. [Atualizacao 2026-04-23 - Mercado Pago Payment Brick](#14-atualizacao-2026-04-23---mercado-pago-payment-brick)
15. [Atualizacao 2026-04-24 - Estado Atual Consolidado](#15-atualizacao-2026-04-24---estado-atual-consolidado)
16. [Atualizacao 2026-05-03 - Estado Atual do Admin SaaS](#16-atualizacao-2026-05-03---estado-atual-do-admin-saas)

---

## 1. Visão Geral da Arquitetura

```
┌─────────────────────────────────────────────────────────────────┐
│                        CLIENTE (Browser)                        │
│                                                                 │
│   React SPA (Vite + TypeScript + TailwindCSS)                   │
│   └── AppContext (estado global em memória)                     │
│       └── React Router 6 (client-side routing)                  │
└──────────────────────────┬──────────────────────────────────────┘
                           │ HTTP / REST (JSON)
                           │ CORS habilitado
┌──────────────────────────▼──────────────────────────────────────┐
│                    BACKEND (FastAPI / Python)                   │
│                                                                 │
│   Routes → Services → Core (StateMachine + EventBus) → ORM     │
│                                                                 │
│   Módulos: products, orders, payments, shipping, delivery,      │
│            coupons, loyalty, customers, promotions, admin       │
└──────────────────────────┬──────────────────────────────────────┘
                           │ SQLAlchemy
┌──────────────────────────▼──────────────────────────────────────┐
│                   PostgreSQL (banco de dados)                   │
│                                                                 │
│   21 tabelas | auto-criadas no startup | seed automático        │
└─────────────────────────────────────────────────────────────────┘
```

**Princípio central da camada de serviços:**
- Nenhuma rota ou integração ERP modifica status diretamente no banco
- Todo status passa pela `StateMachine` que valida a transição
- Eventos de domínio são publicados *após* o commit (ERP sync, push notifications)
- Loja online e ERP usam as mesmas classes de serviço

---

## 2. Stack Tecnológica

### Front-end
| Tecnologia | Versão | Uso |
|-----------|--------|-----|
| React | 18 | UI framework |
| TypeScript | 5 | Tipagem estática |
| Vite | 5 | Build tool / dev server |
| TailwindCSS | 3 | Estilização (JIT) |
| React Router | 6 | Roteamento SPA |
| Lucide React | — | Ícones |
| shadcn/ui | — | Componentes base (40+) |
| @tanstack/react-query | — | Cache de dados (pronto para uso) |

### Back-end
| Tecnologia | Versão | Uso |
|-----------|--------|-----|
| Python | 3.13 | Runtime |
| FastAPI | 0.115.5 | Web framework |
| SQLAlchemy | 2.0.36 | ORM |
| Pydantic | 2.10.3 | Validação de dados |
| pydantic-settings | 2.7.0 | Config via .env |
| psycopg2-binary | 2.9.10 | Driver PostgreSQL |
| Uvicorn | 0.32.1 | ASGI server |
| Alembic | 1.14.0 | Migrações de banco |
| mercadopago | 2.3.0 | SDK pagamento |

### Infraestrutura
| Componente | Tecnologia |
|-----------|-----------|
| Banco de dados | PostgreSQL 15+ |
| Servidor de API | Uvicorn (produção: Gunicorn + Uvicorn workers) |
| Servidor web | Nginx (reverse proxy) |
| Processo manager | Systemd ou PM2 |

---

## 3. Estrutura de Diretórios

```
builderpizzaapp-main/
│
├── client/                        ← Front-end React
│   ├── pages/
│   │   ├── Index.tsx              ← Home
│   │   ├── Product.tsx            ← Produto + multi-sabor
│   │   ├── Cart.tsx               ← Carrinho
│   │   ├── Checkout.tsx           ← Finalizar compra
│   │   ├── OrderTracking.tsx      ← Rastreio do pedido
│   │   ├── Pedidos.tsx            ← Histórico de pedidos
│   │   ├── Conta.tsx              ← Perfil do cliente
│   │   ├── Cupons.tsx             ← Meus cupons
│   │   ├── Fidelidade.tsx         ← Programa de fidelidade
│   │   ├── Localizacao.tsx        ← Localização da loja
│   │   └── admin/
│   │       ├── Dashboard.tsx      ← Painel principal
│   │       ├── Products.tsx       ← CRUD produtos + config multi-sabor
│   │       ├── Orders.tsx         ← Gestão de pedidos
│   │       ├── Promotions.tsx     ← Gestão de promoções
│   │       ├── AdminCupons.tsx    ← CRUD cupons
│   │       ├── AdminFidelidade.tsx← CRUD fidelidade
│   │       ├── Conteudo.tsx       ← Edição de conteúdo do site
│   │       └── AdminPagamentos.tsx← Config gateway de pagamento
│   ├── components/
│   │   ├── AdminSidebar.tsx       ← Sidebar compartilhada do admin
│   │   └── ui/                   ← shadcn/ui (40+ componentes)
│   ├── context/
│   │   └── AppContext.tsx         ← Estado global (React Context)
│   └── App.tsx                   ← Rotas da aplicação
│
├── backend/                       ← Back-end Python
│   ├── main.py                   ← Entry point FastAPI + lifespan
│   ├── config.py                 ← Settings via .env (extra="ignore")
│   ├── database.py               ← Engine SQLAlchemy + get_db
│   ├── models/                   ← Tabelas do banco
│   │   ├── product.py            ← products, multi_flavors_config
│   │   ├── order.py              ← orders, order_items, order_item_flavors
│   │   ├── customer.py           ← customers, addresses
│   │   ├── payment.py            ← payments
│   │   ├── payment_config.py     ← payment_gateway_config
│   │   ├── shipping.py           ← shipping_zones, shipping_zone_areas, shipping_rules
│   │   ├── coupon.py             ← coupons
│   │   ├── loyalty.py            ← loyalty_levels, loyalty_rewards, loyalty_rules, customer_loyalty, loyalty_transactions
│   │   ├── promotion.py          ← promotions
│   │   └── delivery.py           ← delivery_persons, deliveries
│   ├── schemas/                  ← Pydantic (request/response)
│   │   ├── order.py, payment.py, shipping.py, coupon.py
│   │   ├── loyalty.py, promotion.py, customer.py, product.py
│   │   ├── payment_config.py
│   │   └── delivery.py           ← DeliveryPersonOut, DeliveryOut, etc.
│   ├── routes/                   ← Endpoints FastAPI
│   │   ├── products.py, orders.py, payments.py, shipping.py
│   │   ├── coupons.py, loyalty.py, customers.py, promotions.py
│   │   ├── admin.py
│   │   └── delivery.py           ← /delivery/* (motoboys + rastreio)
│   ├── services/                 ← Lógica de negócio centralizada
│   │   ├── order_service.py      ← OrderService (classe)
│   │   ├── payment_service.py    ← PaymentService (classe) + gateways
│   │   ├── shipping_service.py   ← ShippingService (classe)
│   │   ├── delivery_service.py   ← DeliveryService (classe)
│   │   ├── coupon_service.py     ← CouponService
│   │   └── loyalty_service.py   ← award_points_for_order
│   ├── core/
│   │   ├── seed.py               ← Dados iniciais do banco
│   │   ├── exceptions.py         ← Hierarquia DomainError
│   │   ├── state_machine.py      ← StateMachine + ORDER/DELIVERY/PAYMENT transitions
│   │   └── events.py             ← EventBus + todos os eventos de domínio
│   ├── requirements.txt
│   ├── .env.example
│   └── start.sh
│
├── KNOWLEDGE_BASE.md             ← Este documento
├── INSTALL_MANUAL.md             ← Manual de instalação VPS
└── package.json                  ← Dependências Node/front-end
```

---

## 4. Front-end — Tela por Tela

### 4.1 App Cliente

#### `/` — Home (`Index.tsx`)
**Funcionalidades:**
- Status bar simulada (hora, sinal, bateria)
- Header com ícones Menu e Pesquisa
- **Banner de promoção ativa** — exibe `title`, `subtitle` e `icon` da primeira promoção com `active: true` do AppContext
- **Subtítulo e título da seção** — editáveis via Admin → Conteúdo (`siteContent.home.sectionSubtitle`, `siteContent.home.sectionTitle`)
- **Pills de categorias** — horizontais, scroll, editáveis via Admin → Conteúdo (`siteContent.home.categories`)
- **Carrossel de produtos** — mostra produto anterior (40% opacidade), produto central (destacado) e próximo. Navegação por botões ← →
- Ao clicar no produto central: animação de rotateY + redirect para `/product/:id`
- **Bottom Navigation fixo:** Home | Carrinho | Pedidos | Conta

**Dados consumidos:** `products`, `promotions`, `siteContent` do AppContext

---

#### `/product/:id` — Produto (`Product.tsx`)

1. **Seletor de Tamanho** — Pequena (×0.8) | Média (×1.0) | Grande (×1.2)
2. **Seletor de Divisão de Sabores** — Inteira | Meio a Meio | 3 Sabores (filtrado por `multiFlavorsConfig.maxFlavors`)
3. **Diagrama SVG da Pizza** — Division 1: círculo; Division 2: clipPath; Division 3: setores 120° trigonométricos
4. **Slots de sabor** — botão por divisão, abre lista de produtos, valida sem duplicatas
5. **Preço em tempo real** — aplica `pricingRule` (most_expensive / average / proportional)
6. **Add-ons / Extras** — lista com toggle
7. **Seletor de quantidade** (+/-)
8. **Botão Adicionar ao Carrinho** — valida slots preenchidos, cria `cartItemId` único, navega para `/cart`

---

#### `/cart` — Carrinho (`Cart.tsx`)
- Lista `CartItem` com ícones, nome multi-sabor, badge de divisão, controles de quantidade, preço
- Subtotal, taxa de entrega fixa (R$ 10,00), total
- Botão "Finalizar Pedido" → `/checkout`

---

#### `/checkout` — Checkout (`Checkout.tsx`)
- Formulário de entrega (Nome, Telefone, Rua, Cidade, Complemento)
- Resumo do pedido com suporte multi-sabor
- Ao confirmar: `createOrder()` → redireciona para `/order-tracking?orderId=...`

---

#### `/order-tracking` — Rastreio (`OrderTracking.tsx`)
- Número do pedido em destaque
- Barra de progresso: Preparing → On the way → Delivered
- `clearCart()` chamado ao montar (limpa carrinho após pedido criado)

---

#### `/pedidos` — Meus Pedidos (`Pedidos.tsx`)
- Lista pedidos em ordem reversa com badge de status, itens multi-sabor, total
- Botão "Ver detalhes" → `/order-tracking?orderId=...`

---

#### `/conta` — Minha Conta (`Conta.tsx`)
- Avatar, nome, e-mail, stats (total pedidos + total gasto)
- Dados editáveis com modo edição (draft state)
- Atalhos: Fidelidade, Cupons, Pedidos, Localização

---

#### `/cupons` — Meus Cupons (`Cupons.tsx`)
- Lista cupons com código, desconto, validade, distinção ativo/usado

---

#### `/fidelidade` — Fidelidade (`Fidelidade.tsx`)
- Níveis com colorPalette (orange, gray, yellow, blue, green, purple) — classes Tailwind literais
- Recompensas e regras de ganho do AppContext

---

#### `/localizacao` — Localização (`Localizacao.tsx`)
- Tela de mapa/localização da loja

---

### 4.2 Painel Administrativo

Todas as páginas compartilham `AdminSidebar`:
`Dashboard | Produtos | Promoções | Pedidos | Cupons | Fidelidade | Conteúdo | Pagamentos`

---

#### `/painel` — Dashboard
- Cards: Total Pedidos, Total Produtos, Promoções Ativas, Receita Total
- Tabela dos últimos 5 pedidos
- Atalhos rápidos

---

#### `/painel/products` — Produtos
**CRUD de Produtos:** nome, preço, descrição, ícone/emoji, avaliação (1–5)
**Config Multi-Sabor:**
- Máximo de sabores: 2 ou 3
- Regra de precificação com exemplos visuais
- Badge "✓ Configuração salva" por 2 segundos

---

#### `/painel/orders` — Pedidos
- Lista pedidos com controle de status: Preparando | A caminho | Entregue
- Status atual destacado em laranja

---

#### `/painel/promotions` — Promoções
- CRUD de banners da Home (título, subtítulo, ícone, ativo/inativo)

---

#### `/painel/cupons` — Cupons
- CRUD: código, tipo, desconto, validade, ícone
- Toggle Marcar como usado / Reativar

---

#### `/painel/fidelidade` — Fidelidade
- **Níveis:** CRUD com seletor de 6 cores
- **Recompensas:** CRUD ordenado por pontos
- **Regras de Ganho:** CRUD (por pedido / por R$1 / primeiro pedido)

---

#### `/painel/conteudo` — Conteúdo
- Editar subtítulo e título da Home
- Gerenciador de categorias (pills)

---

#### `/painel/pagamentos` — Pagamentos

**1. Processador de Pagamento**
Cards: 🧪 Mock | 💙 Mercado Pago | ⚡ Stripe | 🟡 PagSeguro

**2. Ambiente** — Toggle Sandbox ↔ Produção

**3. Métodos Aceitos** — Toggles: PIX | Cartão de Crédito | Cartão de Débito | Dinheiro

**4. Credenciais por Gateway**
- Mercado Pago: Public Key, Access Token (mascarado), Webhook Secret
- Stripe: Publishable Key, Secret Key, Webhook Secret
- PagSeguro: E-mail, Token
- Campos secretos com botão 👁 mostrar/ocultar

**5. Config PIX** — Tipo de chave, Chave PIX, Nome e Cidade do beneficiário

**6. URL do Webhook** — Campo com botão "Copiar"

**Comportamento:** `GET/PUT /admin/payment-gateway`

---

## 5. Estado Global — AppContext

**Arquivo:** `client/context/AppContext.tsx`

Os dados **resetam ao recarregar** (sem localStorage/backend ainda).

| Estado | Tipo | Descrição |
|--------|------|-----------|
| `products` | `Pizza[]` | Catálogo de produtos |
| `cart` | `CartItem[]` | Itens no carrinho |
| `promotions` | `Promotion[]` | Banners da Home |
| `orders` | `Order[]` | Pedidos realizados na sessão |
| `coupons` | `Coupon[]` | Cupons disponíveis |
| `fidelidadeLevels` | `FidelidadeLevel[]` | Níveis de fidelidade |
| `fidelidadeRewards` | `FidelidadeReward[]` | Recompensas disponíveis |
| `earnRules` | `EarnRule[]` | Regras para ganhar pontos |
| `siteContent` | `SiteContent` | Textos da Home |
| `multiFlavorsConfig` | `MultiFlavorsConfig` | Config divisão de sabores |

```typescript
interface CartItem {
  cartItemId: string;       // "cart-{timestamp}-{random4}"
  productId: string;
  quantity: number;
  selectedSize: string;     // "Pequena" | "Média" | "Grande"
  selectedAddOns: string[];
  productData: Pizza;
  flavorDivision: 1 | 2 | 3;
  flavors: PizzaFlavor[];
  finalPrice: number;       // calculado pela pricingRule
}
```

---

## 6. Banco de Dados

> **Nome do banco configurável:** O nome do banco de dados não é fixo — ele é definido no momento da instalação conforme o nome da loja/domínio.
> - Script de criação: `setup_database.sh --nome <nome_da_loja>`
> - Variável de conexão: `DATABASE_URL` em `backend/.env`
> - Exemplo: loja "brasell" → banco `brasell`, usuário `brasell_user`
> - O `setup_database.sql` aceita o nome via `-v DBNAME=<nome>` ou pela edição manual das variáveis `\set` no topo do arquivo.

### 6.1 Tabelas e Colunas

#### `products`
| Coluna | Tipo | Constraints | Descrição |
|--------|------|-------------|-----------|
| `id` | VARCHAR | PK | "prod-{hex8}" |
| `name` | VARCHAR(200) | NOT NULL | — |
| `description` | TEXT | NOT NULL | — |
| `price` | FLOAT | NOT NULL | Preço base em R$ |
| `icon` | VARCHAR(100) | default "🍕" | — |
| `rating` | FLOAT | default 4.5 | 1.0–5.0 |
| `active` | BOOLEAN | default TRUE | — |
| `created_at` | TIMESTAMPTZ | auto | — |
| `updated_at` | TIMESTAMPTZ | auto | — |

#### `multi_flavors_config`
| Coluna | Tipo | Constraints | Descrição |
|--------|------|-------------|-----------|
| `id` | VARCHAR | PK | Fixo: "default" |
| `max_flavors` | INTEGER | default 2 | 2 ou 3 |
| `pricing_rule` | ENUM | default "most_expensive" | most_expensive / average / proportional |
| `updated_at` | TIMESTAMPTZ | auto | — |

#### `customers`
| Coluna | Tipo | Constraints | Descrição |
|--------|------|-------------|-----------|
| `id` | VARCHAR | PK | UUID |
| `name` | VARCHAR(200) | NOT NULL | — |
| `email` | VARCHAR(200) | UNIQUE, NOT NULL | — |
| `phone` | VARCHAR(30) | — | — |
| `created_at` | TIMESTAMPTZ | auto | — |
| `updated_at` | TIMESTAMPTZ | auto | — |

#### `addresses`
| Coluna | Tipo | Constraints | Descrição |
|--------|------|-------------|-----------|
| `id` | VARCHAR | PK | UUID |
| `customer_id` | VARCHAR | FK → customers.id | — |
| `street` | VARCHAR(300) | NOT NULL | — |
| `number` | VARCHAR(20) | — | — |
| `complement` | VARCHAR(100) | — | — |
| `neighborhood` | VARCHAR(100) | — | — |
| `city` | VARCHAR(100) | NOT NULL | — |
| `state` | VARCHAR(50) | — | — |
| `zip_code` | VARCHAR(20) | — | — |
| `is_default` | BOOLEAN | default FALSE | — |
| `created_at` | TIMESTAMPTZ | auto | — |

#### `orders`
| Coluna | Tipo | Constraints | Descrição |
|--------|------|-------------|-----------|
| `id` | VARCHAR | PK | "order-{hex8}" |
| `customer_id` | VARCHAR | FK → customers.id, nullable | NULL = guest |
| `address_id` | VARCHAR | FK → addresses.id, nullable | — |
| `delivery_name` | VARCHAR(200) | — | Entrega inline (guest) |
| `delivery_phone` | VARCHAR(30) | — | — |
| `delivery_street` | VARCHAR(300) | — | — |
| `delivery_city` | VARCHAR(100) | — | — |
| `delivery_complement` | VARCHAR(100) | — | — |
| `status` | ENUM | default "pending" | pending / **waiting_payment** / paid / preparing / ready_for_pickup / on_the_way / delivered / cancelled / refunded |
| `coupon_id` | VARCHAR | FK → coupons.id, nullable | — |
| `subtotal` | FLOAT | NOT NULL | — |
| `shipping_fee` | FLOAT | default 0.0 | — |
| `discount` | FLOAT | default 0.0 | Desconto do cupom |
| `total` | FLOAT | NOT NULL | subtotal + frete - desconto |
| `estimated_time` | INTEGER | default 40 | Minutos |
| `loyalty_points_earned` | INTEGER | default 0 | — |
| `notes` | TEXT | — | — |
| `created_at` | TIMESTAMPTZ | auto | — |
| `updated_at` | TIMESTAMPTZ | auto | — |

#### `order_items`
| Coluna | Tipo | Constraints | Descrição |
|--------|------|-------------|-----------|
| `id` | VARCHAR | PK | UUID |
| `order_id` | VARCHAR | FK → orders.id | — |
| `product_id` | VARCHAR | FK → products.id | Produto principal |
| `quantity` | INTEGER | default 1 | — |
| `selected_size` | VARCHAR(50) | — | "Pequena" / "Média" / "Grande" |
| `flavor_division` | INTEGER | default 1 | 1 / 2 / 3 |
| `unit_price` | FLOAT | NOT NULL | Preço calculado por unidade |
| `total_price` | FLOAT | NOT NULL | unit_price × quantity |

#### `order_item_flavors`
| Coluna | Tipo | Constraints | Descrição |
|--------|------|-------------|-----------|
| `id` | VARCHAR | PK | UUID |
| `order_item_id` | VARCHAR | FK → order_items.id | — |
| `product_id` | VARCHAR | FK → products.id | Produto deste sabor |
| `flavor_name` | VARCHAR(200) | NOT NULL | — |
| `flavor_price` | FLOAT | NOT NULL | Preço individual do sabor |
| `position` | INTEGER | default 0 | Slot 0, 1 ou 2 |

#### `payments`
| Coluna | Tipo | Constraints | Descrição |
|--------|------|-------------|-----------|
| `id` | VARCHAR | PK | UUID |
| `order_id` | VARCHAR | FK → orders.id, UNIQUE | 1 pagamento por pedido |
| `method` | ENUM | NOT NULL | pix / credit_card / debit_card / cash |
| `status` | ENUM | default "pending" | pending / paid / failed / refunded |
| `amount` | FLOAT | NOT NULL | Valor em R$ |
| `transaction_id` | VARCHAR(300) | nullable | ID no gateway |
| `gateway` | VARCHAR(50) | default "mock" | — |
| `qr_code` | TEXT | nullable | Base64 do QR PIX |
| `qr_code_text` | TEXT | nullable | Copia e cola PIX |
| `payment_url` | VARCHAR(500) | nullable | Link Checkout Pro |
| `client_secret` | VARCHAR(300) | nullable | Stripe client secret |
| `webhook_data` | TEXT | nullable | Payload bruto do webhook |
| `created_at` | TIMESTAMPTZ | auto | — |
| `paid_at` | TIMESTAMPTZ | nullable | Quando foi confirmado |

#### `payment_gateway_config`
| Coluna | Tipo | Constraints | Descrição |
|--------|------|-------------|-----------|
| `id` | VARCHAR | PK | Fixo: "default" |
| `gateway` | VARCHAR(50) | default "mock" | mock / mercadopago / stripe / pagseguro |
| `mp_public_key` | VARCHAR(300) | nullable | MP Public Key |
| `mp_access_token` | VARCHAR(300) | nullable | MP Access Token |
| `mp_webhook_secret` | VARCHAR(300) | nullable | — |
| `stripe_publishable_key` | VARCHAR(300) | nullable | — |
| `stripe_secret_key` | VARCHAR(300) | nullable | — |
| `stripe_webhook_secret` | VARCHAR(300) | nullable | — |
| `pagseguro_email` | VARCHAR(200) | nullable | — |
| `pagseguro_token` | VARCHAR(300) | nullable | — |
| `pix_key` | VARCHAR(200) | nullable | Chave PIX da loja |
| `pix_key_type` | VARCHAR(30) | nullable | cpf / cnpj / email / phone / random |
| `pix_beneficiary_name` | VARCHAR(200) | nullable | — |
| `pix_beneficiary_city` | VARCHAR(100) | nullable | — |
| `accept_pix` | BOOLEAN | default TRUE | — |
| `accept_credit_card` | BOOLEAN | default TRUE | — |
| `accept_debit_card` | BOOLEAN | default FALSE | — |
| `accept_cash` | BOOLEAN | default TRUE | — |
| `sandbox` | BOOLEAN | default TRUE | Ambiente de testes |
| `updated_at` | TIMESTAMPTZ | auto | — |

#### `shipping_zones`
| Coluna | Tipo | Constraints | Descrição |
|--------|------|-------------|-----------|
| `id` | VARCHAR | PK | UUID |
| `name` | VARCHAR(100) | NOT NULL | Ex: "Centro", "Zona Sul" |
| `active` | BOOLEAN | default TRUE | — |
| `created_at` | TIMESTAMPTZ | auto | — |

#### `shipping_zone_areas`
| Coluna | Tipo | Constraints | Descrição |
|--------|------|-------------|-----------|
| `id` | VARCHAR | PK | UUID |
| `zone_id` | VARCHAR | FK → shipping_zones.id | — |
| `area_type` | ENUM | NOT NULL | city / neighborhood / zip_prefix |
| `value` | VARCHAR(100) | NOT NULL | Ex: "São Paulo", "Centro", "01310" |

#### `shipping_rules`
| Coluna | Tipo | Constraints | Descrição |
|--------|------|-------------|-----------|
| `id` | VARCHAR | PK | UUID |
| `zone_id` | VARCHAR | FK → shipping_zones.id, nullable | NULL = global |
| `name` | VARCHAR(100) | NOT NULL | — |
| `rule_type` | ENUM | NOT NULL | fixed / per_distance / free_above / promotional |
| `priority` | INTEGER | default 0 | Maior = avaliado primeiro |
| `active` | BOOLEAN | default TRUE | — |
| `base_price` | FLOAT | default 0.0 | Preço base em R$ |
| `per_km_price` | FLOAT | default 0.0 | Para tipo per_distance |
| `store_lat` | FLOAT | nullable | Lat da loja (per_distance) |
| `store_lng` | FLOAT | nullable | Lng da loja (per_distance) |
| `free_above_amount` | FLOAT | nullable | Mínimo para frete grátis |
| `valid_from` | TIMESTAMPTZ | nullable | Início de validade (promotional) |
| `valid_until` | TIMESTAMPTZ | nullable | Fim de validade (promotional) |
| `created_at` | TIMESTAMPTZ | auto | — |

#### `coupons`
| Coluna | Tipo | Constraints | Descrição |
|--------|------|-------------|-----------|
| `id` | VARCHAR | PK | UUID |
| `code` | VARCHAR(50) | UNIQUE, NOT NULL | Sempre em maiúsculas |
| `description` | VARCHAR(300) | — | — |
| `icon` | VARCHAR(50) | default "🎟️" | — |
| `coupon_type` | ENUM | NOT NULL | percentage / fixed |
| `discount_value` | FLOAT | NOT NULL | % ou R$ |
| `min_order_value` | FLOAT | default 0.0 | Pedido mínimo |
| `max_uses` | INTEGER | nullable | NULL = ilimitado |
| `used_count` | INTEGER | default 0 | — |
| `expiry_date` | TIMESTAMPTZ | nullable | — |
| `active` | BOOLEAN | default TRUE | — |
| `created_at` | TIMESTAMPTZ | auto | — |

#### `loyalty_levels`
| Coluna | Tipo | Constraints | Descrição |
|--------|------|-------------|-----------|
| `id` | VARCHAR | PK | UUID |
| `name` | VARCHAR(100) | NOT NULL | Ex: "Bronze" |
| `min_points` | INTEGER | NOT NULL | — |
| `max_points` | INTEGER | nullable | NULL = sem teto |
| `icon` | VARCHAR(50) | default "🏆" | — |
| `color` | VARCHAR(30) | default "orange" | Chave do colorPalette |
| `created_at` | TIMESTAMPTZ | auto | — |

#### `loyalty_rewards`
| Coluna | Tipo | Constraints | Descrição |
|--------|------|-------------|-----------|
| `id` | VARCHAR | PK | UUID |
| `label` | VARCHAR(200) | NOT NULL | Ex: "Pizza Grátis" |
| `points_required` | INTEGER | NOT NULL | — |
| `icon` | VARCHAR(50) | default "🎁" | — |
| `active` | BOOLEAN | default TRUE | — |
| `created_at` | TIMESTAMPTZ | auto | — |

#### `loyalty_rules`
| Coluna | Tipo | Constraints | Descrição |
|--------|------|-------------|-----------|
| `id` | VARCHAR | PK | UUID |
| `label` | VARCHAR(200) | NOT NULL | — |
| `icon` | VARCHAR(50) | default "⭐" | — |
| `points` | INTEGER | NOT NULL | — |
| `rule_type` | VARCHAR(50) | default "per_order" | per_order / per_real / first_order |
| `active` | BOOLEAN | default TRUE | — |
| `created_at` | TIMESTAMPTZ | auto | — |

#### `customer_loyalty`
| Coluna | Tipo | Constraints | Descrição |
|--------|------|-------------|-----------|
| `id` | VARCHAR | PK | UUID |
| `customer_id` | VARCHAR | FK → customers.id, UNIQUE | 1 conta por cliente |
| `total_points` | INTEGER | default 0 | Saldo atual |
| `level_id` | VARCHAR | FK → loyalty_levels.id, nullable | Nível atual |
| `created_at` | TIMESTAMPTZ | auto | — |

#### `loyalty_transactions`
| Coluna | Tipo | Constraints | Descrição |
|--------|------|-------------|-----------|
| `id` | VARCHAR | PK | UUID |
| `customer_loyalty_id` | VARCHAR | FK → customer_loyalty.id | — |
| `order_id` | VARCHAR | FK → orders.id, nullable | — |
| `points` | INTEGER | NOT NULL | Positivo (ganho) ou negativo (resgate) |
| `transaction_type` | ENUM | NOT NULL | earned / redeemed |
| `description` | VARCHAR(300) | — | — |
| `created_at` | TIMESTAMPTZ | auto | — |

#### `promotions`
| Coluna | Tipo | Constraints | Descrição |
|--------|------|-------------|-----------|
| `id` | VARCHAR | PK | UUID |
| `title` | VARCHAR(200) | NOT NULL | — |
| `subtitle` | VARCHAR(300) | — | — |
| `description` | TEXT | — | — |
| `icon` | VARCHAR(100) | default "🍕" | — |
| `active` | BOOLEAN | default FALSE | — |
| `valid_from` | TIMESTAMPTZ | nullable | — |
| `valid_until` | TIMESTAMPTZ | nullable | — |
| `created_at` | TIMESTAMPTZ | auto | — |
| `updated_at` | TIMESTAMPTZ | auto | — |

#### `delivery_persons` *(novo)*
| Coluna | Tipo | Constraints | Descrição |
|--------|------|-------------|-----------|
| `id` | VARCHAR | PK | UUID |
| `name` | VARCHAR(200) | NOT NULL | — |
| `phone` | VARCHAR(30) | NOT NULL | — |
| `vehicle_type` | ENUM | default "motorcycle" | motorcycle / bicycle / car / walking |
| `status` | ENUM | default "offline" | available / busy / offline |
| `active` | BOOLEAN | default TRUE | — |
| `location_lat` | FLOAT | nullable | GPS latitude (app mobile) |
| `location_lng` | FLOAT | nullable | GPS longitude (app mobile) |
| `location_updated_at` | TIMESTAMPTZ | nullable | — |
| `total_deliveries` | INTEGER | default 0 | — |
| `average_rating` | FLOAT | default 5.0 | Média ponderada 1–5 |
| `created_at` | TIMESTAMPTZ | auto | — |
| `updated_at` | TIMESTAMPTZ | auto | — |

#### `deliveries` *(novo)*
| Coluna | Tipo | Constraints | Descrição |
|--------|------|-------------|-----------|
| `id` | VARCHAR | PK | UUID |
| `order_id` | VARCHAR | FK → orders.id, UNIQUE | 1 entrega por pedido |
| `delivery_person_id` | VARCHAR | FK → delivery_persons.id, nullable | — |
| `status` | ENUM | default "pending_assignment" | pending_assignment / assigned / picked_up / on_the_way / delivered / completed / failed / cancelled |
| `assigned_at` | TIMESTAMPTZ | nullable | — |
| `picked_up_at` | TIMESTAMPTZ | nullable | — |
| `delivered_at` | TIMESTAMPTZ | nullable | — |
| `estimated_minutes` | INTEGER | default 40 | — |
| `delivery_photo_url` | VARCHAR(500) | nullable | Prova de entrega |
| `recipient_name` | VARCHAR(200) | nullable | — |
| `notes` | TEXT | nullable | — |
| `rating` | INTEGER | nullable | 1–5 (avaliação do cliente) |
| `rating_comment` | TEXT | nullable | — |
| `created_at` | TIMESTAMPTZ | auto | — |
| `updated_at` | TIMESTAMPTZ | auto | — |

---

### 6.2 Relacionamentos

```
customers ──┬── 1:N ──→ addresses
            ├── 1:N ──→ orders
            └── 1:1 ──→ customer_loyalty ──→ 1:N ──→ loyalty_transactions

orders ──┬── 1:N ──→ order_items ──→ 1:N ──→ order_item_flavors
         ├── 1:1 ──→ payments
         ├── 1:1 ──→ deliveries ──→ N:1 ──→ delivery_persons
         └── N:1 ──→ coupons

order_item_flavors ──→ N:1 ──→ products

shipping_zones ──→ 1:N ──→ shipping_zone_areas
shipping_zones ──→ 1:N ──→ shipping_rules

customer_loyalty ──→ N:1 ──→ loyalty_levels

delivery_persons ──→ 1:N ──→ deliveries
```

### 6.3 Seed de Dados Iniciais

Executado automaticamente na primeira inicialização (`core/seed.py`):

| Entidade | Quantidade | Exemplos |
|----------|-----------|---------|
| Produtos | 8 | Calabresa R$35, Camarão R$65, 4 Queijos R$48... |
| Multi-flavor config | 1 | max_flavors=2, pricing_rule=most_expensive |
| Promoções | 1 | "20% off em qualquer pizza" |
| Níveis de fidelidade | 4 | Bronze (0pts), Prata (501pts), Ouro (1501pts), Diamante (3001pts) |
| Recompensas | 4 | Pizza Grátis (500pts), Entrega Grátis (200pts)... |
| Regras de ganho | 3 | Primeiro Pedido (+50pts), A cada R$1 (+1pt), Entrega (+10pts) |
| Cupons | 2 | BEMVINDO10 (10% off), FRETE0 (frete grátis) |
| Regras de frete | 2 | Taxa padrão R$8, Frete grátis acima R$100 |

---

## 7. Backend — Endpoints da API

**Base URL:** `http://localhost:8000`
**Documentação interativa:** `http://localhost:8000/docs` (Swagger UI)

### Produtos
| Método | Rota | Descrição |
|--------|------|-----------|
| `GET` | `/products` | Lista produtos (`?active_only=true`) |
| `GET` | `/products/{id}` | Detalhe do produto |
| `POST` | `/products` | Criar produto |
| `PUT` | `/products/{id}` | Atualizar produto |
| `DELETE` | `/products/{id}` | Excluir produto |
| `GET` | `/products/config/multi-flavors` | Obter config multi-sabor |
| `PATCH` | `/products/config/multi-flavors` | Atualizar config multi-sabor |

### Pedidos
| Método | Rota | Descrição |
|--------|------|-----------|
| `POST` | `/orders/checkout` | **Criar pedido** (valida preços server-side via OrderService) |
| `GET` | `/orders` | Listar pedidos (`?status=`, `?customer_id=`, `?limit=`) |
| `GET` | `/orders/{id}` | Detalhe do pedido |
| `PATCH` | `/orders/{id}/status` | Atualizar status (via state machine) |
| `POST` | `/orders/{id}/cancel` | Cancelar pedido |

### Pagamentos
| Método | Rota | Descrição |
|--------|------|-----------|
| `POST` | `/payments/create` | Criar pagamento (gera PIX ou link) |
| `GET` | `/payments/{order_id}` | Obter pagamento por pedido |
| `POST` | `/payments/cash/{order_id}` | **ERP/caixa:** confirmar pagamento em dinheiro |
| `POST` | `/payments/webhook` | Receber confirmação do gateway |

### Frete
| Método | Rota | Descrição |
|--------|------|-----------|
| `POST` | `/shipping/calculate` | Calcular frete |
| `GET` | `/shipping/zones` | Listar zonas |
| `POST` | `/shipping/zones` | Criar zona |
| `DELETE` | `/shipping/zones/{id}` | Excluir zona |
| `GET` | `/shipping/rules` | Listar regras |
| `POST` | `/shipping/rules` | Criar regra |
| `DELETE` | `/shipping/rules/{id}` | Excluir regra |

### Entrega *(novo)*
| Método | Rota | Descrição |
|--------|------|-----------|
| `POST` | `/delivery/persons` | Cadastrar motoboy |
| `GET` | `/delivery/persons` | Listar motoboys (`?available_only=true`) |
| `GET` | `/delivery/persons/available` | Somente disponíveis |
| `GET` | `/delivery/persons/{id}` | Detalhe do motoboy |
| `PATCH` | `/delivery/persons/{id}/status` | Mudar status: available / offline |
| `PATCH` | `/delivery/persons/{id}/location` | Atualizar GPS (app mobile) |
| `DELETE` | `/delivery/persons/{id}` | Desativar motoboy (soft delete) |
| `POST` | `/delivery/assign` | Atribuir motoboy a um pedido |
| `GET` | `/delivery/active` | Entregas em andamento |
| `GET` | `/delivery/order/{order_id}` | Entrega de um pedido específico |
| `GET` | `/delivery/{id}` | Detalhe da entrega |
| `PATCH` | `/delivery/{id}/status` | Avançar status da entrega |
| `POST` | `/delivery/{id}/complete` | Finalizar com prova de entrega |
| `POST` | `/delivery/{id}/rate` | Cliente avalia a entrega (1–5) |

### Cupons
| Método | Rota | Descrição |
|--------|------|-----------|
| `GET` | `/coupons` | Listar cupons |
| `POST` | `/coupons` | Criar cupom |
| `PUT` | `/coupons/{id}` | Atualizar |
| `DELETE` | `/coupons/{id}` | Excluir |
| `POST` | `/coupons/apply` | Validar e calcular desconto |

### Fidelidade
| Método | Rota | Descrição |
|--------|------|-----------|
| `GET` | `/loyalty/levels` | Listar níveis |
| `POST` | `/loyalty/levels` | Criar nível |
| `PUT` | `/loyalty/levels/{id}` | Atualizar |
| `DELETE` | `/loyalty/levels/{id}` | Excluir |
| `GET` | `/loyalty/rewards` | Listar recompensas |
| `POST` | `/loyalty/rewards` | Criar |
| `DELETE` | `/loyalty/rewards/{id}` | Excluir |
| `GET` | `/loyalty/rules` | Listar regras |
| `POST` | `/loyalty/rules` | Criar regra |
| `DELETE` | `/loyalty/rules/{id}` | Excluir |
| `GET` | `/loyalty/account/{customer_id}` | Conta de fidelidade |
| `POST` | `/loyalty/redeem` | Resgatar recompensa |

### Clientes
| Método | Rota | Descrição |
|--------|------|-----------|
| `GET` | `/customers` | Listar clientes |
| `GET` | `/customers/{id}` | Detalhe |
| `POST` | `/customers` | Criar cliente |
| `PUT` | `/customers/{id}` | Atualizar |
| `GET` | `/customers/{id}/addresses` | Endereços |
| `POST` | `/customers/{id}/addresses` | Adicionar endereço |
| `DELETE` | `/customers/{id}/addresses/{addr_id}` | Remover endereço |

### Promoções
| Método | Rota | Descrição |
|--------|------|-----------|
| `GET` | `/promotions` | Listar (`?active_only=true`) |
| `POST` | `/promotions` | Criar |
| `PUT` | `/promotions/{id}` | Atualizar |
| `DELETE` | `/promotions/{id}` | Excluir |

### Admin
| Método | Rota | Descrição |
|--------|------|-----------|
| `GET` | `/admin/dashboard` | Stats: pedidos, receita, produtos, clientes |
| `GET` | `/admin/payment-gateway` | Config do gateway (chaves mascaradas) |
| `PUT` | `/admin/payment-gateway` | Atualizar configuração |

### Sistema
| Método | Rota | Descrição |
|--------|------|-----------|
| `GET` | `/health` | Health check |
| `GET` | `/docs` | Swagger UI |

---

## 8. Camada de Serviços

**Regra fundamental:** nenhuma rota ou integração externa pode mudar status diretamente no banco. Todo status passa pelo serviço correspondente, que aciona a `StateMachine` antes do commit.

Todos os serviços seguem o mesmo padrão:
```python
svc = OrderService(db)   # instanciado por request com a sessão SQLAlchemy
result = svc.create_from_checkout(payload)
```

### 8.1 OrderService

**Arquivo:** `backend/services/order_service.py`

| Método | Descrição |
|--------|-----------|
| `create_from_checkout(payload)` | Valida carrinho, recomputa preços, aplica frete+cupom, persiste Order+Items+Flavors, publica `OrderCreated` |
| `change_status(order_id, new_status, *, changed_by)` | **Único caminho para mudar status** — chama `order_sm.transition()`, publica `OrderStatusChanged`, concede pontos ao chegar em "delivered" |
| `cancel(order_id, *, reason, changed_by)` | Atalho para `change_status("cancelled")` + publica `OrderCancelled` |
| `get(order_id)` | Retorna Order com items e flavors carregados |
| `list(*, status, customer_id, limit)` | Listagem com filtros |
| `recalculate_total(order_id)` | Re-soma preços dos itens (para ajustes admin, apenas status "pending") |

**Algoritmo do checkout:**
1. Carrega `MultiFlavorsConfig`
2. Valida cada item: `len(flavors) == flavor_division`, `flavor_division <= max_flavors`, preço ±R$0,01
3. Recomputa preço server-side pela `pricing_rule`
4. Chama `ShippingService.calculate()` com cidade e subtotal
5. Aplica cupom via `CouponService.apply()` (se houver)
6. Calcula total = subtotal + frete - desconto
7. Persiste Order + OrderItems + OrderItemFlavors
8. Marca cupom como usado
9. Publica `OrderCreated` **após** o commit

---

### 8.2 PaymentService

**Arquivo:** `backend/services/payment_service.py`

| Método | Descrição |
|--------|-----------|
| `create(payload)` | Valida pedido em `pending`, sem pagamento duplicado, amount correto → chama gateway → avança pedido para `waiting_payment` → persiste, publica `PaymentCreated` |
| `confirm(payment, *, transaction_id)` | `payment_sm`: pending→paid; `order_sm`: waiting_payment→paid; publica `PaymentConfirmed` |
| `fail(payment, *, reason)` | `payment_sm`: pending→failed; pedido volta a ser tratável; publica `PaymentFailed` |
| `process_webhook(payload, raw_body, signature)` | Verifica assinatura HMAC, re-consulta status no gateway (não confia no payload), chama `confirm()` ou `fail()` |
| `confirm_cash(order_id)` | ERP/caixa: cria Payment (cash) se não existir, avança `pending→waiting_payment→paid` em uma transação |
| `get_by_order(order_id)` | Retorna PaymentOut |

**Idempotência:**
- `PaymentAlreadyExists` (409) se `order.payment` já existe
- `PaymentOrderNotEligible` (400) se pedido não está em `pending` ao criar pagamento

**Gateways disponíveis:**

| Gateway | Status | Funcionalidades |
|---------|--------|----------------|
| `MockGateway` | Ativo (dev) | PIX com QR fake, sempre retorna "paid" |
| `MercadoPagoGateway` | Ativo (SDK real) | PIX real (QR code base64), Checkout Pro, HMAC + re-fetch |
| `StripeGateway` | Estrutura pronta | Descomente + `pip install stripe` |
| `PagSeguroGateway` | Estrutura pronta | Implementar REST |

**Interface de gateway:**
```python
class GatewayInterface(ABC):
    def create_payment(self, payment, config) -> dict: ...
    def verify_webhook(self, payload, signature, config) -> bool: ...
    def fetch_status(self, transaction_id, config) -> str: ...  # "paid"|"pending"|"failed"
```

---

### 8.3 ShippingService

**Arquivo:** `backend/services/shipping_service.py`

| Método | Descrição |
|--------|-----------|
| `calculate(payload, *, order_id)` | Avalia regras por prioridade, retorna `ShippingCalculateOut`, publica `ShippingCalculated` |
| `list_zones()` | Lista zonas com áreas |
| `create_zone(payload)` | Cria zona + áreas |
| `delete_zone(zone_id)` | Remove zona |
| `list_rules()` | Lista regras por prioridade DESC |
| `create_rule(payload)` | Valida zona existe, cria regra |
| `delete_rule(rule_id)` | Remove regra |

**Algoritmo de cálculo:**
1. Carrega todas as regras ativas, ordena por `priority DESC`
2. Separa regras promocionais (dentro da janela de datas)
3. Avalia: promocionais primeiro, depois demais
4. Para cada regra: verifica zona (city / neighborhood / zip_prefix), verifica `free_above_amount`
5. Primeira regra aprovada → calcula preço e retorna
6. Fallback: taxa fixa R$5,00

**Tipos de regra:**
- `fixed`: retorna `base_price`
- `free_above`: R$0 se subtotal ≥ `free_above_amount`, senão `base_price`
- `per_distance`: retorna `base_price` (estrutura para geocode futuro)
- `promotional`: retorna `base_price` com alta prioridade por data

---

### 8.4 DeliveryService

**Arquivo:** `backend/services/delivery_service.py`

| Método | Descrição |
|--------|-----------|
| `assign(order_id, delivery_person_id, *, estimated_minutes)` | Atribui motoboy a pedido em `preparing` **ou** `ready_for_pickup`, avança pedido para `on_the_way`, marca motoboy como "busy", publica `DeliveryAssigned` |
| `update_status(delivery_id, new_status)` | Avança delivery_sm, atualiza timestamps, em "delivered" avança pedido e concede pontos |
| `complete(delivery_id, *, recipient_name, photo_url, notes)` | Finaliza entrega, registra prova, libera motoboy, publica `DeliveryCompleted` |
| `rate(delivery_id, rating, comment)` | Registra avaliação 1–5, atualiza média ponderada do motoboy |
| `update_location(delivery_person_id, lat, lng)` | Atualiza GPS do motoboy (app mobile) |
| `list_active()` | Entregas em: assigned / picked_up / on_the_way |
| `get_by_order(order_id)` | Entrega de um pedido |
| `list_persons(*, available_only)` | Lista motoboys ativos |
| `create_person(name, phone, vehicle_type)` | Cadastra motoboy |
| `set_person_status(person_id, status)` | "available" ou "offline" (não "busy" — esse é automático) |
| `deactivate_person(person_id)` | Soft delete |

**Pré-requisitos do `assign()`:**
- Pedido em status `preparing` **ou** `ready_for_pickup` (pagamento já confirmado — a state machine garante que não há como chegar nesses status sem passar por `paid`)
- Motoboy ativo e com status `available`
- Sem entrega já atribuída para o pedido (ou a anterior em "failed"/"cancelled")

---

### 8.5 CouponService

**Arquivo:** `backend/services/coupon_service.py`

`apply(payload)`: valida existência, ativa, validade, esgotamento, `min_order_value`. Calcula:
- `percentage`: `subtotal × discount_value / 100`
- `fixed`: `min(discount_value, subtotal)`

`mark_used(coupon_id)`: incrementa `used_count`.

---

### 8.6 LoyaltyService

**Arquivo:** `backend/services/loyalty_service.py`

`award_points_for_order(customer_id, order_id, order_total, db)`:
- Pontos = `int(order_total × POINTS_PER_REAL) + DELIVERY_POINTS`
- Cria `LoyaltyTransaction` (earned)
- Atualiza `CustomerLoyalty.total_points`
- Chama `_update_level()`: percorre níveis por `min_points DESC`, atribui o primeiro que se qualifica

---

## 9. Core — Infraestrutura de Domínio

### 9.1 Máquina de Estados

**Arquivo:** `backend/core/state_machine.py`

Três instâncias singleton: `order_sm`, `delivery_sm`, `payment_sm`.

**Transições de Pedido:**
```
pending          → waiting_payment, cancelled
waiting_payment  → paid, cancelled
paid             → preparing, cancelled, refunded
preparing        → ready_for_pickup, on_the_way, cancelled
ready_for_pickup → on_the_way
on_the_way       → delivered
delivered        → (terminal)
cancelled        → (terminal)
refunded         → (terminal)
```

**Happy path obrigatório:**
`pending → waiting_payment → paid → preparing → on_the_way → delivered`

**Regras críticas impostas pela state machine:**
- Não pode ir para `preparing` sem pagamento confirmado (`paid`)
- Não pode ir para `delivered` sem passar por `on_the_way`
- `ready_for_pickup` é intermediário opcional entre `preparing` e `on_the_way`

**Transições de Entrega:**
```
pending_assignment → assigned, cancelled
assigned → picked_up, cancelled
picked_up → on_the_way
on_the_way → delivered, failed
delivered → completed
completed → (terminal)
failed → pending_assignment  (pode ser reatribuída)
cancelled → (terminal)
```

**Transições de Pagamento:**
```
pending → paid, failed
paid → refunded
failed → pending  (pode ser retentada)
refunded → (terminal)
```

**API da StateMachine:**
```python
order_sm.transition(entity_id, from_status, to_status)   # levanta InvalidStatusTransition
order_sm.can_transition(from_status, to_status) -> bool
order_sm.allowed_transitions(current_status) -> list[str]
order_sm.is_terminal(status) -> bool
order_sm.on_enter(status, hook)   # registra side-effect
```

---

### 9.2 Bus de Eventos

**Arquivo:** `backend/core/events.py`

Singleton `bus = EventBus()`. Publicação acontece **após** o commit do banco.

**Eventos publicados:**

| Evento | Publicado por | Handlers registrados |
|--------|--------------|---------------------|
| `OrderCreated` | OrderService.create_from_checkout | erp_order_created, push_notification |
| `OrderStatusChanged` | OrderService.change_status | erp_order_status, push_notification |
| `OrderCancelled` | OrderService.cancel | — |
| `PaymentCreated` | PaymentService.create | — |
| `PaymentConfirmed` | PaymentService.confirm | erp_payment_confirmed, push_notification |
| `PaymentFailed` | PaymentService.fail | — |
| `DeliveryAssigned` | DeliveryService.assign | push_notification |
| `DeliveryStatusChanged` | DeliveryService.update_status | — |
| `DeliveryCompleted` | DeliveryService.complete | erp_delivery_completed, push_notification |
| `ShippingCalculated` | ShippingService.calculate | — |

**Registro em `main.py lifespan`:**
```python
bus.subscribe(OrderCreated, erp_order_created_handler)
bus.subscribe(PaymentConfirmed, erp_payment_confirmed_handler)
# ... etc.
```

**Handlers pré-definidos (stubs — implementar conforme necessidade):**
- `erp_order_created_handler` → POST para ERP / fiscal
- `erp_order_status_handler` → PATCH status no ERP
- `erp_payment_confirmed_handler` → emitir NF-e via ERP API
- `erp_delivery_completed_handler` → fechar entrega no ERP
- `push_notification_handler` → Firebase FCM / OneSignal

---

### 9.3 Exceções de Domínio

**Arquivo:** `backend/core/exceptions.py`

```python
class DomainError(Exception):
    http_status: int = 400
    message: str
    code: str       # nome da classe por padrão
```

**Hierarquia por domínio:**

| Exceção | http_status | Quando |
|---------|------------|--------|
| `OrderNotFound` | 404 | Pedido não existe |
| `CartEmpty` | 400 | Checkout sem itens |
| `ProductNotFound` | 404 | Produto inativo ou inexistente |
| `PriceConflict` | 400 | Preço enviado ≠ preço do banco |
| `FlavorDivisionMismatch` | 400 | len(flavors) ≠ flavor_division |
| `MaxFlavorsExceeded` | 400 | flavor_division > max_flavors |
| `InvalidStatusTransition` | 400 | Transição inválida na state machine |
| `PaymentNotFound` | 404 | — |
| `PaymentAlreadyExists` | 409 | Pedido já tem pagamento |
| `PaymentOrderNotEligible` | 400 | Pedido não está em 'pending' ao criar pagamento |
| `PaymentAmountMismatch` | 400 | amount ≠ order.total |
| `GatewayError` | 502 | Erro na chamada ao gateway |
| `GatewayNotConfigured` | 503 | Credencial ausente |
| `WebhookSignatureInvalid` | 403 | HMAC inválido |
| `ShippingZoneNotFound` | 404 | — |
| `ShippingRuleNotFound` | 404 | — |
| `CouponNotFound` | 404 | — |
| `CouponExpired` | 400 | — |
| `CouponExhausted` | 400 | — |
| `CouponMinValueNotMet` | 400 | — |
| `DeliveryNotFound` | 404 | — |
| `DeliveryPersonNotFound` | 404 | — |
| `DeliveryPersonUnavailable` | 400 | Motoboy está "busy" |
| `OrderNotReadyForDelivery` | 400 | Pedido não está em ready_for_pickup |
| `DeliveryAlreadyAssigned` | 409 | Pedido já tem entrega ativa |

Todas as rotas convertem `DomainError` em `HTTPException(status_code=exc.http_status, detail=exc.message)`.

---

## 10. Integrações Externas

### Mercado Pago (SDK 2.3.0 — ativo)

**PIX:**
```python
sdk = mercadopago.SDK(access_token)
result = sdk.payment().create({
    "transaction_amount": amount,
    "payment_method_id": "pix",
    "payer": {"email": "cliente@pizzaapp.com"}
})
# Retorna: qr_code_base64, qr_code (copia e cola)
```

**Cartão (Checkout Pro):**
```python
result = sdk.preference().create({
    "items": [...],
    "notification_url": "https://dominio.com/payments/webhook",
    "back_urls": {"success": "...", "failure": "...", "pending": "..."}
})
# Retorna: sandbox_init_point (teste) ou init_point (produção)
```

**Webhook:**
- Header: `x-signature: ts=<ts>,v1=<hmac-sha256>`
- Payload: `{"action": "payment.updated", "data": {"id": "<mp_id>"}}`
- Serviço consulta MP (`sdk.payment().get(id)`) para confirmar status — **não confia no payload**

### Stripe (estrutura pronta — SDK não instalado)
- `pip install stripe`
- Descomentar bloco em `StripeGateway.create_payment()`
- Usar `PaymentIntent` + `stripe.Webhook.construct_event()`

### PagSeguro (estrutura pronta — REST)
- Implementar em `PagSeguroGateway.create_payment()`

---

## 11. Sistema de Multi-Sabor

### Configuração (admin)
- `max_flavors`: 2 ou 3 (limita opções no seletor de divisão)
- `pricing_rule`: most_expensive | average | proportional

### Divisão Visual (SVG)

| Divisão | Implementação SVG |
|---------|------------------|
| 1 (Inteira) | Círculo completo com cor do sabor |
| 2 (Meio a Meio) | `<clipPath>` com `<rect>` esquerda/direita |
| 3 Sabores | Três setores de 120° via `sectorPath()` |

**Fórmula do setor:**
```
M cx cy L x1 y1 A r r 0 0 1 x2 y2 Z
onde: x = cx + r × cos(θ), y = cy + r × sin(θ)
Setores: [-90°→30°], [30°→150°], [150°→270°]
```

### Cálculo de Preço (front-end e back-end — idênticos)

```typescript
// most_expensive
price = Math.max(...flavors.map(f => f.price))

// average
price = flavors.reduce((s, f) => s + f.price, 0) / flavors.length

// proportional
price = flavors.reduce((s, f) => s + f.price / division, 0)
```

### Chave única do carrinho
`cartItemId = "cart-{timestamp}-{random4chars}"`
Permite que o mesmo produto apareça múltiplas vezes no carrinho com combinações diferentes de sabores.

---

## 12. Regras de Negócio Críticas

1. **Preço sempre revalidado no servidor** — front-end envia `final_price`, backend recalcula e compara (tolerância ±R$0,01). Diferença → HTTP 400 `PriceConflict`.

2. **Toda mudança de status passa pela StateMachine** — nenhuma rota ou ERP pode setar `order.status = X` diretamente. Transição inválida → HTTP 400 `InvalidStatusTransition`.

3. **Fluxo obrigatório de status do pedido:**
   `pending → waiting_payment → paid → preparing → on_the_way → delivered`
   - NÃO pode ir para `preparing` sem pagamento aprovado (`paid`)
   - NÃO pode ir para `delivered` sem passar por `on_the_way`
   - A state machine bloqueia qualquer atalho com `InvalidStatusTransition`

4. **Pagamento abre a janela: `pending → waiting_payment`** — ao chamar `POST /payments/create`, o pedido imediatamente avança para `waiting_payment`. Isso impede modificações no pedido enquanto o pagamento está em aberto.

5. **Pagamento confirma pedido atomicamente** — `PaymentService.confirm()` usa `payment_sm` + `order_sm` na mesma transação (`waiting_payment → paid`). Os dois nunca ficam dessincronizados.

6. **Idempotência de pagamento** — `PaymentAlreadyExists` (409) se `order.payment` já existe. `PaymentOrderNotEligible` (400) se pedido não está em `pending`.

7. **Webhook verificado na API do gateway** — o backend re-consulta `sdk.payment().get(id)` para confirmar status, não confia no payload do webhook.

8. **Motoboy só pode ser atribuído após pagamento confirmado** — `DeliveryService.assign()` aceita pedidos em `preparing` ou `ready_for_pickup`. A state machine garante que nenhum desses status é atingível sem passar por `paid`.

9. **Frete salvo como snapshot no pedido** — `Order.shipping_fee` é gravado no momento da criação. Mudanças futuras nas regras de frete não afetam pedidos existentes.

10. **Motoboy liberado automaticamente** — ao marcar entrega como "failed", "cancelled" ou "completed", `DeliveryService` coloca o motoboy de volta em "available".

11. **Pontos de fidelidade concedidos apenas na entrega** — `award_points_for_order()` chamado quando pedido muda para "delivered".

12. **Cupom decrementado na criação do pedido** — `mark_used()` é chamado dentro de `create_from_checkout()`, não ao aplicar o cupom.

13. **Eventos publicados após commit** — handlers de ERP e push notification nunca comprometem a consistência do banco. Falha do handler é logada e ignorada.

14. **Tailwind JIT — classes dinâmicas** — todos os nomes de classe aparecem literalmente no código (sem interpolação). O `colorPalette` é um objeto com strings completas.

15. **pydantic-settings com `extra = "ignore"`** — necessário para ignorar variáveis Vite/Node do `.env` raiz (ex: `VITE_PUBLIC_BUILDER_KEY`, `PING_MESSAGE`).

---

## 13. Fluxo Completo de um Pedido

```
STATUS DO PEDIDO AO LONGO DO FLUXO:
  pending → waiting_payment → paid → preparing → on_the_way → delivered

════════════════════════════════════════════════════════════════════════

1. Cliente navega pela Home
   └── Carrossel de produtos → /product/:id

2. Página do produto
   └── Seleciona tamanho + divisão + sabores
   └── Preço calculado em tempo real
   └── "Adicionar ao Carrinho" → /cart

3. Carrinho
   └── Revisa itens + preços
   └── "Finalizar Pedido" → /checkout

4. Checkout  [order.status = "pending"]
   └── Preenche dados de entrega
   └── POST /orders/checkout:
       ├── OrderService.create_from_checkout()
       ├── ShippingService.calculate() → frete salvo no pedido (snapshot)
       ├── CouponService.apply() (se houver)
       ├── Persiste Order + Items + Flavors  (status = pending)
       ├── Publica OrderCreated → ERP, push
       └── Retorna order_id
   └── Navega para /order-tracking?orderId=...

5. Pagamento iniciado  [order.status = "waiting_payment"]
   └── POST /payments/create:
       ├── PaymentService.create()
       │   ├── Valida: pedido existe, status = pending, sem pagamento duplicado
       │   ├── Valida: amount == order.total (±R$0,01)
       │   ├── Gateway.create_payment() → QR Code PIX ou payment_url
       │   ├── order_sm: pending → waiting_payment  ← NOVO
       │   └── Persiste Payment + order.status atomicamente
       └── Retorna {qr_code, qr_code_text} ou {payment_url}
   └── Cliente paga (PIX / cartão)
   └── Caixa confirma (dinheiro) → POST /payments/cash/{order_id}
       └── pending → waiting_payment → paid (em uma única chamada)

6. Pagamento confirmado  [order.status = "paid"]
   └── Gateway → POST /payments/webhook
   └── PaymentService.process_webhook():
       ├── Verifica assinatura HMAC (x-signature)
       ├── Re-consulta status na API do gateway (não confia no payload)
       ├── PaymentService.confirm():
       │   ├── payment_sm: pending → paid
       │   ├── order_sm: waiting_payment → paid  ← status correto
       │   └── Publica PaymentConfirmed → ERP (NF-e), push
       └── Retorna {"status": "ok", "payment_status": "paid"}

7. Produção  [order.status = "preparing"]
   └── PATCH /orders/{id}/status → "preparing"
       └── Só possível a partir de "paid" (state machine bloqueia qualquer outro)
   └── [Opcional] PATCH /orders/{id}/status → "ready_for_pickup"
       └── Sinaliza que a pizza saiu do forno

8. Atribuição de entrega  [order.status = "on_the_way"]
   └── POST /delivery/assign:
       ├── DeliveryService.assign()
       ├── Valida: pedido em "preparing" OU "ready_for_pickup"
       │   └── (ambos garantem pagamento confirmado — state machine não deixa chegar
       │       nesses status sem passar por "paid")
       ├── Valida: motoboy ativo e "available"
       ├── Cria Delivery record  (status = assigned)
       ├── Motoboy → "busy"
       ├── order_sm: preparing/ready_for_pickup → on_the_way
       └── Publica DeliveryAssigned → push ("🛵 Motoboy a caminho!")

9. Rastreio da entrega  [order.status = "delivered"]
   └── PATCH /delivery/{id}/status → "picked_up"
   └── PATCH /delivery/{id}/status → "on_the_way"
   └── PATCH /delivery/{id}/status → "delivered"
       ├── order_sm: on_the_way → delivered
       └── award_points_for_order() → loyalty points
   └── POST /delivery/{id}/complete (prova de entrega)
       ├── Motoboy → "available"
       ├── total_deliveries++
       └── Publica DeliveryCompleted → ERP, push ("🎉 Bom apetite!")

10. Avaliação
    └── POST /delivery/{id}/rate
        └── Atualiza média ponderada do motoboy

11. Cliente acompanha em /order-tracking
    └── Barra de progresso: Preparing → On the way → Delivered
```

---

## 14. Atualizacao 2026-04-23 - Mercado Pago Payment Brick

Esta secao registra o fluxo atual implementado no commit `b5e33c3`. Ela prevalece sobre referencias antigas deste documento a Checkout Pro, QR/link gerado diretamente no backend ou confirmacao de pagamento baseada em resposta do frontend.

### 14.1 Resumo da mudanca

O checkout foi refatorado para usar Mercado Pago Payment Brick. O frontend cria o pedido, renderiza o Brick e envia o `formData` para o backend. O backend cria/processa o pagamento no Mercado Pago, mas o pedido so vira pago depois que o webhook do Mercado Pago for recebido e o backend consultar a API do Mercado Pago para confirmar o status real.

### 14.2 Variaveis de ambiente

Frontend Vite:

```env
VITE_MERCADO_PAGO_PUBLIC_KEY=
```

Backend:

```env
PAYMENT_PROVIDER=mercado_pago
MERCADO_PAGO_ACCESS_TOKEN=
MERCADO_PAGO_PUBLIC_KEY=
MERCADO_PAGO_WEBHOOK_SECRET=
```

Regras:
- `VITE_MERCADO_PAGO_PUBLIC_KEY` e chave publica e pode ser exposta ao browser.
- `MERCADO_PAGO_ACCESS_TOKEN` e `MERCADO_PAGO_WEBHOOK_SECRET` ficam somente no backend.
- Se `MERCADO_PAGO_WEBHOOK_SECRET` estiver configurado, webhook sem `x-signature` e rejeitado.

### 14.3 Frontend

Arquivo principal: `client/pages/Checkout.tsx`.

Fluxo:
1. Cliente preenche dados, frete e cupom no checkout.
2. Frontend chama `ordersApi.checkout()` via `client/lib/api.ts`.
3. Backend retorna pedido criado com status `aguardando_pagamento`.
4. Frontend carrega `https://sdk.mercadopago.com/js/v2`.
5. Frontend instancia `new MercadoPago(publicKey, { locale: "pt-BR" })`.
6. Frontend renderiza o Payment Brick em `#paymentBrick_container`.
7. `onSubmit` do Brick envia `formData` para `paymentsApi.createFromBrick(order_id, formData)`.
8. Checkout consulta `ordersApi.paymentStatus(order_id)` periodicamente.
9. Apenas quando backend retornar `payment_status=approved` ou `pedido_status=pago`, o carrinho e limpo e o usuario e enviado para rastreio.

Estados exibidos no checkout:
- aguardando pagamento
- pagamento aprovado
- pagamento recusado
- pagamento expirado/cancelado
- erro no pagamento

### 14.4 Endpoints atuais

Todos os endpoints tambem estao disponiveis com prefixo `/api` por alias em `backend/main.py`.

| Metodo | Rota | Funcao |
|--------|------|--------|
| `POST` | `/orders` | Cria pedido com `pedido_status=aguardando_pagamento` e `payment_status=pending` |
| `POST` | `/orders/checkout` | Alias legado para criar pedido |
| `GET` | `/orders/{id}/payment-status` | Retorna status atual do pedido/pagamento para o frontend |
| `GET` | `/payments/public-key` | Retorna Public Key do Mercado Pago cadastrada no backend |
| `POST` | `/payments/create` | Recebe `formData` do Brick e cria/processa pagamento no Mercado Pago |
| `GET` | `/payments/{order_id}` | Retorna pagamento por pedido |
| `POST` | `/payments/webhook` | Webhook legado de pagamento |
| `POST` | `/webhooks/mercadopago` | Webhook atual esperado para Mercado Pago |

Endpoint publico recomendado no painel Mercado Pago:

```txt
https://SEU_DOMINIO/api/webhooks/mercadopago
```

### 14.5 Banco de dados

`orders` recebeu:
- `external_reference`
- novos status: `aguardando_pagamento`, `pago`, `pagamento_recusado`, `pagamento_expirado`

`payments` recebeu:
- `provider`
- `mercado_pago_payment_id`
- `external_reference`
- `raw_response`
- `updated_at`
- novos status: `approved`, `rejected`, `cancelled`, `expired`
- novo metodo: `debit_card`

Nova tabela `payment_events`:

| Coluna | Uso |
|--------|-----|
| `id` | ID interno do evento |
| `provider` | Ex.: `mercado_pago` |
| `event_type` | Acao/tipo recebido no webhook |
| `mercado_pago_payment_id` | ID do pagamento no Mercado Pago |
| `external_reference` | Vinculo com pedido interno |
| `raw_payload` | Payload bruto recebido |
| `processed_at` | Quando o evento foi processado |
| `created_at` | Criacao local |

Migration criada:

```txt
backend/migrations/versions/20260423_payment_brick.py
```

O startup fallback em `backend/main.py` tambem inclui migracoes idempotentes para os novos campos, indices, enums e `payment_events`.

### 14.6 PaymentService atual

Arquivo: `backend/services/payment_service.py`.

Responsabilidades:
- carregar configuracao do gateway;
- validar pedido e valor;
- garantir `external_reference`;
- criar/reusar `Payment` pendente;
- criar pagamento em `/v1/payments` do Mercado Pago;
- usar `X-Idempotency-Key`;
- salvar `mercado_pago_payment_id`, `raw_response` e `webhook_data`;
- nao marcar aprovado por resposta do frontend ou resposta imediata do create;
- processar webhook, consultar `/v1/payments/{id}` e aplicar status real;
- chamar `sendOrderToSaipos(orderId)` apenas quando o status muda pela primeira vez para `approved`.

Mapeamento de status Mercado Pago:

| Mercado Pago | `payments.status` | `orders.status` |
|--------------|-------------------|-----------------|
| `approved` | `approved` | `pago` |
| `rejected` / `charged_back` | `rejected` | `pagamento_recusado` |
| `cancelled` / `canceled` | `cancelled` | `pagamento_expirado` |
| `expired` | `expired` | `pagamento_expirado` |
| demais pendentes | `pending` | `aguardando_pagamento` |

### 14.7 Idempotencia e seguranca

Regras obrigatorias implementadas:
- Pedido nao e duplicado pelo webhook.
- Pagamento ja aprovado nao e recriado.
- Webhook pode ser chamado mais de uma vez sem reenviar pedido para Saipos.
- `external_reference` vincula pagamento Mercado Pago ao pedido interno.
- Backend nao confia no payload do webhook: sempre consulta a API do Mercado Pago.
- Frontend nunca marca pedido como pago.
- Pedido nao e enviado para Saipos antes de `payment_status=approved`.

### 14.8 Saipos

Arquivo:

```txt
backend/services/saipos_service.py
```

Funcao stub atual:

```python
sendOrderToSaipos(order_id: str) -> None
```

Ela registra log quando chamada. Quando a integracao real Saipos estiver disponivel, a implementacao deve substituir o stub mantendo a mesma assinatura para preservar o contrato com `PaymentService`.

### 14.9 Validacao executada

Comandos executados apos a implementacao:

```powershell
npm.cmd run typecheck
npm.cmd test
npm.cmd run build
.\.tools\python-3.12.10-embed-amd64\python.exe -m compileall -q backend
git diff --check
```

Resultados:
- TypeScript passou.
- Vitest passou: 4 arquivos, 20 testes.
- Build Vite passou.
- Compilacao Python do backend passou.
- `git diff --check` passou.

### 14.10 Commit e push

Commit enviado para `origin/main`:

```txt
b5e33c3 Implement Mercado Pago Payment Brick flow
```

---

## 15. Atualizacao 2026-04-24 - Estado Atual Consolidado

Esta secao consolida a leitura atual do codigo em 2026-04-24 e deve prevalecer sobre trechos legados deste documento ate que a base seja reescrita por completo. Ela foi criada para reduzir divergencias entre documentacao antiga e o sistema Moschettieri em producao/desenvolvimento.

### 15.1 Regra de precedencia da base

- Se uma secao antiga citar Checkout Pro como fluxo principal, considerar desatualizado: o fluxo atual e Mercado Pago Payment Brick.
- Se uma secao antiga citar adicionais/extras no produto, considerar desatualizado: adicionais foram removidos da experiencia atual.
- Se uma secao antiga citar tamanhos P, M, G ou GG para pizza, considerar desatualizado: a pizza usa apenas Brotinho e Pizza Grande.
- Se uma secao antiga citar pagamento aprovado pela resposta do frontend, considerar desatualizado: pagamento aprovado so vem de webhook validado no backend com consulta a API do Mercado Pago.
- Se houver conflito entre este item 15 e secoes anteriores, o item 15 e a referencia operacional mais atual.

### 15.2 Rotas principais atuais

Loja:
- `/` home da loja.
- `/product/:id` detalhe do produto.
- `/cart` carrinho.
- `/checkout` checkout com Payment Brick.
- `/order-tracking` rastreio/status do pedido.
- `/fidelidade`, `/cupons`, `/pedidos`, `/conta`, `/localizacao`, `/cardapio`.
- `/campanha/:slug` campanhas publicas.

Painel:
- `/painel` dashboard.
- `/painel/products` produtos, categorias, tamanhos, massas e variantes.
- `/painel/orders` pedidos.
- `/painel/fidelidade` fidelidade.
- `/painel/conteudo` conteudo textual/visual da loja.
- `/painel/pagamentos` credenciais e webhook.
- `/painel/frete` frete.
- `/painel/campanhas` campanhas.
- `/painel/chatbot` configuracao, FAQ, conversas, automacoes, IA e relatorios.
- `/painel/aparencia` tema visual.
- `/painel/home-config` controle do catalogo exibido na home.

### 15.3 Checkout e pagamento atual

O fluxo oficial de pagamento e Mercado Pago Payment Brick:

1. Cliente finaliza o pedido no checkout.
2. Backend cria pedido com `pedido_status=aguardando_pagamento` e `payment_status=pending`.
3. Frontend renderiza o Payment Brick com a Public Key.
4. Cliente paga com Pix ou cartao.
5. Frontend envia os dados do Brick para `/payments/create` via `client/lib/api.ts`.
6. Backend cria/processa o pagamento no Mercado Pago.
7. Mercado Pago notifica o backend em `/webhooks/mercadopago`.
8. Backend valida o evento consultando a API do Mercado Pago.
9. Apenas apos status real aprovado, backend atualiza `payment_status=approved`, `pedido_status=pago` e chama `sendOrderToSaipos(orderId)`.

Endpoints relevantes:
- `POST /orders` e `POST /orders/checkout`: criacao de pedido.
- `POST /payments/create`: processamento do Payment Brick.
- `GET /payments/public-key`: chave publica usada pelo frontend.
- `GET /orders/{id}/payment-status`: polling do checkout.
- `POST /webhooks/mercadopago`: webhook atual recomendado.
- `POST /payments/webhook`: webhook legado mantido por compatibilidade.

Variaveis esperadas:

```env
PAYMENT_PROVIDER=mercado_pago
MERCADO_PAGO_ACCESS_TOKEN=
MERCADO_PAGO_PUBLIC_KEY=
MERCADO_PAGO_WEBHOOK_SECRET=
VITE_MERCADO_PAGO_PUBLIC_KEY=
```

Regras criticas:
- Nao considerar pedido pago pela resposta do frontend.
- Usar `external_reference` para vincular pagamento e pedido interno.
- Salvar `mercado_pago_payment_id`.
- Registrar eventos em `payment_events`.
- Webhook deve ser idempotente.
- Pedido aprovado nao pode ser duplicado.
- Saipos so pode ser chamado quando o pagamento for aprovado pelo webhook validado.

### 15.4 Produto, pizzas e categorias

Produto:
- Modelo principal: `backend/models/product.py`.
- Rotas: `backend/routes/products.py`.
- API frontend: `client/lib/api.ts`.
- Tela admin: `client/pages/admin/Products.tsx`.
- Tela loja: `client/pages/Product.tsx`.

Categorias:
- Existe tabela `product_categories`.
- Migration: `backend/migrations/versions/20260424_product_categories.py`.
- Service: `backend/services/product_category_service.py`.
- Endpoints:
  - `GET /products/categories`
  - `POST /products/categories`
  - `PUT /products/categories/{category_id}`
  - `DELETE /products/categories/{category_id}`
- No painel, a aba Categorias permite criar, listar, ordenar, ativar/desativar e remover categorias.

Pizzas:
- Tamanhos permitidos na loja: `Brotinho` e `Pizza Grande`.
- O painel permite cadastrar o valor de cada tamanho por produto em `product_sizes`.
- Tipos de massa atuais: `Napolitana` e `Tradicional`, cadastrados por produto em `product_crust_types`.
- Cada massa pode ter `price_addition`.
- Adicionais como bacon, cebola ou camarao nao fazem parte da experiencia atual.

Bebidas/outros:
- Bebidas podem usar `product_drink_variants`.
- Produtos continuam com `product_type`: `pizza`, `drink` ou `other`.

Multi-sabor:
- A infraestrutura `multi_flavors_config` e os campos de sabores em pedido ainda existem.
- O fluxo atual deve preservar compatibilidade, sem reintroduzir adicionais ou tamanhos antigos.

### 15.5 Conteudo, home e logo

Logo:
- O logo atual e textual via `client/components/MoschettieriLogo.tsx`.
- A loja e o painel devem usar o mesmo componente textual, nao imagem.
- A barra superior da loja foi reduzida sem aumentar a largura do header.

Home da loja:
- Conteudo base vem de `siteContent.home` e da configuracao em `/home-config`.
- A home pode filtrar catalogo por todos os produtos, categorias selecionadas ou produtos selecionados.

Painel Conteudo:
- No submodulo Home, a pre-visualizacao com os textos "O que voce quer comer hoje?" e "Escolha sua Pizza Favorita" foi removida.
- Os placeholders dos campos foram deixados genericos para evitar acoplar a edicao ao texto antigo.

### 15.6 Painel administrativo e responsividade

Sidebar:
- Componente: `client/components/AdminSidebar.tsx`.
- Layout atual: sidebar compacta em telas menores e expandida no desktop.
- Icones simulados de status foram removidos do dashboard/painel.

Responsividade:
- Regras globais em `client/global.css` reduzem padding, ajustam grids e evitam estouro de botoes/textos.
- O admin usa `client/components/AdminGuard.tsx` como shell protegido.
- Ajustes visuais devem preservar os fluxos funcionais de carrinho, produtos, frete, cliente e pagamento.

Login:
- Tela: `client/pages/admin/Login.tsx`.
- Deve manter paleta coerente com o restante do sistema e o mesmo logo textual Moschettieri.

### 15.7 Chatbot e base de conhecimento do atendimento

Backend:
- Rotas publicas: `backend/routes/chatbot.py`.
- Rotas admin: `backend/routes/admin_chatbot.py`.
- Modelos: `backend/models/chatbot.py`.
- Service principal: `backend/services/chatbot_service.py`.
- Montagem de contexto: `backend/services/context_builder.py`.

Fontes de contexto:
- `chatbot_settings`
- `chatbot_faq`
- `chatbot_knowledge_docs`
- produtos, promocoes e regras de negocio consultadas pelo `ContextBuilder`

API admin existente:
- `/admin/chatbot/settings`
- `/admin/chatbot/faq`
- `/admin/chatbot/knowledge`
- `/admin/chatbot/automations`
- `/admin/chatbot/conversations`
- `/admin/chatbot/analytics`

Observacao operacional:
- Existem endpoints e modelos para documentos de conhecimento do chatbot.
- A UI atual do painel expõe FAQ e demais abas do chatbot; a API de knowledge ja existe em `client/lib/chatbotApi.ts`.

### 15.8 Banco de dados e migrations atuais relevantes

Migrations recentes:
- `backend/migrations/versions/20260423_payment_brick.py`
- `backend/migrations/versions/20260424_product_categories.py`

Tabelas/campos relevantes do estado atual:
- `orders`: status de pedido/pagamento, `external_reference`.
- `payments`: provider, `mercado_pago_payment_id`, `external_reference`, status e resposta bruta.
- `payment_events`: eventos recebidos do gateway.
- `product_categories`: categorias de catalogo.
- `product_sizes`: tamanhos por produto.
- `product_crust_types`: massas por produto.
- `product_drink_variants`: variantes de bebidas.
- `home_catalog_config`: configuracao do catalogo da home.
- `chatbot_knowledge_docs`: documentos de conhecimento do chatbot.

Regra de banco:
- Toda mudanca persistida deve ter migration Alembic correspondente.
- O startup em `backend/main.py` ainda contem fallbacks idempotentes para compatibilidade, mas migration continua sendo a fonte correta para evolucao controlada.

### 15.9 Deploy e operacao

Comando padrao apos push:

```bash
cd /home/deploy/moschettieri && git pull origin main && pnpm install && pnpm run build && sudo systemctl restart moschettieri-web moschettieri-api
```

Cuidados:
- `.env` em producao nao deve ser sobrescrito pelo pull.
- Se houver conflito em `.env`, resolver ou preservar o arquivo local antes de continuar.
- Em incidente real, verificar logs antes de reiniciar servicos.

### 15.10 Validacao local conhecida

Validoes recentes ja executadas neste ciclo:
- `npm.cmd run build` passou apos os ajustes de frontend.
- O ambiente local Windows apresentou historico de indisponibilidade do Python no PATH em alguns momentos; quando validar backend, preferir o Python embarcado do projeto se estiver disponivel.

Pendencias controladas:
- A integracao Saipos real ainda e stub em `backend/services/saipos_service.py`.
- Documentacao antiga acima desta secao ainda pode conter referencias legadas; esta secao 15 e a referencia consolidada mais atual ate a limpeza completa linha a linha.

---

## 16. Atualizacao 2026-05-03 - Estado Atual do Admin SaaS

Esta secao consolida a leitura atual do sistema feita em 2026-05-03. Ela deve ser usada como referencia mais recente para rotas, shell administrativo, modulos, backend e lacunas ainda pendentes de revisao manual.

### 16.1 Inventario atual de rotas do frontend

Rotas da loja:
- `/`
- `/product/:id`
- `/cart`
- `/checkout`
- `/order-tracking`
- `/fidelidade`
- `/cupons`
- `/pedidos`
- `/conta`
- `/localizacao`
- `/cardapio`
- `/campanha/:slug`
- `/motoboy`

Rotas publicas do painel:
- `/painel/login`

Rotas administrativas protegidas por `AdminGuard` e renderizadas dentro de `AdminLayout`:
- `/painel`
- `/painel/products`
- `/painel/orders`
- `/painel/cozinha`
- `/painel/fidelidade`
- `/painel/conteudo`
- `/painel/pagamentos`
- `/painel/frete`
- `/painel/funcionamento`
- `/painel/campanhas`
- `/painel/trafego-pago`
- `/painel/chatbot`
- `/painel/aparencia`
- `/painel/home-config`
- `/painel/lgpd`
- `/painel/configuracoes`
- `/painel/cupons`
- `/painel/clientes`
- `/painel/clientes/:id`
- `/painel/popup-saida`
- `/painel/usuarios`

Rotas de Marketing:
- `/painel/marketing`
- `/painel/marketing/campanhas`
- `/painel/marketing/visitantes`
- `/painel/marketing/links`
- `/painel/marketing/integracoes`
- `/painel/marketing/whatsapp`
- `/painel/marketing/email`
- `/painel/marketing/automacoes`
- `/painel/marketing/ads`
- `/painel/marketing/workflow`
- `/painel/marketing/cupons`

Rotas de CRM:
- `/painel/crm`
- `/painel/crm/inteligencia`
- `/painel/crm/pipeline`
- `/painel/crm/grupos`
- `/painel/crm/tarefas`

Rotas de Operacoes:
- `/painel/logistica`
- `/painel/cozinha`
- `/painel/orders`

### 16.2 Padrao atual do painel administrativo

Shell principal:
- `client/components/layout/AdminLayout.tsx` e a fonte unica de composicao para rotas protegidas do painel.
- `client/components/layout/AppSidebar.tsx` renderiza a sidebar fixa, grupos, submodulos e estado ativo.
- `client/components/layout/AdminHeader.tsx` renderiza o header visual unico da pagina usando metadados centralizados.
- `client/components/layout/PageContainer.tsx` controla area principal e espacamento.
- `client/components/layout/AdminPageChrome.tsx` e usado por paginas que precisam de conteudo interno com tabs/acoes, sem criar segundo header de pagina.

Metadados e navegacao:
- `client/config/adminNavigation.ts` e a fonte atual para grupos, itens, aliases e icones da sidebar.
- `client/config/adminPageMeta.ts` e a fonte atual para eyebrow, titulo e subtitulo do header global.
- Submodulos devem existir na sidebar. Eles nao devem ser duplicados como abas no header.

Compatibilidade e componentes legados:
- `client/components/AdminSidebar.tsx` atua como wrapper de compatibilidade para evitar segunda sidebar dentro do shell global.
- Acoes globais antigas foram neutralizadas para nao duplicar header, busca ou toolbar em paginas que ja estao dentro do `AdminLayout`.
- Novas paginas administrativas devem entrar pelo shell global e nao devem montar `AppHeader`, `AdminHeader` ou sidebar propria.

Tokens visuais:
- O padrao visual do painel esta concentrado em `client/global.css`, principalmente sob `.admin-shell`.
- A paleta do admin usa verde escuro como fundo principal e dourado como cor de acao/ativo.
- Cards, tabs, botoes, bordas, sombras e estados hover/focus devem reutilizar as classes/tokens ja existentes em vez de recriar estilos por pagina.

### 16.3 Estado visual dos principais modulos administrativos

Dashboard:
- Pagina: `client/pages/admin/Dashboard.tsx`.
- O bloco interno usa "Visao Geral" alinhado com a acao "Pedidos".
- O titulo principal vem do header global; nao deve haver titulo duplicado no corpo.

Produtos:
- Pagina: `client/pages/admin/Products.tsx`.
- Tabs internas `Produtos`, `Categorias` e `Configuracoes` representam secoes da mesma pagina.
- As tabs ficam alinhadas com o botao `Novo Produto`, sem caixa/borda envolvendo o grupo inteiro.

Pedidos:
- Pagina: `client/pages/admin/Orders.tsx`.
- O painel de controles `Ativos`, `Total`, `Alertas`, `Atualizar` e horario de atualizacao fica fixo como sub-header horizontal acima do pipeline.
- Somente a area dos pipelines/colunas de pedidos deve possuir rolagem horizontal.
- A rolagem horizontal deve ficar no wrapper do pipeline, mantendo os controles sem deslocamento lateral.

CRM:
- Paginas: `client/pages/admin/crm/*`.
- Rotas cobertas: Dashboard CRM, Inteligencia de Clientes, Pipeline, Grupos & Segmentacoes e Tarefas.
- `Grupos & Segmentacoes` pode ter tabs internas `Grupos`, `Tags` e `Segmentos`, pois representam conteudo interno da mesma pagina.
- Itens como Dashboard CRM, Clientes, Inteligencia, Pipeline e Tarefas devem continuar apenas na sidebar.

Marketing:
- Paginas: `client/pages/admin/marketing/*`.
- Inclui dashboard, campanhas, visitantes, links, integracoes, WhatsApp, Email, automacoes, Ads, workflow e cupons.
- Submodulos de marketing devem permanecer na sidebar e nao no header.

Configuracoes e operacao:
- Paginas cobertas incluem conteudo, pagamentos, frete, funcionamento da loja, chatbot, aparencia, usuarios, LGPD, impressora/modelos, cozinha e logistica.
- Cada pagina deve manter apenas um header visual e usar titulos internos somente quando forem complementares ao contexto.

### 16.4 Inventario atual do backend

Rotas backend existentes em `backend/routes/`:
- Admin e autenticacao: `admin.py`, `admin_auth.py`, `admin_users.py`, `auth.py`, `rbac.py`.
- Loja e catalogo: `products.py`, `home_config.py`, `theme.py`, `site_config.py`, `upload.py`.
- Pedidos e operacao: `orders.py`, `payments.py`, `shipping.py`, `delivery.py`, `store_operation.py`, `webhooks.py`.
- Clientes e relacionamento: `customers.py`, `customer_access.py`, `customer_events.py`, `crm.py`, `order_access.py`.
- Marketing: `marketing.py`, `whatsapp_marketing.py`, `email_marketing.py`, `automations.py`, `marketing_workflow.py`, `paid_traffic.py`, `ads_oauth.py`, `campaigns.py`, `promotions.py`, `coupons.py`, `exit_popup.py`, `loyalty.py`.
- Chatbot e privacidade: `chatbot.py`, `admin_chatbot.py`, `lgpd.py`.

Modelos atuais em `backend/models/`:
- `admin.py`, `campaign.py`, `chatbot.py`, `coupon.py`, `crm.py`, `customer.py`, `customer_event.py`, `delivery.py`, `home_config.py`, `loyalty.py`, `order.py`, `paid_traffic.py`, `payment.py`, `payment_config.py`, `product.py`, `product_promotion.py`, `promotion.py`, `rbac.py`, `shipping.py`, `shipping_v2.py`, `store_operation.py`, `theme.py`.

Services atuais em `backend/services/`:
- Core de negocio: `order_service.py`, `payment_service.py`, `shipping_service.py`, `delivery_service.py`, `coupon_service.py`, `loyalty_service.py`, `store_operation_service.py`.
- Catalogo e preco: `product_category_service.py`, `product_pricing_service.py`.
- Marketing e CRM: `campaign_service.py`, `paid_traffic_service.py`, `automation_service.py`, `customer_ai_service.py`, `customer_metrics_service.py`.
- Atendimento e contexto: `chatbot_service.py`, `context_builder.py`.
- Integracoes/IA: `saipos_service.py`, `ai/base.py`, `ai/factory.py`, `ai/openai_provider.py`, `ai/claude_provider.py`.

Observacoes de startup:
- `backend/main.py` inclui routers diretos e aliases `/api` para grande parte das rotas.
- O startup executa `create_all_tables()`, `_run_migrations()` e `seed_all(db)`.
- Eventos de pedido, pagamento e entrega sao conectados via `backend/core/events.py`.
- Mudancas de schema devem continuar usando Alembic; os fallbacks idempotentes de startup nao substituem migration.

### 16.5 Migrations atuais relevantes

Migrations presentes em `backend/migrations/versions/`:
- `20260423_payment_brick.py`
- `20260424_paid_traffic.py`
- `20260424_pizza_size_descriptions.py`
- `20260424_product_categories.py`
- `20260425_loyalty_settings.py`
- `20260425_product_promotions.py`
- `20260425_product_subcategories.py`
- `20260425_store_operation.py`
- `20260426_runtime_schema_backfill_core.py`
- `20260501_chatbot_modes.py`
- `20260501_crm_tags_segments.py`
- `20260501_customer_ai_profiles.py`
- `20260501_customer_crm_metrics.py`
- `20260502_customer_ai_analysis_jobs.py`
- `20260502_marketing_automation_queue.py`

### 16.6 Scripts de validacao do frontend

Scripts atuais em `package.json`:
- `npm run dev`
- `npm run build`
- `npm run build:client`
- `npm run build:server`
- `npm run start`
- `npm run test`
- `npm run format.fix`
- `npm run typecheck`

Observacao:
- Nao existe script `lint` declarado no `package.json` nesta leitura.
- Para mudancas de frontend, a validacao minima recomendada e `npm run typecheck` e `npm run build`.
- Para mudancas apenas documentais, validar diff e consistencia do Markdown e suficiente.

### 16.7 Lacunas que ainda precisam de revisao manual

- A documentacao historica antes das secoes 15 e 16 ainda possui trechos legados e pode citar rotas/modulos antigos incompletos.
- O inventario de aliases `/api` no backend deve ser revisado quando alguma integracao externa depender de prefixo especifico, pois nem todos os routers novos aparecem necessariamente com alias `/api` no mesmo bloco de inclusao.
- A integracao Saipos continua indicada como stub em `backend/services/saipos_service.py`.
- A padronizacao visual deve ser conferida manualmente em navegador nas rotas administrativas principais, principalmente paginas densas de Marketing, CRM, Logistica, Configuracoes e Pedidos.
- O estado local contem uma alteracao pendente em `client/pages/admin/Orders.tsx`; esta base documenta o comportamento esperado do workspace atual, mas o historico remoto so refletira isso apos commit e push.
