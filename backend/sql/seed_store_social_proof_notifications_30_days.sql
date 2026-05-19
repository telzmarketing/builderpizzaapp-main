-- Seed de notificacoes simuladas para o modulo Notificacoes da loja.
-- Tabela real do projeto: store_notifications.
-- Gera 30 dias x 15 bairros x 10 nomes por bairro/dia = 4500 registros,
-- desde que os 6 produtos abaixo existam na tabela products com estes nomes.

BEGIN;

CREATE TEMP TABLE _store_notification_seed ON COMMIT DROP AS
WITH neighborhoods(name, n_idx) AS (
  VALUES
    ('Santana', 1),
    ('Tucuruvi', 2),
    ('Parada Inglesa', 3),
    ('Mandaqui', 4),
    ('Casa Verde', 5),
    ('Água Fria', 6),
    ('Santa Teresinha', 7),
    ('Vila Guilherme', 8),
    ('Vila Maria', 9),
    ('Imirim', 10),
    ('Lauzane Paulista', 11),
    ('Vila Gustavo', 12),
    ('Cachoeirinha', 13),
    ('Limão', 14),
    ('Jardim São Paulo', 15)
),
days(day_offset, notification_date) AS (
  SELECT gs, CURRENT_DATE + gs
  FROM generate_series(0, 29) AS gs
),
slots(gender, slot_idx) AS (
  VALUES
    ('f', 1), ('f', 2), ('f', 3), ('f', 4), ('f', 5),
    ('m', 1), ('m', 2), ('m', 3), ('m', 4), ('m', 5)
),
products_seed(product_name, p_idx) AS (
  VALUES
    ('Pizza Marguerita', 1),
    ('Pizza Portuguesa', 2),
    ('Pizza Quatro Queijos', 3),
    ('Pizza Calabresa', 4),
    ('Pizza Muçarela', 5),
    ('Pizza Frango com Catupiry', 6)
),
female_names(names) AS (
  VALUES (ARRAY[
    'Maria','Ana','Juliana','Camila','Fernanda','Patricia','Amanda','Carolina','Beatriz','Larissa',
    'Mariana','Renata','Aline','Leticia','Priscila','Daniela','Tatiane','Vanessa','Cristiane','Bruna',
    'Bianca','Claudia','Luciana','Rafaela','Isabela','Gabriela','Monica','Simone','Elaine','Natalia',
    'Adriana','Helena','Laura','Sabrina','Debora','Viviane','Sueli','Regina','Luana','Tais',
    'Roberta','Elisa','Cintia','Flavia','Joana','Michele','Patricia','Sandra','Teresa','Yasmin'
  ]::text[])
),
male_names(names) AS (
  VALUES (ARRAY[
    'Joao','Carlos','Marcos','Rafael','Bruno','Lucas','Felipe','Gustavo','Anderson','Fernando',
    'Ricardo','Eduardo','Thiago','Rodrigo','Leandro','Marcelo','Diego','Alexandre','Paulo','Daniel',
    'Roberto','Fabio','Vinicius','Matheus','Henrique','Gabriel','Andre','Sergio','Wesley','Caio',
    'Renato','Cesar','Murilo','Igor','Leonardo','Samuel','Hugo','Nelson','Vitor','Otavio',
    'Claudio','Rogerio','Mauricio','William','Douglas','Antonio','Jorge','Luiz','Alan','Denis'
  ]::text[])
),
surnames(names) AS (
  VALUES (ARRAY[
    'Silva','Santos','Oliveira','Souza','Pereira','Lima','Costa','Ferreira','Almeida','Rodrigues',
    'Gomes','Martins','Barbosa','Ribeiro','Carvalho','Melo','Castro','Rocha','Dias','Moreira',
    'Correia','Nunes','Cardoso','Vieira','Moura','Araujo','Campos','Teixeira','Mendes','Freitas',
    'Monteiro','Cavalcanti','Farias','Batista','Rezende','Borges','Pinto','Antunes','Duarte','Tavares'
  ]::text[])
),
base_rows AS (
  SELECT
    d.day_offset,
    d.notification_date,
    n.name AS neighborhood,
    n.n_idx,
    s.gender,
    s.slot_idx,
    ps.product_name,
    CASE
      WHEN s.gender = 'f' THEN
        fn.names[((d.day_offset * 11 + n.n_idx * 5 + s.slot_idx) % array_length(fn.names, 1)) + 1]
      ELSE
        mn.names[((d.day_offset * 13 + n.n_idx * 7 + s.slot_idx) % array_length(mn.names, 1)) + 1]
    END AS first_name,
    sn.names[((d.day_offset * 17 + n.n_idx * 3 + s.slot_idx) % array_length(sn.names, 1)) + 1] AS last_name,
    p.id AS product_id
  FROM days d
  CROSS JOIN neighborhoods n
  CROSS JOIN slots s
  CROSS JOIN female_names fn
  CROSS JOIN male_names mn
  CROSS JOIN surnames sn
  JOIN products_seed ps
    ON ps.p_idx = ((d.day_offset + n.n_idx + s.slot_idx) % 6) + 1
  LEFT JOIN products p
    ON lower(p.name) = lower(ps.product_name)
)
SELECT
  'sn-seed-' || substr(md5(notification_date::text || neighborhood || gender || slot_idx::text), 1, 24) AS id,
  'fomento'::varchar AS type,
  'active'::varchar AS status,
  'Simulada ' || notification_date::text || ' - ' || neighborhood || ' - ' || gender || slot_idx::text AS internal_name,
  first_name || ' ' || last_name AS display_name,
  product_id,
  neighborhood,
  '{nome}, {bairro}. Comprou hoje {produto_com_artigo}'::text AS template_text,
  CASE WHEN slot_idx IN (1, 2) THEN 'high' ELSE 'medium' END::varchar AS priority,
  (1 + ((n_idx + slot_idx + day_offset) % 3))::integer AS weight,
  7::integer AS display_seconds,
  (5 + ((n_idx * 7 + slot_idx * 11 + day_offset * 13) % 180))::integer AS purchase_minutes_ago,
  false::boolean AS clear_after_view,
  '09:00'::time AS start_time,
  '23:59'::time AS end_time,
  notification_date::date AS start_date,
  notification_date::date AS end_date,
  (extract(isodow from notification_date)::integer - 1) AS weekday,
  NOW() AS created_at,
  NOW() AS updated_at
