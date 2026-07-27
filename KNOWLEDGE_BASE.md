# Base de Conhecimento — PizzaApp
> Documento técnico completo: telas, funcionalidades, banco de dados, endpoints e integrações.
> Gerado em: 2026-04-13 | **Atualizado em: 2026-07-22** | Versao: 3.3.0

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
17. [Atualizacao 2026-05-13 - Estado Atual Completo](#17-atualizacao-2026-05-13---estado-atual-completo)
18. [Atualizacao 2026-07-01 - Gestão ERP Concluida](#18-atualizacao-2026-07-01---gestao-erp-concluida)
19. [Atualizacao 2026-07-03 - ASAAS Multi-Gateway](#19-atualizacao-2026-07-03---asaas-multi-gateway)
20. [Atualizacao 2026-07-03 - Cartao ASAAS na Tela Propria](#20-atualizacao-2026-07-03---cartao-asaas-na-tela-propria)
21. [Atualizacao 2026-07-03 - Backend ASAAS Cartao](#21-atualizacao-2026-07-03---backend-asaas-cartao)
22. [Atualizacao 2026-07-04 - Checkout ASAAS Cartao](#22-atualizacao-2026-07-04---checkout-asaas-cartao)
23. [Atualizacao 2026-07-04 - Admin ASAAS Cartao](#23-atualizacao-2026-07-04---admin-asaas-cartao)
24. [Atualizacao 2026-07-04 - Alerta de Atendimento Humano no Agente WhatsApp](#24-atualizacao-2026-07-04---alerta-de-atendimento-humano-no-agente-whatsapp)
25. [Atualizacao 2026-07-21 - Estado Atual Consolidado de Marketing e Notificacoes](#25-atualizacao-2026-07-21---estado-atual-consolidado-de-marketing-e-notificacoes)
26. [Atualizacao 2026-07-21 - Preparacao Multiempresa em Codigo](#26-atualizacao-2026-07-21---preparacao-multiempresa-em-codigo)
27. [Atualizacao 2026-07-22 - Rating WhatsApp, Previews e Automacoes Transversais](#27-atualizacao-2026-07-22---rating-whatsapp-previews-e-automacoes-transversais)

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
- publicar `PaymentConfirmed` quando o status muda pela primeira vez para `approved`, sem chamar sistema fiscal externo.

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
- Webhook pode ser chamado mais de uma vez sem duplicar efeitos de pagamento.
- `external_reference` vincula pagamento Mercado Pago ao pedido interno.
- Backend nao confia no payload do webhook: sempre consulta a API do Mercado Pago.
- Frontend nunca marca pedido como pago.
- Pedido pago nao aciona sistema fiscal externo automaticamente.

### 14.8 Sistemas fiscais externos

O ERP nao deve chamar, preparar ou depender de sistema fiscal externo por padrao. O fluxo de pagamento aprovado publica eventos internos; qualquer modulo fiscal deve ser autossuficiente e idempotente dentro do proprio ERP, salvo autorizacao explicita para uma integracao futura.

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
9. Apenas apos status real aprovado, backend atualiza `payment_status=approved`, `pedido_status=pago` e publica eventos internos.

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
- Nenhum sistema fiscal externo deve ser chamado pelo fluxo de pagamento.

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
- Historico: nesta leitura, o fluxo fiscal autossuficiente ainda estava pendente. Status atualizado na secao 18, com base interna Fiscal SEFAZ implementada na trilha Gestao.
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
- Integracoes/IA: `ai/base.py`, `ai/factory.py`, `ai/openai_provider.py`, `ai/claude_provider.py`.

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
- O ERP nao deve depender de integracao fiscal externa. O fiscal interno/autossuficiente da trilha Gestao esta descrito na secao 18 e exige validacao real em SEFAZ/homologacao antes de producao.
- A padronizacao visual deve ser conferida manualmente em navegador nas rotas administrativas principais, principalmente paginas densas de Marketing, CRM, Logistica, Configuracoes e Pedidos.
- O estado local deve ser sempre verificado com `git status -sb`; em 2026-05-13 o remoto `origin/main` estava sincronizado apos o commit `f5fa13a`, restando apenas ruido local em `.claude/*` e `backend/__pycache__/*`.

---

## 17. Atualizacao 2026-05-13 - Estado Atual Completo

Esta secao consolida a leitura atual feita em 2026-05-13. Quando houver divergencia com secoes historicas anteriores, esta secao deve ser tratada como a referencia mais recente.

### 17.1 Estado do repositorio

- Branch principal: `main`.
- Remoto: `https://github.com/telzmarketing/builderpizzaapp-main.git`.
- Ultimo push funcional confirmado: `f5fa13a feat(marketing): mapear eventos e ajustar notificacoes`.
- Sincronizacao apos push: `git rev-list --left-right --count origin/main...HEAD` retornou `0 0`.
- Ruido local conhecido e fora de escopo de commits funcionais: `.claude/settings*`, `.claude/worktrees/*` e `backend/__pycache__/*`.
- O projeto possui cerca de 346 arquivos principais em `backend/`, `client/`, `server/` e `shared/`.

### 17.2 Validacao atual

Comandos executados em 2026-05-13:

- `npm.cmd run typecheck`: passou.
- `npm.cmd test`: passou quando executado isoladamente, com 6 arquivos e 25 testes.
- `npm.cmd run build`: passou, gerando `dist/spa` e `dist/server`.
- `py -m py_compile backend/main.py`: nao executou porque nao ha Python instalado neste ambiente local.

Observacao operacional:
- Evitar rodar `npm test` em paralelo com outros comandos neste ambiente, pois uma execucao concorrente apontou o Vitest para uma copia sandbox e incluiu specs dentro de `.claude/worktrees`, gerando falha falsa.

### 17.3 Stack e scripts atuais

Scripts declarados em `package.json`:

- `npm run dev`
- `npm run build`
- `npm run build:client`
- `npm run build:server`
- `npm run start`
- `npm run test`
- `npm run format.fix`
- `npm run typecheck`

Nao ha script `lint` declarado.

Stack operacional:

- Frontend: React 18, TypeScript, Vite, Tailwind, React Router, shadcn/Radix, Lucide.
- Backend: FastAPI, SQLAlchemy, Pydantic, Alembic, PostgreSQL.
- Server JS: Vite SSR/Express em `server/`.
- Cliente de API frontend: `client/lib/api.ts`; componentes nao devem chamar `fetch` diretamente.

### 17.4 Rotas principais do app cliente

Rotas publicas relevantes em `client/App.tsx`:

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

Componente global da loja:

- `client/components/StoreSocialProofNotification.tsx` renderiza os baloes de prova social.
- O componente cria uma sessao anonima em `localStorage` e consulta `/store-notifications/next`.

### 17.5 Rotas atuais do painel administrativo

Rotas administrativas protegidas relevantes:

- `/painel`
- `/painel/bi`
- `/painel/products`
- `/painel/home-config`
- `/painel/orders`
- `/painel/cozinha`
- `/painel/logistica`
- `/painel/clientes`
- `/painel/clientes/:id`
- `/painel/crm`
- `/painel/crm/inteligencia`
- `/painel/crm/pipeline`
- `/painel/crm/grupos`
- `/painel/crm/tarefas`
- `/painel/marketing`
- `/painel/marketing/campanhas`
- `/painel/marketing/visitantes`
- `/painel/marketing/links`
- `/painel/marketing/integracoes`
- `/painel/marketing/whatsapp`
- `/painel/marketing/email`
- `/painel/marketing/automacoes`
- `/painel/marketing/ads`
- `/painel/trafego-pago`
- `/painel/marketing/workflow`
- `/painel/marketing/cupons`
- `/painel/marketing/notificacoes`
- `/painel/marketing/upsell`
- `/painel/campanhas`
- `/painel/fidelidade`
- `/painel/popup-saida`
- `/painel/conteudo`
- `/painel/pagamentos`
- `/painel/frete`
- `/painel/funcionamento`
- `/painel/chatbot`
- `/painel/aparencia`
- `/painel/usuarios`
- `/painel/lgpd`
- `/painel/configuracoes`

Fontes de navegacao e metadados:

- `client/config/adminNavigation.ts`
- `client/config/adminPageMeta.ts`

Regra vigente do painel:

- O shell global fica em `client/components/layout/AdminLayout.tsx`.
- Paginas administrativas nao devem montar header/sidebar propria.
- Ordem visual esperada: Header global, tabs quando aplicavel, toolbar, conteudo.

### 17.6 Inventario backend atual

Rotas em `backend/routes/`:

- Admin/autenticacao: `admin.py`, `admin_auth.py`, `admin_users.py`, `auth.py`, `rbac.py`.
- Loja/catalogo: `products.py`, `home_config.py`, `theme.py`, `site_config.py`, `upload.py`.
- Pedidos/operacao: `orders.py`, `payments.py`, `shipping.py`, `delivery.py`, `store_operation.py`, `webhooks.py`.
- Clientes/CRM: `customers.py`, `customer_access.py`, `customer_events.py`, `crm.py`, `order_access.py`.
- Marketing: `marketing.py`, `whatsapp_marketing.py`, `email_marketing.py`, `automations.py`, `marketing_workflow.py`, `paid_traffic.py`, `ads_oauth.py`, `campaigns.py`, `promotions.py`, `coupons.py`, `exit_popup.py`, `loyalty.py`, `store_notifications.py`, `upsells.py`.
- BI: `bi.py`.
- Chatbot/privacidade: `chatbot.py`, `admin_chatbot.py`, `lgpd.py`.

Modelos novos ou relevantes:

- `store_notification.py`: notificacoes reais/manuais, capturadas e historico de exibicao.
- `upsell.py`: upsells, metricas, eventos e vinculo com pedido.
- `business_intelligence.py`: base de BI.
- `paid_traffic.py`: pixels, CAPI e rastreamento pago.

Services novos ou relevantes:

- `store_notification_service.py`
- `upsell_engine.py`
- `business_intelligence_service.py`
- `paid_traffic_service.py`
- `automation_service.py`

`backend/main.py` inclui routers diretos e aliases com prefixo `/api` para os modulos principais, incluindo `bi`, `store_notifications` e `upsells`.

### 17.7 Migrations atuais relevantes

Migrations presentes ate 2026-05-13:

- `20260503_business_intelligence.py`
- `20260503_driver_mobile_logistics.py`
- `20260504_coupon_compound_benefits.py`
- `20260504_customer_password_auth.py`
- `20260505_coupon_public_profile.py`
- `20260505_coupon_trigger_automation.py`
- `20260506_campaign_product_link.py`
- `20260506_store_notifications.py`
- `20260507_notification_captured.py`
- `20260507_whatsapp_interval_range.py`
- `20260507_whatsapp_providers_media.py`
- `20260507_whatsapp_template_media.py`
- `20260508_whatsapp_contact_lists.py`
- `20260511_best_seller_badge.py`
- `20260511_visitor_location_status.py`
- `20260512_ads_pixel_capi_config.py`
- `20260512_ads_pixel_event_defaults.py`
- `20260512_delivery_problem_resolution.py`
- `20260512_exit_popup_delay.py`
- `20260513_store_notification_display_rules.py`

Regra:
- Toda alteracao persistente deve ter migration Alembic.
- Os `ALTER TABLE ... IF NOT EXISTS` de `backend/main.py` sao compatibilidade de runtime e nao substituem migration.

### 17.8 Marketing, pixel e trafego pago

Separacao vigente:

- `Marketing > Integracoes` (`MarketingIntegracoes.tsx`) concentra Meta Graph/OAuth e credenciais de conta.
- `Trafego Pago` (`PaidTraffic.tsx`) concentra Pixel ID, Conversions API token, codigo base e configuracoes de eventos.
- `client/lib/tracking.ts` inicializa e dispara tracking da loja.
- Configuracao store-facing do pixel vem de `/paid-traffic/pixels/store-config`.

Eventos mapeados:

- O modulo de automacoes em `MarketingAutomacoes.tsx` possui aba/eventos mapeados e consome tipos em `client/lib/api.ts`.
- Backend relacionado: `backend/routes/automations.py` e `backend/services/automation_service.py`.

### 17.9 Notificacoes da loja e prova social

Fluxo atual:

- Painel: `client/pages/admin/marketing/MarketingStoreNotifications.tsx`.
- Balão na loja: `client/components/StoreSocialProofNotification.tsx`.
- Backend: `backend/routes/store_notifications.py`, `backend/services/store_notification_service.py`.
- Model/schema: `backend/models/store_notification.py`, `backend/schemas/store_notification.py`.

Regras implementadas:

- Compras reais/capturadas tem prioridade sobre notificacoes manuais.
- Notificacoes manuais usam o campo `purchase_minutes_ago`.
- O painel exibe e edita o campo "Exibir como compra realizada ha X minutos".
- Tempo precisa ser inteiro positivo.
- Notificacao com nome, produto, bairro ou tempo faltando nao e exibida.
- Notificacao cujo horario simulado fique antes de 18:00 nao e exibida.
- Cliente logado nao deve ver notificacao da propria compra quando `source_customer_id` coincide com `customer_id`.
- Visitante anonimo recebe `anonymous_session_id` e o backend registra historico em `store_notification_impressions`.
- A mesma notificacao nao deve aparecer mais de uma vez para o mesmo cliente/sessao anonima.
- Se nao houver notificacao elegivel, o frontend nao forca exibicao.

Campos adicionados:

- `store_notifications.purchase_minutes_ago`
- `store_notification_impressions.customer_id`
- `store_notification_impressions.anonymous_session_id`
- `store_notification_impressions.notification_type`

### 17.10 WhatsApp marketing

Estado atual:

- Backend: `backend/routes/whatsapp_marketing.py`.
- Painel: `client/pages/admin/marketing/MarketingWhatsApp.tsx`.
- Configuracao suporta intervalo minimo/maximo entre envios: `interval_min_seconds` e `interval_max_seconds`.
- Listas de contatos possuem estrutura minima: nome e telefone.
- O disparador permite selecionar/criar lista dentro do fluxo de envio.
- Templates suportam midia e provedores.
- Deve manter fallback de `interval_seconds` para compatibilidade.

### 17.11 Cupons, campanhas, promocoes e banners

Cupons:

- Backend principal: `backend/services/coupon_service.py`.
- Cupom com gatilho de automacao so deve ser usado por clientes elegiveis pelo gatilho.
- Cupom sem gatilho segue liberado conforme suas regras normais.

Promocoes e banners:

- Painel: `client/pages/admin/AdminCampanhas.tsx`.
- Produtos vinculados a campanhas devem listar produtos promocionais elegiveis, nao apenas brindes.
- Migration relevante: `20260506_campaign_product_link.py`.

### 17.12 Produtos, tamanhos e massas

Painel principal:

- `client/pages/admin/Products.tsx`.

Regras recentes:

- Cadastro inicial de produto nao deve exigir preco base quando o preco depende de tamanho/massa/borda.
- Tamanhos e tipos de massa podem ser organizados por ordem.
- Produtos no painel podem ser ordenados por criterios como recente, data, nome e tipo.
- Helpers de midia em `client/lib/api.ts` continuam relevantes para resolver uploads/imagens.

### 17.13 Carrinho e upsell

Upsell:

- Backend: `backend/routes/upsells.py`, `backend/services/upsell_engine.py`, `backend/models/upsell.py`.
- Painel: `/painel/marketing/upsell`.
- Carrinho deve exibir upsell logo abaixo do produto selecionado pelo cliente.
- Tabelas/runtime incluem `upsells`, `upsell_metrics`, `upsell_events` e `order_upsells`.

### 17.14 Pedidos, cozinha, impressora e som

Pedidos:

- Painel: `client/pages/admin/Orders.tsx`.
- Cozinha: `client/pages/admin/Cozinha.tsx`.
- Impressora/configuracoes: `client/pages/admin/AdminConfiguracoes.tsx` e helpers em `client/lib/printing.ts`.

Comportamentos recentes:

- Ao confirmar pedido, impressao deve gerar via da cozinha e via completa/recepcao.
- Via de entrega deve mascarar sobrenome e ocultar telefone quando aplicavel.
- Alerta sonoro de novo pedido deve tocar e, em seguida, dizer em voz alta "PEDIDO".
- `client/lib/printing.spec.ts` cobre montagem de comandas.

### 17.15 Logistica, motoboy e entrega

Arquivos principais:

- `client/pages/Motoboy.tsx`
- `client/pages/admin/logistica/LogisticaMapa.tsx`
- `backend/routes/delivery.py`
- `backend/services/delivery_service.py`

Regras vigentes:

- Usuario motoboy deve ver apenas modulo/fluxo de logistica.
- Mapa deve renderizar o pin do motoboy.
- Sistema deve sugerir rota de entregas e link acionavel do Google Maps.

### 17.16 BI e CRM

BI:

- Rota frontend: `/painel/bi`.
- Backend: `backend/routes/bi.py`, `backend/services/business_intelligence_service.py`, `backend/models/business_intelligence.py`.

CRM:

- Rotas: `/painel/crm`, `/painel/crm/inteligencia`, `/painel/crm/pipeline`, `/painel/crm/grupos`, `/painel/crm/tarefas`.
- Services relevantes: `customer_ai_service.py`, `customer_metrics_service.py`.
- Modelos relevantes: `crm.py`, `customer_event.py`, `customer.py`.

### 17.17 Chatbot e configuracoes

Chatbot:

- Backend: `chatbot.py`, `admin_chatbot.py`, `chatbot_service.py`.
- Painel: `/painel/chatbot` e paginas em `client/pages/admin/chatbot/`.
- Suporta modos/provedor de IA e configuracoes de atendimento.

Configuracoes:

- `/painel/configuracoes` concentra impressora/modelos e som.
- `/painel/funcionamento` concentra horario de loja.
- `/painel/lgpd` concentra politicas e consentimentos.

### 17.18 Regras operacionais para proximas demandas

- Antes de alterar comportamento, mapear estrutura do projeto e arquivos responsaveis.
- Preservar arquitetura atual: rota delega, service decide regra, schema valida, frontend consome via `client/lib/api.ts`.
- Em painel admin, manter o shell global e evitar headers/sidebars duplicados.
- Quando houver banco, criar migration Alembic e manter compatibilidade de runtime se o projeto ja fizer isso no mesmo modulo.
- Para frontend, validar com `npm.cmd run typecheck` e `npm.cmd run build`.
- Para testes, executar `npm.cmd test` isoladamente neste ambiente.
- Python local nao esta disponivel; validacao backend Python precisa ocorrer em ambiente com Python instalado.
- Ao fazer push, manter `.claude/*` e `backend/__pycache__/*` fora do commit.

---

## 18. Atualizacao 2026-07-01 - Gestão ERP Concluida

Status: trilha Gestão ERP executada ate a Fase 10.

Documento operacional principal:

- `docs/gestao-operacao-fase-10.md`

Documento de desenho e historico:

- `docs/GESTAO_AUDIT.md`

### 18.1 Navegacao e configuracao

Rotas administrativas:

- `/painel/gestao/estoque`
- `/painel/gestao/cmv`
- `/painel/gestao/financeiro`
- `/painel/gestao/fiscal`

Backend:

- `backend/routes/gestao.py`
- `backend/services/gestao_service.py`
- `backend/models/gestao.py`

Os modulos Estoque, CMV, Financeiro e Fiscal possuem configuracao persistida em `gestao_module_settings`.

Regra de UX atual:

- A categoria deve aparecer como `Gestão` na navegacao e no titulo de pagina.
- Os submodulos Estoque, CMV, Financeiro e Fiscal ficam na sidebar da categoria Gestão.
- Dentro de cada submodulo, as abas devem representar secoes internas do modulo selecionado, nunca repetir `Estoque / CMV / Financeiro / Fiscal`.
- `AdminGestao.tsx` e o wrapper comum para configuracao/habilitacao do modulo, mas as abas locais sao definidas por cada pagina.

Abas internas atuais:

- Estoque: `Configuracoes`, `Insumos`, `Base`, `Fornecedores`, `Compras`, `Entradas`.
- CMV: `Configuracoes`, `Indicadores`, `Produtos e fichas`.
- Financeiro: `Configuracoes`, `Resumo e DRE`, `Cadastros`, `Lancamentos`.
- Fiscal: `Configuracoes`, `Resumo`, `Empresa`, `Certificado e serie`, `Perfis tributarios`, `Documentos`.

### 18.2 Estoque

Arquivos principais:

- `backend/models/inventory.py`
- `backend/schemas/inventory.py`
- `backend/services/inventory_service.py`
- `backend/routes/inventory.py`
- `client/pages/admin/gestao/GestaoInventory.tsx`

Regras:

- Estoque nasce opcional.
- Venda publica so e bloqueada quando `inventory.enabled=true` e `inventory.sales_control_enabled=true`.
- Falta de insumo obrigatorio deixa produtos dependentes indisponiveis.
- Cozinha nao e bloqueada pelo Estoque.

### 18.3 CMV

Arquivos principais:

- `backend/models/cmv.py`
- `backend/services/cmv_service.py`
- `backend/services/cmv_snapshot_service.py`
- `backend/routes/cmv.py`
- `client/pages/admin/gestao/GestaoCmv.tsx`

Regras:

- CMV e analitico e nao altera cozinha, pedido, estoque ou StateMachine.
- DRE sem CMV aparece parcial.
- DRE com snapshots operacionais confiaveis aparece completa.

### 18.4 Financeiro

Arquivos principais:

- `backend/models/finance.py`
- `backend/schemas/finance.py`
- `backend/services/finance_service.py`
- `backend/routes/finance.py`
- `client/pages/admin/gestao/GestaoFinance.tsx`

Regras:

- Recebiveis por pagamento confirmado sao idempotentes.
- Estornos geram reversao financeira por `PaymentReversed`.
- Compras de estoque confirmadas podem gerar contas a pagar.
- O painel mostra caixa, competencia, DRE e relatorios por origem, categoria, centro de custo e canal.

### 18.5 Fiscal SEFAZ

Arquivos principais:

- `backend/models/fiscal.py`
- `backend/schemas/fiscal.py`
- `backend/services/fiscal_service.py`
- `backend/routes/fiscal.py`
- `client/pages/admin/gestao/GestaoFiscal.tsx`

Regras:

- Fiscal e interno/autossuficiente.
- Nao usar Saipos, Bling, Tiny, PlugNotas, TecnoSpeed ou middleware fiscal externo.
- Empresa fiscal, certificado, series e perfis tributarios sao administrados no ERP.
- Documentos fiscais guardam snapshot, XML interno, status e eventos.
- Transmissao/autorizacao real depende de certificado valido e integracao SEFAZ direta habilitada.
- O sistema nao simula autorizacao fiscal.

### 18.6 Validacao e operacao

Validacoes locais disponiveis neste host:

- `npm.cmd run typecheck`
- `npm.cmd run build`
- `npm.cmd test`
- `git diff --check`

Validacoes backend que devem ocorrer em ambiente com Python:

- `py -m py_compile ...`
- `alembic -c backend/alembic.ini heads`
- `alembic -c backend/alembic.ini upgrade head`

Ativacao em producao deve seguir a ordem documentada em `docs/gestao-operacao-fase-10.md`.

### 18.7 Deploy VPS validado em 2026-07-01

Commits relevantes:

- `7a3f6b0 feat(gestao): concluir modulos ERP`
- `01d9202 fix(gestao): ajustar abas internas dos modulos`

Fluxo executado na VPS:

- `git pull origin main`
- `pnpm install --frozen-lockfile`
- `pnpm run build`
- `python -m alembic -c backend/alembic.ini upgrade 20260630_gestao_fiscal_sefaz_base`
- `sudo systemctl restart moschettieri-api moschettieri-web`
- `curl -i http://127.0.0.1:8000/health`

Resultado validado:

- Build passou.
- Alembic ficou em `20260630_gestao_fiscal_sefaz_base (head)`.
- `moschettieri-api` ficou `active (running)`.
- `moschettieri-web` ficou `active (running)`.
- `/health` respondeu `200 OK` com `{"success":true,"data":{"status":"ok","version":"1.0.0"}}`.

Observacao operacional:

- Ajustes apenas de frontend, como abas internas e ortografia de `Gestão`, nao exigem Alembic nem restart da API. Para esses casos, usar `git pull origin main`, `pnpm run build` e `sudo systemctl restart moschettieri-web`.

## 19. Atualizacao 2026-07-03 - ASAAS Multi-Gateway

### 19.1 Escopo consolidado

O projeto passou a suportar multi-gateway no dominio existente `payments`, sem criar um segundo dominio de pagamentos. Mercado Pago permanece preservado como provider compativel para Pix/cartao e ASAAS entra como provider adicional para Pix.

Arquivos principais:

- `backend/services/payment_service.py`
- `backend/services/payment_gateway_resolver.py`
- `backend/services/asaas_client.py`
- `backend/services/asaas_gateway.py`
- `backend/routes/payments.py`
- `backend/routes/webhooks.py`
- `backend/models/payment.py`
- `backend/models/payment_config.py`
- `backend/models/customer.py`
- `client/lib/api.ts`
- `client/pages/Checkout.tsx`
- `client/pages/admin/AdminPagamentos.tsx`
- `client/pages/admin/Orders.tsx`
- `docs/ASAAS_MULTI_GATEWAY_EXECUTION_PLAN.md`

### 19.2 Modelo de dados

Novas/alteradas estruturas:

- `payment_gateway_configs`: credenciais por provider, status ativo/inativo, modo sandbox/producao e roteamento por modalidade.
- `payments.provider`: provider historico usado na cobranca.
- `payments.provider_payment_id`: id normalizado da cobranca no gateway.
- `payments.provider_status`: status bruto recebido do gateway.
- `payments.pix_qr_code`, `payments.pix_qr_code_base64`, `payments.pix_copy_paste`, `payments.checkout_url`, `payments.expires_at`: dados publicos de pagamento.
- `payments.cancelled_at`, `payments.cancellation_reason`, `payments.refunded_at`, `payments.refund_amount`, `payments.refund_reason`: operacao e pos-pagamento.
- `payment_events`: provider, event id, event type e payload para idempotencia e auditoria.
- `customers.provider_customer_id_asaas` e `customers.provider_customer_id_mercado_pago`: vinculo externo por gateway.

Migrations:

- `backend/migrations/versions/20260702_asaas_multi_gateway_config.py`
- `backend/migrations/versions/20260702_asaas_payment_generic_fields.py`
- `backend/migrations/versions/20260702_asaas_provider_customers.py`

### 19.3 Compatibilidade Mercado Pago

O fluxo Mercado Pago foi preservado. A configuracao inicial continua usando `PAYMENT_PROVIDER=mercado_pago`, webhooks Mercado Pago continuam em `/webhooks/mercadopago` e `/api/webhooks/mercadopago`, e o checkout de cartao segue pelo fluxo Mercado Pago atual.

Regra critica: operacoes administrativas de consulta, cancelamento e estorno usam `payments.provider`, nao o provider atualmente selecionado no painel. Isso evita operar uma cobranca antiga no gateway errado apos troca de configuracao.

### 19.4 ASAAS Pix

Fluxo ASAAS Pix:

1. Checkout consulta `/payments/config/public`.
2. Cliente cria pedido pelo fluxo atual.
3. `POST /payments/create` delega ao `PaymentService`.
4. `PaymentGatewayResolver` escolhe ASAAS quando Pix esta roteado para ASAAS.
5. `AsaasGateway` cria/reutiliza customer ASAAS e cria cobranca Pix.
6. QR Code/copia e cola sao persistidos em `payments`.
7. Checkout renderiza QR Code, codigo Pix e polling/status sem sair do dominio `payments`.
8. Webhook ASAAS ou conciliacao atualiza status final.

### 19.5 Cartao ASAAS seguro

Cartao ASAAS foi retomado em fases posteriores por decisao de negocio, usando fluxo dedicado no checkout da loja. O sistema continua proibido de persistir numero completo, CVV, validade completa, payload bruto `creditCard`, payload `creditCardHolderInfo` ou ultimos 4 digitos. A persistencia permitida fica limitada a metadados nao sensiveis, como provider, id externo, status, parcelas, bandeira e logo/identificador visual da bandeira.

### 19.6 Webhooks e idempotencia

Webhooks atuais:

- Mercado Pago: `/webhooks/mercadopago` e `/api/webhooks/mercadopago`.
- ASAAS: `/webhooks/asaas` e `/api/webhooks/asaas`.

Regras:

- ASAAS valida `asaas-access-token`, token diferente da API key.
- Evento externo e gravado em `payment_events`.
- Status final e confirmado por consulta ao gateway antes de aplicar mudanca interna.
- Eventos duplicados nao devem duplicar financeiro, estoque, WhatsApp ou BI.

### 19.7 Painel administrativo

`/painel/pagamentos` passa a administrar Mercado Pago e ASAAS:

- salva credenciais sem reexpor segredo salvo;
- permite escolher provider de Pix e cartao separadamente;
- mostra status de configuracao;
- exige ASAAS ativo, Cartao ASAAS ativo e API Key configurada para rotear cartao pelo ASAAS;
- preserva Mercado Pago Payment Brick quando o provider de cartao e Mercado Pago.

Em `client/pages/admin/Orders.tsx`, pedidos exibem provider e operacoes de conciliacao, cancelamento e estorno quando ha pagamento remoto associado.

### 19.8 Checkout

`client/pages/Checkout.tsx` consome apenas `client/lib/api.ts`. O checkout:

- preserva cartao Mercado Pago;
- preserva Pix Mercado Pago;
- renderiza Pix ASAAS quando configurado;
- renderiza cartao ASAAS na tela da loja quando configurado;
- trata provider indisponivel com mensagem funcional;
- mantem polling/status pelo endpoint oficial de pagamentos.

### 19.9 Validacao e operacao

Validacoes locais esperadas para esta entrega:

- `git diff --check`
- `npm.cmd run typecheck`
- `npm.cmd test`
- `npm.cmd run build`

Validacoes obrigatorias em ambiente com Python antes de producao:

- `alembic -c backend/alembic.ini heads`
- `alembic -c backend/alembic.ini current`
- `alembic -c backend/alembic.ini upgrade head`

Cenarios manuais recomendados:

- Pix Mercado Pago preservado.
- Pix ASAAS com CPF/CNPJ valido.
- Cartao Mercado Pago preservado.
- Cartao ASAAS com CPF/CNPJ, CEP e numero do titular.
- Webhook ASAAS com token valido/invalido.
- Duplicidade de webhook sem duplicar efeitos internos.
- Conciliacao/cancelamento/estorno por provider historico.

### 19.10 Riscos conhecidos

- `payments.order_id` unico limita multiplas tentativas reais por pedido.
- Segredos ficam em env/banco sem camada dedicada de criptografia.
- Valores monetarios ainda dependem de campos legados com `Float`.
- Webhook ASAAS processa regra sensivel e deve responder rapido.
- Ambientes sandbox/producao precisam ser separados com rigor.
- Cartao ASAAS exige HTTPS, sanitizacao de logs, idempotencia e conferencia real de webhook antes de operacao em producao.

## 20. Atualizacao 2026-07-03 - Cartao ASAAS na Tela Propria

### 20.1 Decisao

O objetivo do ASAAS foi ajustado: alem de Pix, ASAAS tambem deve processar cartao de credito para reduzir rejeicoes do Mercado Pago.

Decisao arquitetural: o cliente permanecera no checkout da loja. Nao usar redirecionamento para invoiceUrl ASAAS como solucao principal.

Documento de seguranca da fase: `docs/ASAAS_CREDIT_CARD_SECURITY_PHASE_12.md`.

### 20.2 Regra de armazenamento

Dados de cartao nunca podem ficar salvos no sistema.

Proibido salvar ou logar:

- numero completo do cartao;
- CVV/CCV;
- validade completa;
- payload `creditCard`;
- payload `creditCardHolderInfo`;
- payload bruto de requisicao ou resposta ASAAS com dados sensiveis;
- dados de cartao em localStorage, sessionStorage, cookies, analytics ou eventos internos.

Permitido nesta decisao:

- provider;
- id da cobranca;
- status;
- valor;
- parcelas;
- bandeira do cartao;
- identificador visual/logo da bandeira.

Nao salvar ultimos 4 digitos nesta etapa.

### 20.3 Mensagem ao cliente

O checkout deve exibir perto dos campos de cartao:

> Nao armazenamos os dados do seu cartao. Eles sao usados apenas para processar esta compra com seguranca.

### 20.4 Carteira do celular

O checkout pode usar atributos HTML de autocomplete para permitir preenchimento por cartoes salvos no navegador/celular:

- `cc-name`
- `cc-number`
- `cc-exp-month`
- `cc-exp-year`
- `cc-csc`

Isso nao significa salvar cartao na loja. Botao nativo Apple Pay/Google Pay fica fora do escopo ate confirmacao oficial de suporte.

### 20.5 Regras tecnicas para implementacao

- HTTPS obrigatorio.
- `remoteIp` deve ser o IP real do comprador.
- Timeout ASAAS de pelo menos 60 segundos.
- Idempotencia por pedido/pagamento para evitar dupla captura.
- Logs devem ser sanitizados.
- Erros ao cliente devem ser genericos e amigaveis.
- Mercado Pago permanece como fallback.
- Webhook ASAAS confirma status final e nao pode duplicar efeitos internos.

### 20.6 Proximas fases

- Fase 13: backend ASAAS cartao.
- Fase 14: checkout ASAAS cartao.
- Fase 15: admin, validacao e deploy.

## 21. Atualizacao 2026-07-03 - Backend ASAAS Cartao

### 21.1 Entrega

A Fase 13 implementou o backend para cartao ASAAS na tela propria, mantendo o dominio unico `payments`.

Arquivos principais:

- `backend/schemas/payment.py`
- `backend/routes/payments.py`
- `backend/services/payment_service.py`
- `backend/services/asaas_gateway.py`
- `backend/services/asaas_client.py`
- `backend/services/payment_gateway_resolver.py`
- `backend/models/payment.py`
- `backend/migrations/versions/20260703_asaas_card_metadata.py`

### 21.2 Contrato backend

Nova rota:

- `POST /payments/asaas/credit-card`

Entrada validada por `AsaasCreditCardPaymentCreate`, separada do `PaymentCreate` generico. O endpoint generico continua bloqueando dados brutos de cartao.

O backend calcula `remoteIp` a partir de `x-forwarded-for`, `x-real-ip` ou IP da conexao, sem confiar em campo enviado pelo cliente.

### 21.3 Persistencia permitida

Adicionados campos nao sensiveis:

- `payments.card_brand`
- `payments.card_brand_logo`

O sistema continua proibido de salvar numero completo, CVV, validade completa, payload bruto do cartao, payload do titular e ultimos 4 digitos.

### 21.4 Idempotencia e seguranca

- Pedido com pagamento ASAAS cartao pendente e `provider_payment_id` retorna a mesma tentativa.
- `AsaasClient` usa timeout padrao de 60 segundos.
- `sanitize_asaas_payload` mascara cartao, titular, CVV, numero, tokens e chaves.
- Mercado Pago permanece como fallback.

### 21.5 Proxima etapa

Fase 14 executada em `client/pages/Checkout.tsx` e `client/lib/api.ts`: chamada ao novo endpoint, autocomplete do celular, mensagem de nao armazenamento e limpeza de estado sensivel apos a tentativa.

## 22. Atualizacao 2026-07-04 - Checkout ASAAS Cartao

### 22.1 Entrega

A Fase 14 ligou o checkout ao backend ASAAS cartao, mantendo o cliente na tela da loja.

Arquivos principais:

- `client/lib/api.ts`
- `client/pages/Checkout.tsx`
- `docs/ASAAS_MULTI_GATEWAY_EXECUTION_PLAN.md`

### 22.2 Fluxo

Quando `GET /payments/config/public` indicar `credit_card.provider="asaas"` e `implementation_status="available"`, o checkout:

1. Mantem o formulario de cartao na loja.
2. Exige CPF/CNPJ, CEP e numero de endereco do titular.
3. Envia a tentativa para `POST /payments/asaas/credit-card`.
4. Limpa numero, nome, validade, CVV e CPF/CNPJ do estado apos tentativa real.
5. Exibe pagamento pendente ou recusado conforme resposta.

Mercado Pago continua preservado quando o provider de cartao e Mercado Pago.

### 22.3 Seguranca

- Campos usam autocomplete do navegador/celular.
- A mensagem "Nao armazenamos os dados do seu cartao..." aparece no fluxo ASAAS.
- O frontend nao salva cartao em storage.
- O backend continua responsavel por sanitizacao, idempotencia e webhook.

### 22.4 Proxima etapa

Fase 15 deve concluir o painel administrativo e a validacao local. Alembic em ambiente Python, deploy e teste real de webhook ASAAS cartao seguem como etapa operacional de VPS.

## 23. Atualizacao 2026-07-04 - Admin ASAAS Cartao

### 23.1 Entrega

A Fase 15 alinhou o painel `/painel/pagamentos` com o fluxo ASAAS cartao implementado no backend e no checkout.

Arquivo principal:

- `client/pages/admin/AdminPagamentos.tsx`

### 23.2 Comportamento do painel

- ASAAS cartao nao e mais bloqueado por uma trava antiga de tokenizacao client-side.
- O admin pode ligar `Cartao ASAAS`.
- O roteamento de cartao para ASAAS fica selecionavel quando ASAAS esta ativo, `Cartao ASAAS` esta ativo e existe API Key salva ou sendo informada.
- O campo visual foi renomeado para `Status operacional do cartao`, preservando `asaas_tokenization_status` no contrato para compatibilidade.
- O painel informa que dados de cartao sao usados apenas para processar a compra e nao ficam salvos no sistema.

### 23.3 Compatibilidade

- Mercado Pago Payment Brick permanece preservado quando `credit_card_provider` e `mercado_pago`.
- Pix Mercado Pago e Pix ASAAS continuam no mesmo dominio `payments`.
- Nao foi criado segundo dominio de pagamentos.
- Sem fallback automatico em runtime: o checkout usa o provider configurado.

### 23.4 Operacao pendente

Antes de producao, executar em ambiente com Python/Alembic:

- `alembic -c backend/alembic.ini heads`
- `alembic -c backend/alembic.ini current`
- `alembic -c backend/alembic.ini upgrade head`

Tambem testar pagamento ASAAS cartao e webhook real, confirmando idempotencia e ausencia de dados sensiveis nos logs.

## 24. Atualizacao 2026-07-04 - Alerta de Atendimento Humano no Agente WhatsApp

### 24.1 Entrega

Foi implementado alerta operacional para quando o cliente pedir atendimento humano, fizer reclamacao ou o Agente WhatsApp classificar a conversa como `waiting_human`.

Commit publicado:

- `9cbaa67 feat(whatsapp): alertar atendimento humano`

Arquivos principais:

- `backend/services/agente_whatsapp_outbox_service.py`
- `client/components/admin/AdminTopActions.tsx`
- `client/pages/admin/crm/CrmAgenteWhatsApp.tsx`

### 24.2 Decisao arquitetural

A solucao reutiliza o modulo nativo `Agente WhatsApp` e a tabela existente `agente_whatsapp_internal_alerts`.

Nao foi criada nova tabela, migration, endpoint paralelo ou sistema separado de atendimento.

Persistencia existente:

- Model: `backend/models/agente_whatsapp.py` (`AgenteWhatsAppInternalAlert`)
- Schema: `backend/schemas/agente_whatsapp.py` (`AgenteWhatsAppInternalAlertOut`)
- Migration original: `backend/migrations/versions/20260514_agente_whatsapp_internal_alerts.py`

O alerta e tratado como um tipo novo de alerta interno:

- `alert_type`: `human_handoff`
- `level`: `critical`
- `dedupe_key`: `agente_whatsapp:human_handoff:{session_id}`

### 24.3 Fluxo backend

`AgenteWhatsAppOutboxService.sync_internal_alerts()` agora inclui sessoes com:

- `AgenteWhatsAppSession.status == "waiting_human"`

Para cada sessao elegivel, o backend busca a ultima mensagem inbound e cria/atualiza um alerta interno com payload:

- `session_id`
- `phone`
- `customer_id`
- `customer_name`
- `current_intent`
- `last_message_id`
- `last_message`
- `last_message_at`
- `ai_enabled`
- `automation_blocked`

O alerta permanece ativo enquanto a sessao estiver em `waiting_human`. Quando a sessao deixa esse estado, a sincronizacao existente resolve o alerta por ausencia da chave desejada.

### 24.4 Fluxo global do painel

`AdminTopActions.tsx` continua buscando:

- `agenteWhatsAppApi.listInternalAlerts({ status: "active", limit: 10 })`

Quando recebe `human_handoff`, o painel:

- mostra o alerta no sino global;
- mostra popup fixo no canto inferior direito;
- usa a ultima mensagem como descricao quando disponivel;
- navega para `/painel/crm/agente-whatsapp?session={session_id}`.

Regra importante:

- Abrir um alerta `human_handoff` pelo sino global nao faz `ack` automatico.
- Isso evita esconder o alerta antes de alguem realmente assumir ou tratar a conversa.
- Alertas internos de outros tipos continuam podendo ser reconhecidos pelo fluxo normal.

### 24.5 Fluxo na tela CRM / Agente WhatsApp

`CrmAgenteWhatsApp.tsx` passou a:

- carregar alertas internos ativos;
- filtrar alertas `human_handoff`;
- destacar "Atendimento humano pendente" acima das metricas;
- exibir ate 3 conversas pendentes no destaque;
- mostrar popup local "Cliente chamando humano";
- aceitar deep link por query param `?session=...`;
- abrir conversa especifica a partir do alerta;
- permitir assumir a conversa pelo botao `Assumir`.

Ao assumir pelo alerta, o frontend:

1. atualiza a sessao para `status: "human"`;
2. desativa IA com `ai_enabled: false`;
3. tenta reconhecer o alerta interno;
4. recarrega as sessoes mantendo a conversa selecionada.

### 24.6 Contratos e endpoints reutilizados

Sem contrato novo.

Endpoints existentes reutilizados:

- `GET /agente-whatsapp/outbox/internal-alerts`
- `POST /agente-whatsapp/outbox/internal-alerts/{alert_id}/ack`
- `PATCH /agente-whatsapp/sessions/{session_id}`
- `GET /agente-whatsapp/sessions/{session_id}`

API frontend reutilizada via `client/lib/api.ts`:

- `agenteWhatsAppApi.listInternalAlerts`
- `agenteWhatsAppApi.acknowledgeInternalAlert`
- `agenteWhatsAppApi.updateSession`
- `agenteWhatsAppApi.getSession`

### 24.7 Criterios de funcionamento

O alerta deve aparecer quando:

- a IA/guardrails ou o gerente do Agente WhatsApp colocarem a sessao em `waiting_human`;
- existir reclamacao, risco de qualidade, pedido de atendente, pedido de gerente ou necessidade de revisao humana ja coberta pelo fluxo de IA.

O alerta deve deixar de aparecer quando:

- a sessao for assumida como `human`;
- a sessao for encerrada;
- a sessao voltar para `open`/IA;
- a sincronizacao de alertas internos resolver a chave `human_handoff` por nao existir mais sessao `waiting_human`.

### 24.8 Validacao executada

Validacoes locais da entrega:

- `npm.cmd run typecheck`: passou.
- `npm.cmd run build`: passou.
- `npm.cmd test`: passou com 7 arquivos e 33 testes.

Limitacao local:

- Validacao Python nao executada porque este Windows nao possui runtime Python instalado (`python` nao existe no PATH e `py` retorna `No installed Python found!`).

### 24.9 Operacao e cuidados

- Nao usar `git add -A` em publish desta trilha; o worktree pode conter ruido local em `.claude/*`.
- O popup global usa polling do sino do admin, atualmente a cada 30 segundos.
- O alerta de atendimento humano e operacional, nao promocional; nao deve ser misturado com notificacoes de prova social da loja.
- A regra de negocio continua no backend/service; o frontend apenas exibe, abre e assume conversas via API oficial.

## 25. Atualizacao 2026-07-21 - Estado Atual Consolidado de Marketing e Notificacoes

### 25.1 Precedencia e escopo

Esta secao registra o estado comprovado do repositorio apos a secao 24 e prevalece sobre inventarios anteriores quando houver divergencia. As secoes antigas permanecem como historico.

Escopo confirmado: navegacao ausente da secao 17, listas padronizadas de contatos, vinculo com campanhas, validacao bloqueante de destinatarios, importacao de compradores para prova social e correcao da sincronizacao do Agente WhatsApp.

Commits de referencia: `4cf9101`, `e8d39ec`, `be18815`, `08d8022`, `5b4409e` e `0c99d13`.

### 25.2 Inventario atual de navegacao

`client/App.tsx` seleciona a experiencia publica por `PublicHome`/`ExperienceRoute`, preservando a loja delivery e adicionando a experiencia do salao.

Rotas publicas do salao confirmadas: `/menu`, `/blog`, `/sobre`, `/galeria`, `/pessoas`, `/certificados`, `/duvidas`, `/reservas`, `/contato`, `/login-cadastro` e `/minha-conta`.

Rotas administrativas que complementam a secao 17.5: `/painel/bi-mobile`, `/painel/whatsapp-gateway`, `/painel/salao`, `/painel/salao/pagina`, `/painel/crm/agente-whatsapp`, `/painel/gestao/estoque`, `/painel/gestao/cmv`, `/painel/gestao/financeiro` e `/painel/gestao/fiscal`.

A rota antiga `/painel/marketing/campanhas`, citada na secao 17.5, nao existe no roteador atual e nao deve ser usada como referencia operacional. As telas continuam lazy, protegidas por `AdminGuard`/`AdminLayout` e integradas por `client/lib/api.ts`.

### 25.3 Listas padronizadas de contatos

WhatsApp e Email possuem listas persistentes administradas pelos modulos de marketing.

- WhatsApp: CRUD `/whatsapp/contact-lists` em `backend/routes/whatsapp_marketing.py`.
- Email: CRUD `/email/contact-lists` em `backend/routes/email_marketing.py`.
- Os routers tambem sao expostos sob o prefixo global `/api` por `backend/main.py`.
- `client/components/admin/ContactListImportBox.tsx` importa o modelo `nome,whatsapp,email` por CSV/TXT, com virgula ou ponto e virgula.
- `MarketingWhatsApp.tsx` e `MarketingEmail.tsx` permitem criar, selecionar e excluir listas.
- Chamadas HTTP permanecem centralizadas em `client/lib/api.ts`.

### 25.4 Campanhas e validacao obrigatoria antes do envio

Campanhas WhatsApp e Email aceitam `contact_list_id`. O relacionamento e opcional; quando a lista e excluida, a FK usa `ON DELETE SET NULL`.

No envio, o backend resolve e deduplica destinatarios de lista, grupo, clientes explicitos e entradas diretas.

- WhatsApp normaliza o telefone, valida o formato internacional e consulta a existencia da conta pelo WhatsApp Gateway conectado.
- Email normaliza e valida a sintaxe com `email-validator`, depois exige dominio entregavel por DNS `MX`, `A` ou `AAAA`.
- Destinatarios invalidos recebem falha registrada e nao seguem para o provider.
- A validacao esta no backend dos endpoints de disparo, nao apenas na interface.

### 25.5 Persistencia e migrations das listas

- `whatsapp_contact_lists` e `whatsapp_contact_list_items`: `20260508_whatsapp_contact_lists.py`.
- `email_contact_lists` e `email_contact_list_items`: `20260704_email_contact_lists.py`.
- `whatsapp_campaigns.contact_list_id` e `email_campaigns.contact_list_id`: `20260704_campaign_contact_lists.py`.

A revisao Alembic mais recente desta trilha e `20260704_campaign_contact_lists`, dependente de `20260704_email_contact_lists`. Antes de aplicar em ambiente real, conferir `heads` e `current`; nao alterar o banco manualmente.

### 25.6 Importacao de compradores para prova social

O admin de notificacoes aceita `.csv` ou `.xlsx` em `POST /store-notifications/import`. `backend/routes/store_notifications.py` recebe `UploadFile` e delega a `StoreNotificationService.import_notifications_file()`.

Regras comprovadas:

- no maximo 1000 linhas;
- CSV em UTF-8/Latin-1, separado por virgula ou ponto e virgula, e XLSX lido com `openpyxl`;
- cada linha e validada individualmente; o retorno informa criados, ignorados, erros por linha e notificacoes criadas;
- nome e bairro sao obrigatorios, e somente o primeiro nome e exibido;
- produto pode ser localizado por ID ou nome; quando ausente, o service seleciona produto ativo e visivel, com fallbacks controlados;
- minutos ausentes sao sorteados entre 8 e 45; quando informados, devem ficar entre 1 e 1440;
- registros importados ficam manuais e ativos, todos os dias, das 18:00 as 23:30, com exibicao de 7 segundos.

`client/lib/api.ts` envia `FormData` por `storeNotificationsApi.importFile`. `MarketingStoreNotifications.tsx` trata selecao, loading, resultado parcial e recarregamento. O modelo publico e `public/templates/compradores-notificacoes-modelo.csv`.

A importacao reutiliza `StoreNotification` e `Product`; nao criou tabela ou migration. Ela difere da captura real: `list_captured()` sincroniza pedidos reativamente por `_sync_captured_from_orders()`, em janela atual de 30 dias, considerando pagos, ignorando cancelados/reembolsados e evitando duplicacao por `order_id`.

### 25.7 Correcao da sincronizacao do disparador WhatsApp

O commit `0c99d13` corrigiu o caminho idempotente de `AgenteWhatsAppService.add_message()` em `backend/services/agente_whatsapp_service.py`.

Atualizacao de metadados, enfileiramento inbound e retorno antecipado agora ocorrem somente quando uma mensagem existente foi encontrada. Quando `provider_message_id` e novo, o fluxo continua para criar a mensagem e preservar os vinculos `campaign_id` e `campaign_delivery_id`.

Essa correcao nao alterou contrato de API, schema de banco ou migration.

### 25.8 Arquitetura e cuidados operacionais

- O frontend continua sem `fetch` direto nestes fluxos; as integracoes passam por `client/lib/api.ts`.
- A importacao preserva o dominio existente de notificacoes da loja.
- As listas reutilizam os modulos atuais de WhatsApp/Email Marketing e campanhas; nao foi criado subsistema paralelo.
- `whatsapp_marketing.py` e `email_marketing.py` ainda concentram models, schemas e regras legadas. Isso descreve o estado atual e nao autoriza ampliar esse padrao.
- Mudancas locais em `.claude/*` e worktrees de agentes nao fazem parte desta atualizacao.

### 25.9 Validacao desta atualizacao

- conferir o diff exclusivamente de `KNOWLEDGE_BASE.md`;
- executar `git diff --check -- KNOWLEDGE_BASE.md`;
- conferir cabecalho, indice e hierarquia da secao 25;
- executar `npm.cmd run typecheck`, `npm.cmd test` e `npm.cmd run build`;
- validar Alembic somente em ambiente com Python instalado, registrando a revisao real antes de qualquer `upgrade`.

## 26. Atualizacao 2026-07-21 - Preparacao Multiempresa em Codigo

### 26.1 Precedencia e estado real

Esta secao registra somente o estado comprovado no codigo e nos documentos `docs/SAAS_MULTI_TENANT*.md` desta execucao. Ela complementa e preserva a secao 25.

O repositorio possui uma preparacao multiempresa aditiva e progressiva, mas ainda nao deve ser tratado como implantado ou integralmente isolado. As migrations foram criadas e o runtime possui slices protegidos por flags; nenhuma migration multiempresa foi aplicada neste ambiente e nao houve validacao com Python, Alembic, PostgreSQL ou VPS.

O tenant de compatibilidade definido pelas migrations e `tenant-legacy-default`. O rotulo historico `default` nao e autoridade de isolamento e aparece apenas como dado legado a ser normalizado pelos backfills controlados.

### 26.2 Fundacao, identidade e selecao de tenant

A fundacao adicionada inclui:

- `tenants` e `tenant_memberships`;
- papeis, permissoes e vinculos explicitos da plataforma;
- auditoria append-only da plataforma;
- `TenantContext` imutavel e fail-closed;
- `TenantService` para tenant ativo, membership, selecao autorizada e soft delete;
- seed idempotente do tenant legado, memberships e papeis iniciais.

Com `MULTI_TENANT_AUTH_ENABLED=false`, login e JWT preservam o caminho legado e nao dependem das novas tabelas. Com a flag ativa, o painel resolve o tenant pelo JWT e por membership ativa; a selecao usa `GET /admin/auth/tenants` e `POST /admin/auth/select-tenant`, sem aceitar `tenant_id` livre como autoridade. O frontend possui seletor integrado ao shell administrativo via `client/lib/api.ts`, exibido somente com `VITE_MULTI_TENANT_AUTH_ENABLED=true` e quando houver mais de uma membership.

### 26.3 Dominios publicos e contexto confiavel

O dominio principal permanece reservado ao login, painel e operacao master. Subdominios e dominios customizados representam somente a experiencia publica do tenant.

`TENANT_DOMAINS_ENABLED=false` preserva o comportamento atual. Quando ativado, hostname desconhecido falha fechado e nao cai no tenant legado. `X-Forwarded-Host` somente pode ser considerado com `TENANT_DOMAINS_TRUST_PROXY_HEADERS=true` e origem contida em `TENANT_DOMAINS_TRUSTED_PROXY_IPS`; hostnames do painel ficam em `TENANT_DOMAINS_PLATFORM_HOSTNAMES`.

O ciclo de dominio implementado e `pending -> verified -> active`, com prova persistida por hash. A resolucao publica exige dominio ativo e tenant ativo nao removido.

### 26.4 Ondas de dados preparadas

A cadeia multiempresa foi organizada por `expand/backfill/contract`:

1. fundacao, seed legado e dominios;
2. identidade/RBAC operacional e catalogo;
3. clientes e pedidos;
4. pagamentos de pedidos e webhooks;
5. operacao, frete, entrega e salao;
6. marketing, CRM, WhatsApp, trafego e BI;
7. estoque, CMV, financeiro, fiscal, cache com dados e processamento assincrono;
8. contracts separados por onda.

Os expands adicionam ownership nullable e constraints tenant-scoped sem remover contratos globais legados. Os backfills exigem o tenant legado, fazem preflights de duplicidade/ownership e nao sobrescrevem ownership valido. Os contracts abortam diante de `tenant_id` nulo, `default`, orfao ou tenant removido; somente depois validam FKs preparadas, removem defaults e aplicam `NOT NULL`. Uniques globais legadas nao sao removidas automaticamente.

O inventario estatico documentado encontrou 109 revisoes, sem IDs duplicados ou pais ausentes, e um unico head de arquivos: `20260810_tenant_backoffice_contract`. Isso nao comprova o estado de `alembic_version` de qualquer banco fisico.

### 26.5 Runtime e flags de ativacao

Todas as flags abaixo permanecem `false` por padrao:

- `MULTI_TENANT_AUTH_ENABLED`;
- `TENANT_IDENTITY_CATALOG_ENFORCEMENT_ENABLED`;
- `TENANT_CUSTOMERS_ORDERS_ENFORCEMENT_ENABLED`;
- `TENANT_OPERATIONS_ENFORCEMENT_ENABLED`;
- `MULTI_TENANT_WAVE6_ORM_ENABLED`;
- `MULTI_TENANT_WAVE7_ORM_ENABLED`;
- `TENANT_DOMAINS_ENABLED`;
- `TENANT_PAYMENT_WEBHOOKS_ENABLED`;
- `TENANT_BACKGROUND_CONTEXT_ENABLED`;
- `TENANT_UPLOAD_NAMESPACE_ENABLED`;
- `TENANT_CREDENTIALS_ENABLED`.

Ha enforcement runtime comprovado em slices centrais de catalogo, clientes e pedidos, sempre dependente de contexto confiavel e das flags correspondentes. Com as flags desligadas, o caminho global legado e preservado. Ativar enforcement sem migration, backfill, contexto resolvido e teste A/B e proibido, pois deve falhar fechado e pode interromper fluxos ainda nao migrados.

Webhooks multiempresa de Mercado Pago e ASAAS usam chave opaca de endpoint mapeada no servidor por `TENANT_PAYMENT_WEBHOOK_ENDPOINTS`; host, header de proxy, body, query, `default` ou tentativa sequencial de credenciais nao sao autoridade. Com `TENANT_PAYMENT_WEBHOOKS_ENABLED=true`, os endpoints globais ficam indisponiveis e o processamento exige tenant/configuracao inequivocos. Stripe e PagSeguro continuam fora deste contrato tenantizado.

### 26.6 Lacunas que ainda bloqueiam segundo tenant

O schema preparado nao equivale a isolamento integral. Permanecem como gates:

- migrar e comprovar todos os readers/writers, buscas por ID e relacoes parent/child dos slices ainda apenas preparados no ORM;
- eliminar usos operacionais de `tenant_id="default"` e construtores com fallback legado antes da ativacao;
- concluir propagacao de tenant em jobs, outbox, caches e qualquer processamento sem contexto HTTP;
- separar, proteger e rotacionar credenciais por tenant;
- concluir namespace e autorizacao de uploads; os arquivos atuais ainda exigem cuidado por historicamente usarem diretorio/URL globais;
- manter billing SaaS separado dos pagamentos de pedidos;
- executar preflights fisicos, testar rollback e confirmar ownership/constraints no PostgreSQL real;
- realizar canario A/B com pelo menos dois tenants antes de remover uniques/FKs globais ou liberar operacao multiempresa.

DDL de startup e Alembic continuam exigindo revisao operacional para que o instalador futuro tenha uma unica autoridade de schema e nao concorra em deploys paralelos.

### 26.7 Validacao e operacao futura

Foram comprovados nesta trilha: inventario estatico do codigo, reconciliacao documentada das ondas/models/constraints, revisao estatica da cadeia de revisions, testes unitarios adicionados para helpers de tenant e verificacoes locais de integridade de diff. As validacoes Node registradas durante a execucao passaram em `npm.cmd run typecheck`, `npm.cmd test` e `npm.cmd run build`.

Nao foram executados neste ambiente:

- import, compile ou testes Python;
- `alembic heads/current/history` contra runtime Python;
- upgrade, downgrade, backfill ou contract;
- queries, contagens, locks, planos ou `VALIDATE CONSTRAINT` no PostgreSQL;
- deploy, restart, smoke test ou rollback em VPS.

O futuro metodo de instalacao para VPS deve registrar o estado real do banco antes de qualquer alteracao, aplicar cada onda na ordem, parar em qualquer preflight, preservar backup restauravel e ativar flags somente depois dos testes correspondentes. Nao usar `stamp`, nao editar migrations para contornar dados invalidos e nao aplicar `upgrade head` sem confirmar `heads`, `current`, historico e janela de rollback.

### 26.8 Fase runtime operacoes - frete e salao

A proxima fase executada apos a preparacao geral fechou uma fatia de runtime da onda de operacoes, ainda com flags desligadas por padrao.

Arquivos principais alterados:

- `backend/services/shipping_service.py`;
- `backend/routes/shipping.py`;
- `backend/services/salao_service.py`;
- `backend/routes/salao.py`.

O `ShippingService` passou a aceitar `TenantContext` opcional e a usar helpers centrais de ownership quando `TENANT_OPERATIONS_ENFORCEMENT_ENABLED=true`. Consultas, criacoes e lookups por ID de configuracao de frete, bairros, CEPs, regras por distancia, faixas por valor, promocoes, regras extras e endpoints legados de zonas/regras ficam tenant-scoped somente com a flag ativa. Com a flag desligada, o fluxo legado global e preservado.

As rotas administrativas de frete resolvem tenant pelo painel, e `POST /shipping/calculate` resolve tenant publico pelo dominio quando `TENANT_DOMAINS_ENABLED=true`.

O runtime do salao passou a aplicar o mesmo padrao em mesas, reservas, comandas e itens de comanda. As rotas administrativas de `/salao/*` passam contexto do painel para os services, a reserva publica resolve contexto por dominio e a criacao/confirmacao de pedido a partir da comanda repassa o tenant ao `OrderService`.

Gates ainda abertos nesta fatia:

- `freight_type_configs.freight_type` ainda possui unique global no model/schema legado; ativacao multiempresa de tipos de frete depende do contract validado no PostgreSQL real;
- entrega/logistica, store operation, estoque, financeiro, fiscal, jobs/outbox/cache e notificacoes publicas ainda precisam de fechamento runtime equivalente;
- Python, Alembic e PostgreSQL continuam sem validacao local.

Validacao executada nesta fase:

- `git diff --check -- backend/services/shipping_service.py backend/routes/shipping.py backend/services/salao_service.py backend/routes/salao.py`;
- `npm.cmd run typecheck`;
- `npm.cmd test`;
- `npm.cmd run build`.

### 26.9 Fase runtime sem contexto HTTP - Agente WhatsApp e prova social

Esta fase fechou dois gaps pontuais que ainda usavam services operacionais sem contexto confiavel quando as flags multiempresa fossem ativadas.

Arquivos principais alterados:

- `backend/services/agente_whatsapp_tools.py`;
- `backend/services/store_notification_service.py`;
- `backend/routes/store_notifications.py`;
- `backend/core/tenant_runtime.py`.

No Agente WhatsApp, `AgenteWhatsAppToolService._resolve_context()` agora deriva `TenantContext` a partir de `AgenteWhatsAppSession.tenant_id` quando a ferramenta e executada com `session_id`. Esse contexto e usado em:

- `calcular_frete`, via `ShippingService`;
- `validar_item_pedido`, `simular_checkout` e `criar_pedido`, via `OrderService`;
- consulta/criacao de pagamento, via `PaymentService(tenant_id=...)`;
- auditoria de tool calls e eventos, preenchendo `tenant_id` quando disponivel.

Sem `session_id` ou sem `tenant_id` na sessao, o fluxo preserva comportamento legado enquanto as flags estao desligadas. Com enforcement ativo, services tenantizados devem falhar fechado se o contexto obrigatorio nao existir.

Na prova social da loja, `StoreNotificationService` passou a aceitar `TenantContext` opcional. O uso nesta fase e limitado a consultar `StoreOperationService` com o tenant correto quando `only_during_store_hours=true`. A rota publica `/store-notifications/next` usa a dependencia publica de operacoes e falha fechado quando `TENANT_OPERATIONS_ENFORCEMENT_ENABLED=true` sem tenant confiavel. As rotas administrativas resolvem tenant pelo painel.

`resolve_public_tenant_context()` tambem passou a preencher `hostname` ao construir `TenantContext` publico, preservando o contrato fail-closed do contexto por dominio.

Limitacao importante: as tabelas de prova social (`store_notification_settings`, `store_notifications`, `store_notification_days`, `store_notification_impressions`, `store_notification_captured`) ainda nao possuem `tenant_id` no model atual. Portanto esta fase corrige a dependencia operacional de horario por tenant, mas nao declara isolamento completo das notificacoes de prova social. A tenantizacao completa dessas tabelas permanece como fase de schema/runtime posterior.

Validacao executada nesta fase:

- `git diff --check -- backend/services/agente_whatsapp_tools.py backend/services/store_notification_service.py backend/routes/store_notifications.py backend/core/tenant_runtime.py KNOWLEDGE_BASE.md`;
- `npm.cmd run typecheck`;
- `npm.cmd test`;
- `npm.cmd run build`.

### 26.10 Fase schema/runtime - tenantizacao da prova social

Esta fase completou a tenantizacao aditiva das tabelas de prova social/notificacoes da loja, sem ativar flags por padrao e sem contract fisico.

Arquivos principais alterados:

- `backend/models/store_notification.py`;
- `backend/core/wave6_tenant_orm.py`;
- `backend/routes/store_notifications.py`;
- `backend/services/store_notification_service.py`;
- `backend/migrations/versions/20260811_tenant_store_notifications_expand.py`;
- `KNOWLEDGE_BASE.md`.

As tabelas `store_notification_settings`, `store_notifications`, `store_notification_days`, `store_notification_impressions` e `store_notification_captured` agora possuem ownership `tenant_id` no ORM por meio do helper da onda 6. A migration `20260811_tenant_store_notifications_expand` adiciona a coluna nullable, FK para `tenants`, indices tenant-scoped e backfill para `tenant-legacy-default`.

O `StoreNotificationService` passou a escopar leituras, contagens, candidatos publicos, impressões, capturas, duplicacao, importacao e lookups por produto/endereco quando `MULTI_TENANT_WAVE6_ORM_ENABLED=true`. Novos registros recebem `tenant_id` pelo `TenantContext` confiavel; com a flag desligada, o comportamento legado global permanece.

Com a Wave 6 ativa, o ID singleton de settings e a consulta de horario de funcionamento usam o tenant do proprio `TenantContext`, evitando depender do flag de operacoes.

Gates ainda abertos:

- a migration ainda nao foi aplicada em PostgreSQL real;
- nao houve `VALIDATE CONSTRAINT`, `NOT NULL` ou contract para estas cinco tabelas;
- a ativacao real depende de `TENANT_DOMAINS_ENABLED=true` e contexto publico/admin confiavel;
- a unique global legada de `store_notification_captured.order_id` permanece ate validacao fisica do banco.

Validacao executada nesta fase:

- `git diff --check -- backend/models/store_notification.py backend/services/store_notification_service.py backend/core/wave6_tenant_orm.py backend/routes/store_notifications.py backend/migrations/versions/20260811_tenant_store_notifications_expand.py KNOWLEDGE_BASE.md`;
- `npm.cmd run typecheck`;
- `npm.cmd test`;
- `npm.cmd run build`;
- Python, Alembic e PostgreSQL somente na futura fase VPS/staging.

### 26.11 Metodo de instalacao Telz VPS por fases

Esta fase validou o prompt mestre Telz contra o estado comprovado do projeto e criou um metodo operacional faseado para instalacao/validacao em VPS.

Arquivo principal:

- `docs/TELZ_VPS_INSTALL_PHASED_METHOD.md`.

Conclusao da validacao: o prompt e coerente como direcao de transformacao SaaS multiempresa, mas nao deve ser executado como big-bang. O metodo aceito para este repositorio e instalar primeiro em modo legado compativel, com flags multiempresa desligadas, validar PostgreSQL/Alembic/Nginx/systemd/build/health check no sistema instalado e somente depois ativar isolamento por ondas.

O metodo documentado define:

- preflight e inventario da VPS antes de qualquer alteracao;
- instalador interativo futuro via `installer/install.sh`, com perguntas por fase, validacao de entradas, confirmacao final, logs mascarados e retomada por `--resume`;
- preparacao de sistema operacional, usuario, diretorios e codigo;
- `.env` operacional Telz com flags multi-tenant desligadas por padrao;
- validacao Alembic com `heads`, `current` e historico antes de `upgrade head`;
- build e testes frontend/backend proporcionais ao ambiente;
- modelos de `systemd` para `telz-api` e `telz-web`;
- Nginx/SSL para dominio principal;
- backup/restore antes das ondas multi-tenant;
- idempotencia obrigatoria para usuario, diretorio, banco, `.env`, Nginx, systemd, cron, certificados, uploads e backups;
- atualizacao futura por `scripts/update-telz.sh`, com lock, backup, typecheck, testes, build, migrations e rollback somente de codigo/build/Nginx/systemd;
- CLI administrativa futura `telz-cli` apenas como wrapper seguro, sem execucao arbitraria de shell;
- smoke test legado antes de qualquer ativacao;
- validacao multi-tenant posterior em staging/VPS;
- contract/hardening somente depois de telemetria e dados consistentes.

Pontos de compatibilidade preservados:

- `DEPLOY.md` legado nao foi substituido;
- nenhuma migration foi executada localmente;
- nenhum script destrutivo foi criado;
- nenhum `.env` foi sobrescrito;
- `curl -fsSL https://install.telz.com.br | sudo bash` permanece apenas como alvo futuro, nao como forma oficial atual;
- a troca operacional para Telz ficou documentada como alvo de instalacao, nao como renomeacao ampla imediata de tabelas, classes ou migrations antigas.

Gates ainda abertos:

- decidir dominio principal, IP, usuario e path final da VPS;
- criar scripts reais do instalador depois dessas decisoes;
- aplicar e validar migrations em PostgreSQL real;
- executar smoke tests no sistema instalado;
- ativar flags multiempresa somente por ondas controladas.

Validacao executada nesta fase:

- revisao do prompt anexado;
- comparacao com `DEPLOY.md`, `package.json`, `backend/.env.example`, scripts atuais, migrations e secoes recentes da base de conhecimento;
- `git diff --check -- docs/TELZ_VPS_INSTALL_PHASED_METHOD.md KNOWLEDGE_BASE.md`.

### 26.12 Especificacao do instalador interativo Telz

O prompt complementar do instalador interativo foi incorporado em `docs/TELZ_VPS_INSTALL_PHASED_METHOD.md` como especificacao da futura fase de automacao. Ele melhora o metodo anterior por definir instalacao assistida, validacao de respostas, confirmacao final, modo nao interativo, retomada por fase, logs mascarados, idempotencia, scripts de update/backup/restore, CLI administrativa e regras explicitas de rollback.

A incorporacao preserva os gates ja definidos:

- primeiro validar o procedimento manual em VPS real ou ambiente descartavel;
- nao publicar `curl | bash` antes de hospedagem segura e versionada;
- nao expor segredos em logs;
- nao sobrescrever `.env`, banco, uploads, certificados ou backups sem confirmacao explicita;
- nao fazer downgrade Alembic automatico;
- manter flags multi-tenant desligadas na instalacao inicial.

Arquivos atualizados:

- `docs/TELZ_VPS_INSTALL_PHASED_METHOD.md`;
- `KNOWLEDGE_BASE.md`.

Validacao executada nesta fase:

- `git diff --check -- docs/TELZ_VPS_INSTALL_PHASED_METHOD.md KNOWLEDGE_BASE.md`.

### 26.13 Instalador modular Telz - primeira versao executavel

Foi criada a primeira versao executavel do instalador modular da Telz, sem executar instalacao local e sem acionar VPS. O instalador fica em `installer/install.sh`, carrega defaults de `installer/config/defaults.env`, usa modulos em `installer/lib/` e templates em `installer/templates/`.

Arquivos principais criados:

- `installer/install.sh`;
- `installer/lib/colors.sh`;
- `installer/lib/prompts.sh`;
- `installer/lib/validation.sh`;
- `installer/lib/system.sh`;
- `installer/lib/git.sh`;
- `installer/lib/database.sh`;
- `installer/lib/backend.sh`;
- `installer/lib/frontend.sh`;
- `installer/lib/nginx.sh`;
- `installer/lib/ssl.sh`;
- `installer/lib/systemd.sh`;
- `installer/lib/backup.sh`;
- `installer/lib/firewall.sh`;
- `installer/lib/summary.sh`;
- `installer/templates/telz-api.service`;
- `installer/templates/telz-web.service`;
- `installer/templates/nginx-telz.conf`;
- `installer/templates/env.production.example`;
- `scripts/health-check.sh`;
- `scripts/backup-telz.sh`;
- `scripts/restore-telz.sh`;
- `scripts/rollback-telz.sh`;
- `scripts/update-telz.sh`;
- `scripts/finish-ssl.sh`;
- `docs/INSTALL_TELZ_VPS.md`;
- `docs/UPDATE_TELZ_VPS.md`;
- `docs/BACKUP_AND_RESTORE.md`;
- `docs/INSTALLER_TROUBLESHOOTING.md`.

Capacidades implementadas:

- modo interativo e modo `--config ... --non-interactive`;
- estado por fase em `/var/lib/telz-installer/state`;
- log em `/var/log/telz-installer`;
- validacao de slug, diretorio, identificadores, portas e dominio;
- instalacao de pacotes base, Node/pnpm, Python, PostgreSQL, Nginx e UFW;
- clone/update de repositorio;
- virtualenv e requirements backend;
- `.env` backend com flags multi-tenant desligadas por padrao;
- Alembic gated com `heads/current/history` antes de `upgrade head`;
- typecheck, testes e build frontend;
- templates systemd para `telz-api` e `telz-web`;
- template Nginx preservando `Host` e `X-Forwarded-Host`;
- SSL opcional com Certbot;
- backup, restore, update, rollback de codigo e health check.
- WhatsApp Gateway instalado por padrao como `telz-whatsapp-gateway`, junto com `telz-api` e `telz-web`, porque faz parte do sistema atual.
- Mercado Pago e ASAAS preparados no `backend/.env` como gateways de pagamento de pedidos, com credenciais opcionais na instalacao e configuracao posterior pelo painel `/painel/pagamentos`.

Gates preservados:

- o instalador nao foi executado neste Windows;
- a sintaxe Bash foi validada com Git Bash, mas ainda nao houve teste em Ubuntu/VPS;
- nao ha `curl | bash` para instalacao NodeSource;
- nao ha downgrade Alembic automatico;
- nao ha comandos destrutivos amplos;
- `.env` existente e preservado por padrao, salvo se `TELZ_OVERWRITE_ENV=true`;
- as flags multi-tenant continuam desligadas na instalacao inicial.
- a opcao do WhatsApp Gateway nao e tratada como pendencia de escopo; ele entra na instalacao padrao, com health operacional dependente da sessao/QR Code.
- Mercado Pago e ASAAS nao sao billing SaaS da Telz nesta fase; continuam pertencendo ao dominio de pagamento dos pedidos.

Validacao executada nesta fase:

- `git diff --check -- installer scripts/backup-telz.sh scripts/finish-ssl.sh scripts/health-check.sh scripts/restore-telz.sh scripts/rollback-telz.sh scripts/update-telz.sh docs/INSTALL_TELZ_VPS.md docs/UPDATE_TELZ_VPS.md docs/BACKUP_AND_RESTORE.md docs/INSTALLER_TROUBLESHOOTING.md`;
- `bash -n` via Git Bash para `installer/install.sh`, `installer/lib/*.sh` e `scripts/*.sh`;
- varredura estatica para evitar `rm -rf`, `dropdb`, downgrade Alembic, `git reset`, `chmod 777`, `eval` e flags multi-tenant ligadas.

### 26.13 Instalador modular Telz - primeira versao executavel

Esta fase materializou a primeira versao executavel do instalador modular Telz para VPS, preservando a decisao operacional de instalar primeiro em modo legado compativel e manter todas as flags multi-tenant desligadas por padrao.

Arquivos principais criados:

- `installer/install.sh`;
- `installer/config/defaults.env`;
- `installer/lib/colors.sh`;
- `installer/lib/prompts.sh`;
- `installer/lib/validation.sh`;
- `installer/lib/system.sh`;
- `installer/lib/git.sh`;
- `installer/lib/database.sh`;
- `installer/lib/backend.sh`;
- `installer/lib/frontend.sh`;
- `installer/lib/nginx.sh`;
- `installer/lib/ssl.sh`;
- `installer/lib/systemd.sh`;
- `installer/lib/backup.sh`;
- `installer/lib/firewall.sh`;
- `installer/lib/summary.sh`;
- `installer/templates/telz-api.service`;
- `installer/templates/telz-web.service`;
- `installer/templates/nginx-telz.conf`;
- `installer/templates/env.production.example`;
- `scripts/update-telz.sh`;
- `scripts/rollback-telz.sh`;
- `scripts/backup-telz.sh`;
- `scripts/restore-telz.sh`;
- `scripts/health-check.sh`;
- `scripts/finish-ssl.sh`;
- `docs/INSTALL_TELZ_VPS.md`;
- `docs/UPDATE_TELZ_VPS.md`;
- `docs/BACKUP_AND_RESTORE.md`;
- `docs/INSTALLER_TROUBLESHOOTING.md`.

Comportamento implementado:

- instalacao interativa via `sudo bash installer/install.sh`;
- modo nao interativo com `--config arquivo.env --non-interactive`;
- retomada por fase com `--resume`;
- logs em `/var/log/telz-installer`;
- estado em `/var/lib/telz-installer/state`;
- validacao de Ubuntu, path de instalacao, slug, banco, usuario e segredos basicos;
- instalacao de pacotes, usuario de servico, diretorios, firewall, Node/pnpm, Python/venv, PostgreSQL local opcional, dependencias backend e frontend;
- geracao de `backend/.env` com flags multi-tenant desligadas;
- gate explicito antes de `alembic upgrade head`;
- typecheck, testes e build antes de systemd;
- services `telz-api` e `telz-web`;
- Nginx para dominio principal preservando `Host` e headers de proxy;
- SSL por Certbot quando DNS estiver pronto;
- backup diario opcional;
- scripts auxiliares de update, rollback de codigo/build, backup, restore, health check e finalizacao posterior de SSL.

Restricoes preservadas:

- nao ativa multi-tenant;
- nao publica `curl | bash`;
- nao remove banco, uploads, backups ou certificados;
- nao faz downgrade automatico de banco;
- nao declara instalador validado em producao sem teste em VPS limpa.

Gate ainda aberto:

- executar em VPS Ubuntu limpa ou staging descartavel;
- validar cadeia real Alembic/PostgreSQL;
- validar Nginx/systemd/SSL com dominio real;
- ajustar comandos conforme logs reais antes de considerar o instalador pronto para uso operacional recorrente.

### 26.14 Deploy Telz e estado real do instalador

Esta atualizacao consolida o estado operacional do deploy apos a criacao do instalador modular e os ajustes de escopo feitos para instalar tudo que o sistema possui no momento da instalacao.

Arquivos de deploy/documentacao relacionados:

- `DEPLOY.md`;
- `docs/INSTALL_TELZ_VPS.md`;
- `docs/UPDATE_TELZ_VPS.md`;
- `docs/BACKUP_AND_RESTORE.md`;
- `docs/INSTALLER_TROUBLESHOOTING.md`;
- `docs/TELZ_VPS_INSTALL_PHASED_METHOD.md`;
- `installer/install.sh`;
- `installer/config/defaults.env`;
- `installer/lib/`;
- `installer/templates/`;
- `scripts/update-telz.sh`;
- `scripts/rollback-telz.sh`;
- `scripts/backup-telz.sh`;
- `scripts/restore-telz.sh`;
- `scripts/health-check.sh`;
- `scripts/finish-ssl.sh`.

Decisao operacional atual:

- `DEPLOY.md` permanece como guia manual legado e referencia de diagnostico.
- Novas VPS devem usar o instalador modular Telz como caminho recomendado.
- O comando de entrada planejado para operador continua simples: `sudo bash installer/install.sh`.
- O instalador foi criado e validado estaticamente, mas ainda nao deve ser chamado de 100% pronto para producao sem teste em Ubuntu/VPS limpa.

Componentes que entram na instalacao padrao:

- API FastAPI como `telz-api`;
- Web como `telz-web`;
- WhatsApp Gateway Baileys como `telz-whatsapp-gateway`;
- PostgreSQL local opcional;
- Nginx;
- SSL via Certbot quando DNS estiver pronto;
- backup, update, rollback e health check;
- Mercado Pago e ASAAS preparados no `backend/.env` como gateways de pagamento dos pedidos.

Regras preservadas:

- WhatsApp Gateway faz parte do sistema atual e entra por padrao. O service pode subir antes da sessao estar conectada; a operacao real depende do QR Code no painel.
- Mercado Pago e ASAAS pertencem ao dominio de pagamento dos pedidos das lojas. Nao representam billing SaaS da Telz nesta fase.
- Credenciais de Mercado Pago e ASAAS podem ficar vazias na instalacao e ser configuradas depois no painel `/painel/pagamentos`.
- Todas as flags multi-tenant ficam desligadas na instalacao inicial.
- A ativacao multi-tenant nao deve ser feita por botao unico nem por edicao manual improvisada do `.env`.

Direcao segura para flags:

- criar `telz-cli flags status`;
- criar `telz-cli flags enable`;
- criar `telz-cli flags disable`;
- exigir preflight antes de ativar qualquer flag;
- exigir backup antes de alterar estado operacional;
- ativar por ondas, nunca em big-bang;
- criar painel/botao apenas depois que a logica segura existir no backend/CLI.

Gates ainda abertos:

- testar instalacao interativa em VPS Ubuntu limpa;
- testar modo nao interativo com `--config ... --non-interactive`;
- testar `--resume`;
- validar Alembic real em PostgreSQL;
- validar services `telz-api`, `telz-web` e `telz-whatsapp-gateway` no systemd;
- validar Nginx, SSL e health check com dominio real;
- validar backup, restore, update e rollback em ambiente descartavel;
- implementar e validar `telz-cli flags` antes de qualquer ativacao multi-tenant assistida.

### 26.15 Atualizacao do DEPLOY.md para Telz

`DEPLOY.md` foi atualizado para deixar explicito que o fluxo antigo permanece como referencia manual/legada e que novas instalacoes Telz devem priorizar o instalador modular em `installer/install.sh`.

O topo do documento agora registra:

- status do instalador como primeira versao executavel, ainda pendente de teste em VPS Ubuntu limpa;
- documentacao operacional atual em `docs/INSTALL_TELZ_VPS.md`, `docs/UPDATE_TELZ_VPS.md`, `docs/BACKUP_AND_RESTORE.md`, `docs/INSTALLER_TROUBLESHOOTING.md` e `docs/TELZ_VPS_INSTALL_PHASED_METHOD.md`;
- componentes instalados: `telz-api`, `telz-web` e `telz-whatsapp-gateway`;
- preparo de Mercado Pago e ASAAS para pagamentos de pedidos;
- flags multi-tenant desligadas na instalacao inicial;
- `telz-cli flags` ainda pendente;
- comandos principais de health, backup, update e logs.

Validacao executada nesta fase:

- `git diff --check -- DEPLOY.md KNOWLEDGE_BASE.md`.

---

## 27. Atualizacao 2026-07-22 - Rating WhatsApp, Previews e Automacoes Transversais

Esta atualizacao registra a entrega consolidada das fases 1 a 5 da evolucao de marketing e automacoes, publicada em `origin/main` no commit `6065939` (`feat: adicionar automacoes transversais e previews sociais`). A entrega estende os dominios existentes de CRM, WhatsApp Marketing, Trafego Pago, pedidos, pagamentos e fidelidade, sem criar um subsistema paralelo.

### 27.1 Fase 1 - rating de risco de contato no WhatsApp

O disparo de campanhas WhatsApp passou a avaliar risco individual antes do envio. O dominio persiste o estado atual em `customer_contact_risks` e o historico auditavel em `customer_contact_risk_events`, sempre com ownership por `tenant_id`.

Sinais tratados pelo rating:

- denuncia do contato;
- reclamacao relacionada ao pedido;
- bloqueio no WhatsApp;
- mais de duas campanhas entregues ao mesmo cliente em uma janela de 15 dias;
- override administrativo auditavel.

O score fica entre 0 e 100 e e classificado em `low`, `attention`, `high` ou `blocked`. A avaliacao ocorre no backend antes do envio; portanto, o bloqueio nao depende apenas da interface. Eventos possuem chave de deduplicacao por tenant e o envio elegivel atualiza o contador da janela quinzenal.

Arquivos e migration principais:

- `backend/models/customer_contact_risk.py`;
- `backend/services/customer_contact_risk_service.py`;
- `backend/routes/customer_contact_risk.py`;
- `backend/routes/whatsapp_marketing.py`;
- `backend/migrations/versions/20260812_customer_contact_risk.py`.

### 27.2 Fase 2 - preview de criativos por rede social

O fluxo de Trafego Pago passou a renderizar o criativo conforme a plataforma e o posicionamento selecionados:

- Facebook Feed: proporcao aproximada de 1.91:1;
- Instagram Feed: 1:1;
- Stories, Reels e TikTok: 9:16;
- Google e configuracoes manuais: fallback generico.

O componente informa dimensoes recomendadas, exibe alertas de incompatibilidade e demarca areas seguras nos formatos verticais. O preview nao inicia video automaticamente e pode ser fechado por backdrop ou pela tecla Escape.

Arquivos principais:

- `client/components/admin/SocialCreativePreview.tsx`;
- `client/pages/admin/PaidTraffic.tsx`.

### 27.3 Fase 3 - nucleo transversal de automacoes

O motor existente foi ampliado com catalogo controlado, validacao estruturada, simulacao sem efeitos colaterais e processamento duravel. Nao existe suporte a SQL ou HTTP arbitrario em automacoes.

Gatilhos liberados no catalogo:

- `customer.created`;
- `customer.tag_assigned`;
- `order.created`;
- `order.status_changed`;
- `payment.confirmed`;
- `loyalty.level_up`.

Acoes liberadas:

- `crm.assign_tag`;
- `crm.create_task`;
- `notification.send_whatsapp`;
- `notification.send_email`.

A tabela `automation_events` funciona como fila duravel e possui deduplicacao por `tenant_id + dedupe_key`, estados `pending`, `processing`, `processed`, `failed` e `dead`, numero maximo de tentativas, disponibilidade, lease e recuperacao de processamento interrompido. O consumo usa claim concorrente com `FOR UPDATE SKIP LOCKED`.

As tabelas filhas do motor receberam `tenant_id`, backfill para `tenant-legacy-default` e filtros tenant-scoped. O handler de WhatsApp reutiliza consentimento, opt-out e o rating de risco da fase 1. O builder administrativo consome o catalogo pela API, valida campos obrigatorios, permite simulacao e salva a definicao usando o contrato oficial em `client/lib/api.ts`.

Arquivos principais:

- `backend/services/automation_registry.py`;
- `backend/services/automation_event_service.py`;
- `backend/services/automation_action_handlers.py`;
- `backend/schemas/automation_core.py`;
- `backend/routes/automations.py`;
- `client/components/admin/AutomationCatalogBuilder.tsx`;
- `client/pages/admin/marketing/MarketingAutomacoes.tsx`;
- `backend/migrations/versions/20260813_automation_event_core.py`.

### 27.4 Fase 4 - produtores reais dos eventos

O servico `backend/services/automation_event_producer.py` padroniza payload, aggregate, customer, tenant e deduplicacao. Os produtores nao executam `commit`: o evento e a mutacao de negocio permanecem na mesma transacao SQLAlchemy, evitando evento orfao ou alteracao de dominio sem evento correspondente.

Integracoes efetivas:

- `customer.created`: cadastros publico, por senha, Google e leads quando ha tenant confiavel;
- `customer.tag_assigned`: atribuicao manual, IA e acao de automacao, somente quando a associacao foi criada;
- `order.created`: checkout e Salao;
- `order.status_changed`: `OrderService` e caminhos operacionais de pagamentos e entrega;
- `payment.confirmed`: gateway, confirmacao manual e Salao;
- `loyalty.level_up`: somente quando uma transacao de fidelidade promove o cliente.

Eventos inbound sem ownership confiavel permanecem sem publicacao, preservando isolamento em vez de assumir um tenant global.

### 27.5 Migration e deploy

A ordem obrigatoria de banco e:

1. `20260812_customer_contact_risk`;
2. `20260813_automation_event_core`.

A revision `20260813_automation_event_core` depende diretamente de `20260812_customer_contact_risk`. Antes de atualizar a aplicacao na VPS, executar o preflight Alembic (`heads`, `current` e `history`) e confirmar que existe apenas uma cabeca compativel. Depois do backup, aplicar a revision exata `20260813_automation_event_core`, executar build, reiniciar os services e validar o fluxo evento -> execucao -> acao com um tenant de teste.

O deploy ainda precisa comprovar em PostgreSQL real:

- upgrade das duas migrations e integridade das FKs compostas;
- isolamento entre dois tenants;
- deduplicacao e lease/retry do worker;
- bloqueio de WhatsApp por rating, consentimento e opt-out;
- execucao controlada de tag, tarefa CRM, WhatsApp e e-mail;
- renderizacao dos previews no build publicado.

Validacao registrada antes da publicacao:

- `git diff --check`;
- `npm.cmd run typecheck`;
- `npm.cmd test` com 33 testes aprovados;
- `npm.cmd run build`;
- sincronizacao `origin/main...HEAD = 0 0` apos o push do commit `6065939`.
