-- =============================================================================
-- Script de criação do banco de dados PostgreSQL
-- Versão: 1.0.0
-- =============================================================================
--
-- ┌─────────────────────────────────────────────────────────────────────────┐
-- │  FORMAS DE EXECUTAR                                                     │
-- │                                                                         │
-- │  1. Via script shell (RECOMENDADO — passa o nome automaticamente):      │
-- │     bash setup_database.sh --nome minhaloja                             │
-- │                                                                         │
-- │  2. Via psql com variáveis na linha de comando:                         │
-- │     psql -U postgres -v DBNAME=minhaloja -v DBUSER=minhaloja_user \     │
-- │       -f setup_database.sql                                             │
-- │                                                                         │
-- │  3. Editando manualmente as duas linhas abaixo e rodando:               │
-- │     psql -U postgres -f setup_database.sql                              │
-- └─────────────────────────────────────────────────────────────────────────┘
--
-- =============================================================================

-- -----------------------------------------------------------------------------
-- VARIÁVEIS — edite aqui se for rodar diretamente com psql
-- (são ignoradas se você passar -v DBNAME=... na linha de comando)
-- -----------------------------------------------------------------------------
\if :{?DBNAME}
\else
  \set DBNAME    minhaloja
\endif

\if :{?DBUSER}
\else
  \set DBUSER    minhaloja_user
\endif

-- -----------------------------------------------------------------------------
-- 1. BANCO DE DADOS E EXTENSÕES
-- -----------------------------------------------------------------------------

-- Cria o banco se ainda não existir
SELECT format('CREATE DATABASE %I', :'DBNAME')
WHERE NOT EXISTS (
    SELECT FROM pg_database WHERE datname = :'DBNAME'
)\gexec

-- Conecta ao banco recém-criado (ou já existente)
\c :DBNAME

-- Extensão para hashing de senhas (bcrypt via pgcrypto)
CREATE EXTENSION IF NOT EXISTS pgcrypto;
-- Extensão para geração de UUID pelo banco
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- -----------------------------------------------------------------------------
-- 2. TIPOS ENUM
-- -----------------------------------------------------------------------------

DO $$ BEGIN
  CREATE TYPE orderstatus AS ENUM (
    'pending', 'waiting_payment', 'paid', 'preparing',
    'ready_for_pickup', 'on_the_way', 'delivered',
    'cancelled', 'refunded'
  );
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
  CREATE TYPE pricingrule AS ENUM (
    'most_expensive', 'average', 'proportional'
  );
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
  CREATE TYPE coupontype AS ENUM (
    'percentage', 'fixed'
  );
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
  CREATE TYPE transactiontype AS ENUM (
    'earned', 'redeemed'
  );
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
  CREATE TYPE paymentmethod AS ENUM (
    'pix', 'credit_card', 'debit_card', 'cash'
  );
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
  CREATE TYPE paymentstatus AS ENUM (
    'pending', 'paid', 'failed', 'refunded'
  );
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
  CREATE TYPE vehicletype AS ENUM (
    'motorcycle', 'bicycle', 'car', 'walking'
  );
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
  CREATE TYPE deliverypersonstatus AS ENUM (
    'available', 'busy', 'offline'
  );
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
  CREATE TYPE deliverystatus AS ENUM (
    'pending_assignment', 'assigned', 'picked_up', 'on_the_way',
    'delivered', 'completed', 'failed', 'cancelled'
  );
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
  CREATE TYPE shippingruletype AS ENUM (
    'fixed', 'per_distance', 'free_above', 'promotional'
  );
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
  CREATE TYPE areatype AS ENUM (
    'city', 'neighborhood', 'zip_prefix'
  );
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

-- -----------------------------------------------------------------------------
-- 3. TABELAS
-- -----------------------------------------------------------------------------

