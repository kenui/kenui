-- Receitas Bem Leves: produtos extras do funil (order bump, upsell e downsell).
-- Rode no Supabase em: SQL Editor > New query > cole este arquivo > Run. Pode rodar mais de uma vez.

-- Cada produto comprado por cada pessoa (o app principal também entra aqui).
create table if not exists public.produtos_comprados (
  email text not null,
  produto text not null check (produto in ('app', 'caderno', 'cardapio12', 'marmitas')),
  status text not null check (status in ('ativo', 'bloqueado')),
  transacao text,
  hotmart_produto_id text,
  atualizado_em timestamptz not null default now(),
  primary key (email, produto)
);
alter table public.produtos_comprados enable row level security;

-- A pessoa vê só as próprias compras (o app usa isso para mostrar os extras que ela tem).
drop policy if exists "ver as próprias compras" on public.produtos_comprados;
create policy "ver as próprias compras" on public.produtos_comprados
  for select to authenticated using (email = lower(coalesce(auth.jwt() ->> 'email', '')));

-- Conteúdo dos extras: cada linha só é lida por quem comprou aquele produto e tem acesso ao app.
create table if not exists public.conteudo_extras (
  produto text primary key check (produto in ('caderno', 'cardapio12', 'marmitas')),
  versao text not null,
  conteudo jsonb not null,
  publicado_em timestamptz not null default now()
);
alter table public.conteudo_extras enable row level security;

create or replace function public.comprou(p_produto text)
returns boolean
language sql
stable
security definer
set search_path = public
as $$
  select public.tem_acesso() and exists (
    select 1 from public.produtos_comprados
    where email = lower(coalesce(auth.jwt() ->> 'email', ''))
      and produto = p_produto
      and status = 'ativo'
  );
$$;
revoke all on function public.comprou(text) from public;
grant execute on function public.comprou(text) to authenticated;

drop policy if exists "ler extra comprado" on public.conteudo_extras;
create policy "ler extra comprado" on public.conteudo_extras
  for select to authenticated using (public.comprou(produto));

-- Quem já tinha acesso ao app passa a constar também como dono do produto 'app'.
insert into public.produtos_comprados (email, produto, status, transacao)
select email, 'app', status, transacao from public.compradores
on conflict (email, produto) do nothing;
