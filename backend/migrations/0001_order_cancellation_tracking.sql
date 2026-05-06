-- Migration: rastreamento de cancelamento de pedidos
-- Executar na VPS: psql $DATABASE_URL -f backend/migrations/0001_order_cancellation_tracking.sql

ALTER TABLE orders
  ADD COLUMN IF NOT EXISTS cancelled_by        VARCHAR(50),
  ADD COLUMN IF NOT EXISTS cancellation_reason TEXT,
  ADD COLUMN IF NOT EXISTS cancelled_at        TIMESTAMPTZ;

-- Índice para buscar pedidos cancelados por responsável rapidamente
CREATE INDEX IF NOT EXISTS idx_orders_cancelled_by ON orders (cancelled_by)
  WHERE cancelled_by IS NOT NULL;

-- Comentário descritivo
COMMENT ON COLUMN orders.cancelled_by        IS 'Quem cancelou: customer | admin | system';
COMMENT ON COLUMN orders.cancellation_reason IS 'Motivo legível do cancelamento';
COMMENT ON COLUMN orders.cancelled_at        IS 'Timestamp do cancelamento';
