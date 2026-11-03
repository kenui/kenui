-- Receitas Bem Leves: tabelas, regras de acesso (RLS) e funções.
-- Rode no Supabase em: SQL Editor > New query > cole este arquivo > Run.

-- Compradores: criados e atualizados pelo webhook da Hotmart.
create table if not exists public.compradores (
  email text primary key,
  user_id uuid references auth.users(id) on delete set null,
  nome text,
  status text not null check (status in ('ativo', 'bloqueado')),
  transacao text,
  produto text,
  ultimo_evento text,
  criado_em timestamptz not null default now(),
  atualizado_em timestamptz not null default now()
);

-- Cada aviso da Hotmart fica registrado uma vez só (o mesmo aviso pode chegar repetido).
create table if not exists public.eventos_hotmart (
  id text primary key,
  tipo text not null,
  email text,
  transacao text,
  conteudo jsonb not null,
  recebido_em timestamptz not null default now()
);

-- Pacote de receitas: só quem tem compra ativa consegue ler.
create table if not exists public.pacote_receitas (
  versao text primary key,
  conteudo jsonb not null,
  publicado_em timestamptz not null default now()
);

-- Favoritos e trocas do plano de cada pessoa (cópia na conta para não perder ao trocar de celular).
create table if not exists public.dados_do_usuario (
  user_id uuid primary key references auth.users(id) on delete cascade,
  favoritos jsonb not null default '[]'::jsonb,
  trocas jsonb not null default '{}'::jsonb,
  atualizado_em timestamptz not null default now()
);

alter table public.compradores enable row level security;
alter table public.eventos_hotmart enable row level security;
alter table public.pacote_receitas enable row level security;
alter table public.dados_do_usuario enable row level security;

-- A pessoa tem compra ativa? (usa o e-mail do login)
create or replace function public.tem_acesso()
returns boolean
language sql
stable
security definer
set search_path = public
as $$
  select exists (
    select 1 from public.compradores
    where email = lower(coalesce(auth.jwt() ->> 'email', ''))
      and status = 'ativo'
  );
$$;
revoke all on function public.tem_acesso() from public;
grant execute on function public.tem_acesso() to authenticated;

drop policy if exists "ler pacote com compra ativa" on public.pacote_receitas;
create policy "ler pacote com compra ativa" on public.pacote_receitas
  for select to authenticated using (public.tem_acesso());

drop policy if exists "ver os próprios dados" on public.dados_do_usuario;
create policy "ver os próprios dados" on public.dados_do_usuario
  for select to authenticated using (user_id = auth.uid());
drop policy if exists "criar os próprios dados" on public.dados_do_usuario;
create policy "criar os próprios dados" on public.dados_do_usuario
  for insert to authenticated with check (user_id = auth.uid() and public.tem_acesso());
drop policy if exists "mudar os próprios dados" on public.dados_do_usuario;
create policy "mudar os próprios dados" on public.dados_do_usuario
  for update to authenticated using (user_id = auth.uid()) with check (user_id = auth.uid() and public.tem_acesso());

-- compradores e eventos_hotmart não têm política: só o webhook (chave de serviço) mexe nelas.

-- Usada pelo webhook para achar o usuário pelo e-mail.
create or replace function public.usuario_por_email(p_email text)
returns uuid
language sql
stable
security definer
set search_path = auth, public
as $$
  select id from auth.users where lower(email) = lower(p_email) limit 1;
$$;
revoke all on function public.usuario_por_email(text) from public, anon, authenticated;
grant execute on function public.usuario_por_email(text) to service_role;

-- Consulta leve usada pela tarefa diária que mantém o projeto grátis acordado.
create or replace function public.manter_acordado()
returns text
language sql
stable
as $$ select 'ok'::text; $$;
grant execute on function public.manter_acordado() to anon;
