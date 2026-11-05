-- Kør denne fil i Supabase: SQL Editor -> New query -> indsæt -> Run.
-- Den er sikker at køre flere gange. Den opretter tabellen, hvis den ikke findes,
-- og tilføjer de kolonner, som log og historik har brug for.

create table if not exists jobansogninger (
  id          bigint generated always as identity primary key,
  created_at  timestamptz not null default now(),
  virksomhed  text,
  stilling    text,
  jobopslag   text,
  cv          text,
  ansogning   text,
  problemer   jsonb default '[]'::jsonb,
  log         jsonb default '[]'::jsonb
);

-- Hvis tabellen fandtes i forvejen, tilføjes de nye kolonner her
alter table jobansogninger add column if not exists created_at timestamptz not null default now();
alter table jobansogninger add column if not exists log jsonb default '[]'::jsonb;

-- Ingen må læse tabellen udefra. Appen bruger secret key på serveren og har stadig adgang.
alter table jobansogninger enable row level security;