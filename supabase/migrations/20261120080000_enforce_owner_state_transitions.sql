-- AutoEarn AI: enforce owner-scoped lifecycle transitions at the database boundary.
-- This migration is prepared for review only. It must be explicitly applied to Supabase.

create or replace function public.autoearn_guard_opportunity_state()
returns trigger
language plpgsql
set search_path = ''
as $$
begin
  if tg_op = 'INSERT' then
    if new.status <> 'discovered' then
      raise exception 'New opportunities must start as discovered.'
        using errcode = '23514';
    end if;
    return new;
  end if;

  if new.id is distinct from old.id
     or new.owner_id is distinct from old.owner_id
     or new.created_at is distinct from old.created_at then
    raise exception 'Opportunity identity and ownership fields are immutable.'
      using errcode = '23514';
  end if;

  if new.status is distinct from old.status then
    if (old.status = 'discovered' and new.status in ('reviewing', 'ineligible', 'archived'))
       or (old.status = 'reviewing' and new.status in ('ineligible', 'archived'))
       or (old.status = 'ineligible' and new.status = 'archived') then
      null;
    else
      raise exception 'Invalid opportunity status transition: % -> %.', old.status, new.status
        using errcode = '23514';
    end if;
  end if;

  return new;
end;
$$;

create or replace function public.autoearn_guard_task_state()
returns trigger
language plpgsql
set search_path = ''
as $$
begin
  if tg_op = 'INSERT' then
    if new.status <> 'pending_approval'
       or new.approved_at is not null
       or new.completed_at is not null then
      raise exception 'New tasks must start pending approval without lifecycle timestamps.'
        using errcode = '23514';
    end if;
    return new;
  end if;

  if new.id is distinct from old.id
     or new.owner_id is distinct from old.owner_id
     or new.opportunity_id is distinct from old.opportunity_id
     or new.created_at is distinct from old.created_at then
    raise exception 'Task identity, ownership, and opportunity fields are immutable.'
      using errcode = '23514';
  end if;

  if new.status is not distinct from old.status then
    if new.approved_at is distinct from old.approved_at
       or new.completed_at is distinct from old.completed_at then
      raise exception 'Task lifecycle timestamps can only change during a valid transition.'
        using errcode = '23514';
    end if;
    return new;
  end if;

  if old.status = 'pending_approval' and new.status = 'approved' then
    new.approved_at := pg_catalog.clock_timestamp();
    new.completed_at := null;
  elsif old.status = 'approved' and new.status = 'completed' then
    if old.approved_at is null then
      raise exception 'A task must have an approval timestamp before completion.'
        using errcode = '23514';
    end if;
    new.approved_at := old.approved_at;
    new.completed_at := pg_catalog.clock_timestamp();
  elsif old.status in ('pending_approval', 'approved') and new.status = 'cancelled' then
    new.approved_at := old.approved_at;
    new.completed_at := null;
  else
    raise exception 'Invalid task status transition: % -> %.', old.status, new.status
      using errcode = '23514';
  end if;

  return new;
end;
$$;

create or replace function public.autoearn_guard_reward_state()
returns trigger
language plpgsql
set search_path = ''
as $$
begin
  if tg_op = 'INSERT' then
    if new.status <> 'pending' then
      raise exception 'New reward records must start as pending.'
        using errcode = '23514';
    end if;
    return new;
  end if;

  if new.id is distinct from old.id
     or new.owner_id is distinct from old.owner_id
     or new.amount is distinct from old.amount
     or new.currency is distinct from old.currency
     or new.created_at is distinct from old.created_at then
    raise exception 'Reward identity, ownership, amount, and currency fields are immutable.'
      using errcode = '23514';
  end if;

  -- ON DELETE SET NULL must be allowed to preserve the reward ledger when
  -- its linked opportunity is deleted. Owners still cannot edit this link.
  if new.opportunity_id is distinct from old.opportunity_id then
    if new.opportunity_id is not null
       or old.opportunity_id is null
       or exists (
         select 1 from public.opportunities
         where id = old.opportunity_id
       ) then
      raise exception 'Reward opportunity association is immutable except when its opportunity is deleted.'
        using errcode = '23514';
    end if;
  end if;

  if new.status is not distinct from old.status then
    if old.status in ('paid', 'rejected') and new.reference is distinct from old.reference then
      raise exception 'References for terminal reward records are immutable.'
        using errcode = '23514';
    end if;
    return new;
  end if;

  if (old.status = 'pending' and new.status in ('confirmed', 'rejected'))
     or (old.status = 'confirmed' and new.status in ('paid', 'rejected')) then
    if new.status = 'paid' and pg_catalog.btrim(new.reference) = '' then
      raise exception 'A paid reward requires a payment reference.'
        using errcode = '23514';
    end if;
  else
    raise exception 'Invalid reward status transition: % -> %.', old.status, new.status
      using errcode = '23514';
  end if;

  return new;
