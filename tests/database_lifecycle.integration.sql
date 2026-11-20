-- Ephemeral PostgreSQL integration test for the AutoEarn lifecycle migrations.
-- This runs only inside GitHub Actions; it never connects to the live Supabase project.

create role anon nologin;
create role authenticated nologin;
create schema auth;
create table auth.users (id uuid primary key);
create function auth.uid()
returns uuid
language sql
stable
as $$
  select nullif(current_setting('request.jwt.claim.sub', true), '')::uuid;
$$;
grant usage on schema auth to anon, authenticated;
grant execute on function auth.uid() to anon, authenticated;

insert into auth.users (id) values
  ('11111111-1111-4111-8111-111111111111');

\ir ../supabase/migrations/20261118134402_create_autoearn_core_tables_with_owner_rls.sql
\ir ../supabase/migrations/20261120080000_enforce_owner_state_transitions.sql
\ir ../supabase/migrations/20261120100000_add_country_payout_metadata.sql
\ir ../supabase/migrations/20261120120000_lock_workspace_to_single_owner.sql

-- A second authenticated identity is created only after the owner is locked.
insert into auth.users (id) values
  ('22222222-2222-4222-8222-222222222222');

set role authenticated;
set request.jwt.claim.sub = '11111111-1111-4111-8111-111111111111';

insert into public.opportunities (owner_id, title, platform, url, status)
values (
  auth.uid(),
  'Lifecycle integration test',
  'AutoEarn CI',
  'https://ci.example.org/opportunity',
  'discovered'
);

do $$
declare
  v_opportunity_id bigint;
begin
  select id into v_opportunity_id
  from public.opportunities
  where url = 'https://ci.example.org/opportunity';

  update public.opportunities set status = 'ineligible' where id = v_opportunity_id;
  update public.opportunities set status = 'eligible' where id = v_opportunity_id;
  if (select status from public.opportunities where id = v_opportunity_id) <> 'eligible' then
    raise exception 'Automatic opportunity approval was not persisted.';
  end if;

  update public.opportunities
  set eligible_countries = array['Azerbaijan', 'Georgia'],
      excluded_countries = array['United States'],
      minimum_withdrawal_amount = 25.00,
      withdrawal_currency = 'USD',
      payout_methods = array['bank_transfer', 'crypto'],
      country_evidence_url = 'https://publisher.example.org/countries',
      payout_evidence_url = 'https://publisher.example.org/payouts'
  where id = v_opportunity_id;

  if not exists (
    select 1 from public.opportunities
    where id = v_opportunity_id
      and status = 'eligible'
      and eligible_countries = array['Azerbaijan', 'Georgia']
      and excluded_countries = array['United States']
      and minimum_withdrawal_amount = 25.00
      and withdrawal_currency = 'USD'
      and payout_methods = array['bank_transfer', 'crypto']
      and country_evidence_url = 'https://publisher.example.org/countries'
      and payout_evidence_url = 'https://publisher.example.org/payouts'
  ) then
    raise exception 'Country/payout metadata was not persisted or changed opportunity approval.';
  end if;
  update public.opportunities set status = 'archived' where id = v_opportunity_id;

  if (select status from public.opportunities where id = v_opportunity_id) <> 'archived' then
    raise exception 'Valid opportunity transitions were not persisted.';
  end if;

  insert into public.tasks (owner_id, opportunity_id, description)
  values (auth.uid(), v_opportunity_id, 'Verify lifecycle transitions');

  begin
    update public.tasks set status = 'completed'
    where public.tasks.opportunity_id = v_opportunity_id;
    raise exception 'Expected direct task completion to fail.';
  exception when check_violation then
    null;
  end;

  update public.tasks set status = 'approved'
  where description = 'Verify lifecycle transitions';
  update public.tasks set status = 'completed'
  where description = 'Verify lifecycle transitions';

  if not exists (
    select 1 from public.tasks
    where description = 'Verify lifecycle transitions'
      and status = 'completed'
      and approved_at is not null
      and completed_at is not null
  ) then
    raise exception 'Task approval/completion timestamps were not recorded.';
  end if;

  insert into public.rewards (owner_id, opportunity_id, amount, currency)
  values (auth.uid(), v_opportunity_id, 12.50, 'USD');

  begin
    update public.rewards set opportunity_id = null
    where amount = 12.50;
    raise exception 'Expected manual reward-link removal to fail.';
  exception when check_violation then
    null;
  end;

  update public.rewards set status = 'confirmed'
  where amount = 12.50;

  begin
    update public.rewards set status = 'paid'
    where amount = 12.50;
    raise exception 'Expected paid reward without a reference to fail.';
  exception when check_violation then
    null;
  end;

  update public.rewards
  set status = 'paid', reference = 'ci-bank-reference'
  where amount = 12.50;

  begin
    update public.rewards set reference = 'tampered-reference'
    where amount = 12.50;
    raise exception 'Expected terminal reward reference mutation to fail.';
  exception when check_violation then
    null;
  end;

  begin
    delete from public.rewards where amount = 12.50;
    raise exception 'Expected paid reward deletion to fail.';
  exception when check_violation then
    null;
  end;

  -- The FK action must clear the association while preserving the paid ledger row.
  delete from public.opportunities where id = v_opportunity_id;

  if not exists (
    select 1 from public.rewards
    where amount = 12.50 and status = 'paid'
      and reference = 'ci-bank-reference' and opportunity_id is null
  ) then
    raise exception 'Deleting an opportunity did not preserve and detach its reward ledger row.';
  end if;

  if exists (
    select 1 from public.tasks
    where description = 'Verify lifecycle transitions'
  ) then
    raise exception 'Deleting an opportunity did not cascade its dependent task.';
  end if;
end;
$$;

-- Verify that a second authenticated account cannot read or create workspace data.
set request.jwt.claim.sub = '22222222-2222-4222-8222-222222222222';
do $
begin
  if (select count(*) from public.rewards) <> 0
     or (select count(*) from public.opportunities) <> 0
     or (select count(*) from public.tasks) <> 0 then
    raise exception 'Single-owner RLS exposed workspace rows to a second account.';
  end if;

  begin
    insert into public.opportunities (owner_id, title, platform, url, status)
    values (auth.uid(), 'Unauthorized second owner', 'CI', 'https://ci.example.org/second-owner', 'eligible');
    raise exception 'Expected second authenticated account insert to be blocked.';
  exception when insufficient_privilege then
    null;
  end;
end;
$;

reset role;