-- ── Usuários administradores ──────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS admin_users (
    id             VARCHAR PRIMARY KEY DEFAULT uuid_generate_v4()::VARCHAR,
    email          VARCHAR(200) UNIQUE NOT NULL,
    name           VARCHAR(200) NOT NULL,
    password_hash  VARCHAR(300) NOT NULL,
    active         BOOLEAN NOT NULL DEFAULT TRUE,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ── Clientes ──────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS customers (
    id         VARCHAR PRIMARY KEY,
    name       VARCHAR(200) NOT NULL,
    email      VARCHAR(200) UNIQUE NOT NULL,
    phone      VARCHAR(30),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ── Endereços ─────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS addresses (
    id           VARCHAR PRIMARY KEY,
    customer_id  VARCHAR NOT NULL REFERENCES customers(id) ON DELETE CASCADE,
    street       VARCHAR(300) NOT NULL,
    number       VARCHAR(20),
    complement   VARCHAR(100),
    neighborhood VARCHAR(100),
    city         VARCHAR(100) NOT NULL,
    state        VARCHAR(50),
    zip_code     VARCHAR(20),
    is_default   BOOLEAN NOT NULL DEFAULT FALSE,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ── Produtos ──────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS products (
    id          VARCHAR PRIMARY KEY,
    name        VARCHAR(200) NOT NULL,
    description TEXT NOT NULL,
    price       FLOAT NOT NULL,
    icon        VARCHAR(100) DEFAULT '🍕',
    rating      FLOAT DEFAULT 4.5,
    active      BOOLEAN NOT NULL DEFAULT TRUE,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ── Configuração multi-sabores (singleton: id = 'default') ───────────────────
CREATE TABLE IF NOT EXISTS multi_flavors_config (
    id           VARCHAR PRIMARY KEY DEFAULT 'default',
    max_flavors  INTEGER NOT NULL DEFAULT 2,
    pricing_rule pricingrule NOT NULL DEFAULT 'most_expensive',
    updated_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ── Promoções ─────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS promotions (
    id          VARCHAR PRIMARY KEY,
    title       VARCHAR(200) NOT NULL,
    subtitle    VARCHAR(300),
    description TEXT,
    icon        VARCHAR(100) DEFAULT '🍕',
    active      BOOLEAN NOT NULL DEFAULT FALSE,
    valid_from  TIMESTAMPTZ,
    valid_until TIMESTAMPTZ,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ── Cupons ────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS coupons (
    id              VARCHAR PRIMARY KEY,
    code            VARCHAR(50) UNIQUE NOT NULL,
    description     VARCHAR(300),
    icon            VARCHAR(50) DEFAULT '🎟️',
    coupon_type     coupontype NOT NULL DEFAULT 'percentage',
    discount_value  FLOAT NOT NULL,
    min_order_value FLOAT NOT NULL DEFAULT 0.0,
    max_uses        INTEGER,
    used_count      INTEGER NOT NULL DEFAULT 0,
    expiry_date     TIMESTAMPTZ,
    active          BOOLEAN NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ── Pedidos ───────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS orders (
    id                    VARCHAR PRIMARY KEY,
    customer_id           VARCHAR REFERENCES customers(id),
    address_id            VARCHAR REFERENCES addresses(id),
    delivery_name         VARCHAR(200),
    delivery_phone        VARCHAR(30),
    delivery_street       VARCHAR(300),
    delivery_city         VARCHAR(100),
    delivery_complement   VARCHAR(100),
    status                orderstatus NOT NULL DEFAULT 'pending',
    coupon_id             VARCHAR REFERENCES coupons(id),
    subtotal              FLOAT NOT NULL,
    shipping_fee          FLOAT NOT NULL DEFAULT 0.0,
    discount              FLOAT NOT NULL DEFAULT 0.0,
    total                 FLOAT NOT NULL,
    estimated_time        INTEGER NOT NULL DEFAULT 40,
    loyalty_points_earned INTEGER NOT NULL DEFAULT 0,
    notes                 TEXT,
    created_at            TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at            TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ── Itens do pedido ───────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS order_items (
    id              VARCHAR PRIMARY KEY,
    order_id        VARCHAR NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
    product_id      VARCHAR NOT NULL REFERENCES products(id),
    quantity        INTEGER NOT NULL DEFAULT 1,
    selected_size   VARCHAR(50),
    flavor_division INTEGER NOT NULL DEFAULT 1,
    unit_price      FLOAT NOT NULL,
    total_price     FLOAT NOT NULL
);

-- ── Sabores dos itens ─────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS order_item_flavors (
    id            VARCHAR PRIMARY KEY,
    order_item_id VARCHAR NOT NULL REFERENCES order_items(id) ON DELETE CASCADE,
    product_id    VARCHAR NOT NULL REFERENCES products(id),
    flavor_name   VARCHAR(200) NOT NULL,
    flavor_price  FLOAT NOT NULL,
    position      INTEGER NOT NULL DEFAULT 0
);

-- ── Pagamentos ────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS payments (
    id             VARCHAR PRIMARY KEY,
    order_id       VARCHAR NOT NULL UNIQUE REFERENCES orders(id),
    method         paymentmethod NOT NULL,
    status         paymentstatus NOT NULL DEFAULT 'pending',
    amount         FLOAT NOT NULL,
    transaction_id VARCHAR(300),
    gateway        VARCHAR(50) NOT NULL DEFAULT 'mock',
    qr_code        TEXT,
    qr_code_text   TEXT,
    payment_url    VARCHAR(500),
    client_secret  VARCHAR(300),
    webhook_data   TEXT,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    paid_at        TIMESTAMPTZ
);

-- ── Configuração de gateway de pagamento (singleton: id = 'default') ─────────
CREATE TABLE IF NOT EXISTS payment_gateway_config (
    id                    VARCHAR PRIMARY KEY DEFAULT 'default',
    gateway               VARCHAR(50) NOT NULL DEFAULT 'mock',
    mp_public_key         VARCHAR(300),
    mp_access_token       VARCHAR(300),
    mp_webhook_secret     VARCHAR(300),
    stripe_publishable_key VARCHAR(300),
    stripe_secret_key     VARCHAR(300),
    stripe_webhook_secret VARCHAR(300),
    pagseguro_email       VARCHAR(200),
    pagseguro_token       VARCHAR(300),
    pix_key               VARCHAR(200),
    pix_key_type          VARCHAR(30),
    pix_beneficiary_name  VARCHAR(200),
    pix_beneficiary_city  VARCHAR(100),
    accept_pix            BOOLEAN NOT NULL DEFAULT TRUE,
    accept_credit_card    BOOLEAN NOT NULL DEFAULT TRUE,
    accept_debit_card     BOOLEAN NOT NULL DEFAULT FALSE,
    accept_cash           BOOLEAN NOT NULL DEFAULT TRUE,
    sandbox               BOOLEAN NOT NULL DEFAULT TRUE,
    updated_at            TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ── Níveis de fidelidade ──────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS loyalty_levels (
    id         VARCHAR PRIMARY KEY,
    name       VARCHAR(100) NOT NULL,
    min_points INTEGER NOT NULL,
    max_points INTEGER,
    icon       VARCHAR(50) NOT NULL DEFAULT '🏆',
    color      VARCHAR(30) NOT NULL DEFAULT 'orange',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ── Recompensas de fidelidade ─────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS loyalty_rewards (
    id              VARCHAR PRIMARY KEY,
    label           VARCHAR(200) NOT NULL,
    points_required INTEGER NOT NULL,
    icon            VARCHAR(50) NOT NULL DEFAULT '🎁',
    active          BOOLEAN NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ── Regras de fidelidade ──────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS loyalty_rules (
    id         VARCHAR PRIMARY KEY,
    label      VARCHAR(200) NOT NULL,
    icon       VARCHAR(50) NOT NULL DEFAULT '⭐',
    points     INTEGER NOT NULL,
    rule_type  VARCHAR(50) NOT NULL DEFAULT 'per_order',
    active     BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ── Conta de fidelidade por cliente ──────────────────────────────────────────
CREATE TABLE IF NOT EXISTS customer_loyalty (
    id           VARCHAR PRIMARY KEY,
    customer_id  VARCHAR UNIQUE NOT NULL REFERENCES customers(id) ON DELETE CASCADE,
    total_points INTEGER NOT NULL DEFAULT 0,
    level_id     VARCHAR REFERENCES loyalty_levels(id),
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ── Transações de fidelidade ──────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS loyalty_transactions (
    id                  VARCHAR PRIMARY KEY,
    customer_loyalty_id VARCHAR NOT NULL REFERENCES customer_loyalty(id) ON DELETE CASCADE,
    order_id            VARCHAR REFERENCES orders(id),
    points              INTEGER NOT NULL,
    transaction_type    transactiontype NOT NULL,
    description         VARCHAR(300),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ── Entregadores ──────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS delivery_persons (
    id                  VARCHAR PRIMARY KEY,
    name                VARCHAR(200) NOT NULL,
    phone               VARCHAR(30) NOT NULL,
    vehicle_type        vehicletype NOT NULL DEFAULT 'motorcycle',
    status              deliverypersonstatus NOT NULL DEFAULT 'offline',
    active              BOOLEAN NOT NULL DEFAULT TRUE,
    location_lat        FLOAT,
    location_lng        FLOAT,
    location_updated_at TIMESTAMPTZ,
    total_deliveries    INTEGER NOT NULL DEFAULT 0,
    average_rating      FLOAT NOT NULL DEFAULT 5.0,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ── Entregas ──────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS deliveries (
    id                   VARCHAR PRIMARY KEY,
    order_id             VARCHAR NOT NULL UNIQUE REFERENCES orders(id),
    delivery_person_id   VARCHAR REFERENCES delivery_persons(id),
    status               deliverystatus NOT NULL DEFAULT 'pending_assignment',
    assigned_at          TIMESTAMPTZ,
    picked_up_at         TIMESTAMPTZ,
    delivered_at         TIMESTAMPTZ,
    estimated_minutes    INTEGER NOT NULL DEFAULT 40,
    delivery_photo_url   VARCHAR(500),
    recipient_name       VARCHAR(200),
    notes                TEXT,
    rating               INTEGER,
    rating_comment       TEXT,
    created_at           TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at           TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ── Zonas de entrega ──────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS shipping_zones (
    id         VARCHAR PRIMARY KEY,
    name       VARCHAR(100) NOT NULL,
    active     BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ── Áreas das zonas ───────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS shipping_zone_areas (
    id        VARCHAR PRIMARY KEY,
    zone_id   VARCHAR NOT NULL REFERENCES shipping_zones(id) ON DELETE CASCADE,
    area_type areatype NOT NULL,
    value     VARCHAR(100) NOT NULL
);

-- ── Regras de frete ───────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS shipping_rules (
    id                VARCHAR PRIMARY KEY,
    zone_id           VARCHAR REFERENCES shipping_zones(id),
    name              VARCHAR(100) NOT NULL,
    rule_type         shippingruletype NOT NULL,
    priority          INTEGER NOT NULL DEFAULT 0,
    active            BOOLEAN NOT NULL DEFAULT TRUE,
    base_price        FLOAT NOT NULL DEFAULT 0.0,
    per_km_price      FLOAT NOT NULL DEFAULT 0.0,
    store_lat         FLOAT,
    store_lng         FLOAT,
    free_above_amount FLOAT,
    valid_from        TIMESTAMPTZ,
    valid_until       TIMESTAMPTZ,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- -----------------------------------------------------------------------------
-- 4. ÍNDICES
-- -----------------------------------------------------------------------------

CREATE INDEX IF NOT EXISTS idx_orders_customer_id   ON orders(customer_id);
CREATE INDEX IF NOT EXISTS idx_orders_status         ON orders(status);
CREATE INDEX IF NOT EXISTS idx_orders_created_at     ON orders(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_order_items_order_id  ON order_items(order_id);
CREATE INDEX IF NOT EXISTS idx_payments_order_id     ON payments(order_id);
CREATE INDEX IF NOT EXISTS idx_deliveries_order_id   ON deliveries(order_id);
CREATE INDEX IF NOT EXISTS idx_customers_phone       ON customers(phone);
CREATE INDEX IF NOT EXISTS idx_customers_email       ON customers(email);
CREATE INDEX IF NOT EXISTS idx_coupons_code          ON coupons(code);

-- -----------------------------------------------------------------------------
-- 5. DADOS INICIAIS (SEED)
-- -----------------------------------------------------------------------------

-- ── Usuário administrador padrão ──────────────────────────────────────────────
INSERT INTO admin_users (id, email, name, password_hash, active)
VALUES (
    uuid_generate_v4()::VARCHAR,
    'adm@brasell.com.br',
    'Administrador',
    crypt('Theodonna@7', gen_salt('bf', 12)),
    TRUE
)
ON CONFLICT (email) DO NOTHING;

-- ── Configuração multi-sabores ────────────────────────────────────────────────
INSERT INTO multi_flavors_config (id, max_flavors, pricing_rule)
VALUES ('default', 2, 'most_expensive')
ON CONFLICT (id) DO NOTHING;

-- ── Configuração de gateway de pagamento ──────────────────────────────────────
INSERT INTO payment_gateway_config (
    id, gateway, accept_pix, accept_credit_card, accept_debit_card, accept_cash, sandbox
)
VALUES ('default', 'mock', TRUE, TRUE, FALSE, TRUE, TRUE)
ON CONFLICT (id) DO NOTHING;

-- ── Produtos ──────────────────────────────────────────────────────────────────
INSERT INTO products (id, name, description, price, icon, rating) VALUES
    ('prod-' || substr(md5(random()::text), 1, 8), 'Calabresa',          'Molho de tomate, mussarela, calabresa fatiada e orégano',          35.0, '🍕', 4.5),
    ('prod-' || substr(md5(random()::text), 1, 8), 'Frango c/ Catupiry', 'Frango desfiado, catupiry e azeitonas',                            42.0, '🐔', 4.7),
    ('prod-' || substr(md5(random()::text), 1, 8), 'Portuguesa',         'Presunto, ovos, cebola, pimentão e ervilhas',                      38.0, '🇵🇹', 4.3),
    ('prod-' || substr(md5(random()::text), 1, 8), 'Margherita',         'Molho de tomate fresco, mussarela de búfala e manjericão',         40.0, '🌿', 4.8),
    ('prod-' || substr(md5(random()::text), 1, 8), 'Pepperoni',          'Molho especial, mussarela e pepperoni artesanal',                  45.0, '🔴', 4.9),
    ('prod-' || substr(md5(random()::text), 1, 8), 'Camarão',            'Camarão salteado ao alho, molho branco e catupiry',                65.0, '🦐', 4.6),
    ('prod-' || substr(md5(random()::text), 1, 8), '4 Queijos',          'Mussarela, parmesão, gorgonzola e provolone',                      48.0, '🧀', 4.7),
    ('prod-' || substr(md5(random()::text), 1, 8), 'Vegana',             'Legumes assados, pimentão, abobrinha e molho de tomate',           37.0, '🥦', 4.4)
ON CONFLICT DO NOTHING;

-- ── Promoção ──────────────────────────────────────────────────────────────────
INSERT INTO promotions (id, title, subtitle, icon, active)
VALUES (uuid_generate_v4()::VARCHAR, '20% off', 'Em qualquer pizza', '🍕', TRUE)
ON CONFLICT DO NOTHING;

-- ── Cupons ────────────────────────────────────────────────────────────────────
INSERT INTO coupons (id, code, description, icon, coupon_type, discount_value, min_order_value) VALUES
    (uuid_generate_v4()::VARCHAR, 'BEMVINDO10', '10% de desconto na primeira compra', '🎉', 'percentage', 10.0, 30.0),
    (uuid_generate_v4()::VARCHAR, 'FRETE0',     'Frete grátis em qualquer pedido',    '🛵', 'fixed',      10.0,  0.0)
ON CONFLICT (code) DO NOTHING;

-- ── Níveis de fidelidade ──────────────────────────────────────────────────────
INSERT INTO loyalty_levels (id, name, min_points, max_points, icon, color) VALUES
    (uuid_generate_v4()::VARCHAR, 'Bronze',   0,    500,  '🥉', 'orange'),
    (uuid_generate_v4()::VARCHAR, 'Prata',    501,  1500, '🥈', 'gray'),
    (uuid_generate_v4()::VARCHAR, 'Ouro',     1501, 3000, '🥇', 'yellow'),
    (uuid_generate_v4()::VARCHAR, 'Diamante', 3001, NULL, '💎', 'blue')
ON CONFLICT DO NOTHING;

-- ── Recompensas de fidelidade ─────────────────────────────────────────────────
INSERT INTO loyalty_rewards (id, label, points_required, icon) VALUES
    (uuid_generate_v4()::VARCHAR, 'Pizza Grátis',     500, '🍕'),
    (uuid_generate_v4()::VARCHAR, 'Entrega Grátis',   200, '🛵'),
    (uuid_generate_v4()::VARCHAR, 'Desconto de R$15', 300, '💰'),
    (uuid_generate_v4()::VARCHAR, 'Bebida Grátis',    150, '🥤')
ON CONFLICT DO NOTHING;

-- ── Regras de fidelidade ──────────────────────────────────────────────────────
INSERT INTO loyalty_rules (id, label, icon, points, rule_type) VALUES
    (uuid_generate_v4()::VARCHAR, 'Primeiro Pedido',  '⭐', 50, 'first_order'),
    (uuid_generate_v4()::VARCHAR, 'A cada R$1 gasto', '💸',  1, 'per_real'),
    (uuid_generate_v4()::VARCHAR, 'Pedido Entregue',  '📦', 10, 'per_order')
ON CONFLICT DO NOTHING;

-- ── Regras de frete ───────────────────────────────────────────────────────────
INSERT INTO shipping_rules (id, name, rule_type, base_price, priority) VALUES
    (uuid_generate_v4()::VARCHAR, 'Taxa padrão',                'fixed',      8.0,  0),
    (uuid_generate_v4()::VARCHAR, 'Frete grátis acima de R$100','free_above', 8.0, 10)
ON CONFLICT DO NOTHING;

-- -----------------------------------------------------------------------------
-- 6. FUNÇÃO DE VERIFICAÇÃO DE SENHA (para uso na aplicação)
-- -----------------------------------------------------------------------------
-- Uso: SELECT check_admin_password('adm@brasell.com.br', 'Theodonna@7');

CREATE OR REPLACE FUNCTION check_admin_password(p_email VARCHAR, p_password VARCHAR)
RETURNS BOOLEAN AS $$
DECLARE
    stored_hash VARCHAR;
BEGIN
    SELECT password_hash INTO stored_hash
    FROM admin_users
    WHERE email = p_email AND active = TRUE;

    IF stored_hash IS NULL THEN
        RETURN FALSE;
    END IF;

    RETURN (stored_hash = crypt(p_password, stored_hash));
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- -----------------------------------------------------------------------------
-- 7. PERMISSÕES DO USUÁRIO DO BANCO
-- -----------------------------------------------------------------------------
-- Concede todas as permissões ao usuário da aplicação
-- (executado apenas se DBUSER foi definido e existe no PostgreSQL)

DO $$
BEGIN
  IF current_setting('app.dbuser', true) IS NOT NULL
     AND current_setting('app.dbuser', true) != '' THEN
    EXECUTE format(
      'GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO %I;
       GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO %I;
       GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA public TO %I;',
      current_setting('app.dbuser'), current_setting('app.dbuser'), current_setting('app.dbuser')
    );
  END IF;
END $$;

-- -----------------------------------------------------------------------------
-- 8. RESUMO
-- -----------------------------------------------------------------------------

DO $$
DECLARE
    v_products  INTEGER;
    v_coupons   INTEGER;
    v_levels    INTEGER;
    v_admins    INTEGER;
    v_dbname    TEXT := current_database();
BEGIN
    SELECT COUNT(*) INTO v_products FROM products;
    SELECT COUNT(*) INTO v_coupons  FROM coupons;
    SELECT COUNT(*) INTO v_levels   FROM loyalty_levels;
    SELECT COUNT(*) INTO v_admins   FROM admin_users;

    RAISE NOTICE '=================================================';
    RAISE NOTICE 'Banco configurado com sucesso!';
    RAISE NOTICE 'Banco de dados:    %', v_dbname;
    RAISE NOTICE '-------------------------------------------------';
    RAISE NOTICE 'Produtos:          %', v_products;
    RAISE NOTICE 'Cupons:            %', v_coupons;
    RAISE NOTICE 'Níveis fidelidade: %', v_levels;
    RAISE NOTICE 'Admins:            %', v_admins;
    RAISE NOTICE '-------------------------------------------------';
    RAISE NOTICE 'Usuário admin:     adm@brasell.com.br';
    RAISE NOTICE 'Senha:             Theodonna@7';
    RAISE NOTICE '=================================================';
END $$;