end;
$$;

create or replace function public.autoearn_guard_reward_delete()
returns trigger
language plpgsql
set search_path = ''
as $$
begin
  if old.status in ('confirmed', 'paid') then
    raise exception 'Confirmed or paid reward records cannot be deleted.'
      using errcode = '23514';
  end if;
  return old;
end;
$$;

drop trigger if exists autoearn_opportunity_state_guard on public.opportunities;
create trigger autoearn_opportunity_state_guard
before insert or update on public.opportunities
for each row execute function public.autoearn_guard_opportunity_state();

drop trigger if exists autoearn_task_state_guard on public.tasks;
create trigger autoearn_task_state_guard
before insert or update on public.tasks
for each row execute function public.autoearn_guard_task_state();

drop trigger if exists autoearn_reward_state_guard on public.rewards;
create trigger autoearn_reward_state_guard
before insert or update on public.rewards
for each row execute function public.autoearn_guard_reward_state();

drop trigger if exists autoearn_reward_delete_guard on public.rewards;
create trigger autoearn_reward_delete_guard
before delete on public.rewards
for each row execute function public.autoearn_guard_reward_delete();

-- Replace broad FOR ALL policies with explicit owner-scoped operations.
drop policy if exists "owner manages opportunities" on public.opportunities;
drop policy if exists "owner manages tasks" on public.tasks;
drop policy if exists "owner manages rewards" on public.rewards;

create policy "owners read opportunities"
on public.opportunities for select to authenticated
using ((select auth.uid()) = owner_id);

create policy "owners insert discovered opportunities"
on public.opportunities for insert to authenticated
with check ((select auth.uid()) = owner_id and status = 'discovered');

create policy "owners update opportunities"
on public.opportunities for update to authenticated
using ((select auth.uid()) = owner_id)
with check ((select auth.uid()) = owner_id);

create policy "owners delete opportunities"
on public.opportunities for delete to authenticated
using ((select auth.uid()) = owner_id);

create policy "owners read tasks"
on public.tasks for select to authenticated
using ((select auth.uid()) = owner_id);

create policy "owners insert pending tasks"
on public.tasks for insert to authenticated
with check (
  (select auth.uid()) = owner_id
  and status = 'pending_approval'
  and exists (
    select 1 from public.opportunities o
    where o.id = opportunity_id and o.owner_id = (select auth.uid())
  )
);

create policy "owners update tasks"
on public.tasks for update to authenticated
using ((select auth.uid()) = owner_id)
with check (
  (select auth.uid()) = owner_id
  and exists (
    select 1 from public.opportunities o
    where o.id = opportunity_id and o.owner_id = (select auth.uid())
  )
);

create policy "owners delete tasks"
on public.tasks for delete to authenticated
using ((select auth.uid()) = owner_id);

create policy "owners read rewards"
on public.rewards for select to authenticated
using ((select auth.uid()) = owner_id);

create policy "owners insert pending rewards"
on public.rewards for insert to authenticated
with check (
  (select auth.uid()) = owner_id
  and status = 'pending'
  and (
    opportunity_id is null
    or exists (
      select 1 from public.opportunities o
      where o.id = opportunity_id and o.owner_id = (select auth.uid())
    )
  )
);

create policy "owners update rewards"
on public.rewards for update to authenticated
using ((select auth.uid()) = owner_id)
with check (
  (select auth.uid()) = owner_id
  and (
    opportunity_id is null
    or exists (
      select 1 from public.opportunities o
      where o.id = opportunity_id and o.owner_id = (select auth.uid())
    )
  )
);

create policy "owners delete rewards"
on public.rewards for delete to authenticated
using ((select auth.uid()) = owner_id);