FROM base_rows
WHERE product_id IS NOT NULL;

INSERT INTO store_notifications (
  id,
  type,
  status,
  internal_name,
  display_name,
  product_id,
  neighborhood,
  template_text,
  priority,
  weight,
  display_seconds,
  purchase_minutes_ago,
  clear_after_view,
  start_time,
  end_time,
  start_date,
  end_date,
  created_at,
  updated_at
)
SELECT
  id,
  type,
  status,
  internal_name,
  display_name,
  product_id,
  neighborhood,
  template_text,
  priority,
  weight,
  display_seconds,
  purchase_minutes_ago,
  clear_after_view,
  start_time,
  end_time,
  start_date,
  end_date,
  created_at,
  updated_at
FROM _store_notification_seed
ON CONFLICT (id) DO UPDATE SET
  status = EXCLUDED.status,
  internal_name = EXCLUDED.internal_name,
  display_name = EXCLUDED.display_name,
  product_id = EXCLUDED.product_id,
  neighborhood = EXCLUDED.neighborhood,
  template_text = EXCLUDED.template_text,
  priority = EXCLUDED.priority,
  weight = EXCLUDED.weight,
  display_seconds = EXCLUDED.display_seconds,
  purchase_minutes_ago = EXCLUDED.purchase_minutes_ago,
  clear_after_view = EXCLUDED.clear_after_view,
  start_time = EXCLUDED.start_time,
  end_time = EXCLUDED.end_time,
  start_date = EXCLUDED.start_date,
  end_date = EXCLUDED.end_date,
  updated_at = NOW();

INSERT INTO store_notification_days (id, notification_id, weekday)
SELECT
  'snd-seed-' || substr(md5(id || weekday::text), 1, 24),
  id,
  weekday
FROM _store_notification_seed
ON CONFLICT (id) DO NOTHING;

COMMIT;
