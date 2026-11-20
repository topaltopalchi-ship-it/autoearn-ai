-- Lock AutoEarn to the one owner account present when this migration is applied.
-- This is a prepared migration: do not apply to production without explicit owner approval.

do $$
declare
  v_user_count bigint;
begin
  select count(*) into v_user_count from auth.users;
  if v_user_count <> 1 then
    raise exception 'AutoEarn single-owner lock requires exactly one existing Auth user; found %.', v_user_count;
  end if;
end;
$$;

create schema if not exists autoearn_private;
revoke all on schema autoearn_private from public, anon, authenticated;

create table autoearn_private.autoearn_owner_guard (
  owner_id uuid primary key references auth.users(id) on delete restrict,
  singleton boolean not null default true unique check (singleton)
);

insert into autoearn_private.autoearn_owner_guard (owner_id)
select id from auth.users;

revoke all on table autoearn_private.autoearn_owner_guard from public, anon, authenticated;

create or replace function public.autoearn_is_single_owner()
returns boolean
language sql
stable
security definer
set search_path = ''
as $$
  select exists (
    select 1
    from autoearn_private.autoearn_owner_guard
    where owner_id = (select auth.uid())
      and singleton
  );
$$;

revoke all on function public.autoearn_is_single_owner() from public, anon;
grant execute on function public.autoearn_is_single_owner() to authenticated;

-- Restrictive policies are ANDed with the existing owner_id-scoped policies.
-- They ensure that even another authenticated account cannot create its own tenant.
create policy "single owner account only"
on public.opportunities as restrictive
for all to authenticated
using (public.autoearn_is_single_owner())
with check (public.autoearn_is_single_owner());

create policy "single owner account only"
on public.tasks as restrictive
for all to authenticated
using (public.autoearn_is_single_owner())
with check (public.autoearn_is_single_owner());

create policy "single owner account only"
on public.rewards as restrictive
for all to authenticated
using (public.autoearn_is_single_owner())
with check (public.autoearn_is_single_owner());
