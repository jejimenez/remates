-- Run this once in the Supabase SQL editor before running ingest.py

create table if not exists remates (
  id bigserial primary key,
  codigo integer not null unique,
  fecha_remate date not null,
  ciudad text not null,
  departamento text not null,
  tipo_bien text not null,
  avaluo numeric(14,2) not null,
  oferta_minima numeric(14,2) not null,
  referencia text,
  week_uploaded date not null,
  created_at timestamptz default now(),
  updated_at timestamptz default now()
);

create index if not exists idx_remates_departamento on remates(departamento);
create index if not exists idx_remates_tipo_bien on remates(tipo_bien);
create index if not exists idx_remates_fecha on remates(fecha_remate);

-- Keep updated_at current automatically on upsert/update
create or replace function set_updated_at()
returns trigger as $$
begin
  new.updated_at = now();
  return new;
end;
$$ language plpgsql;

drop trigger if exists trg_remates_updated_at on remates;
create trigger trg_remates_updated_at
  before update on remates
  for each row execute function set_updated_at();
