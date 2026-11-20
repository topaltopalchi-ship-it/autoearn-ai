-- Informational country and payout metadata for owner-entered opportunities.
-- These fields do not approve, reject, or authorize any opportunity or automation.
alter table public.opportunities
  add column if not exists eligible_countries text[] not null default '{}',
  add column if not exists excluded_countries text[] not null default '{}',
  add column if not exists minimum_withdrawal_amount numeric(14,2)
    check (minimum_withdrawal_amount is null or minimum_withdrawal_amount >= 0),
  add column if not exists withdrawal_currency text not null default 'USD'
    check (withdrawal_currency ~ '^[A-Z]{3}$'),
  add column if not exists payout_methods text[] not null default '{}',
  add column if not exists country_evidence_url text not null default '',
  add column if not exists payout_evidence_url text not null default '';

comment on column public.opportunities.eligible_countries is
  'Owner-entered country claims; not independently verified and never an access gate.';
comment on column public.opportunities.excluded_countries is
  'Owner-entered country restriction claims; informational only.';
comment on column public.opportunities.minimum_withdrawal_amount is
  'Advertised minimum withdrawal amount; not a guarantee of payout.';
comment on column public.opportunities.payout_methods is
  'Advertised payout methods; availability and successful withdrawal are not verified.';
comment on column public.opportunities.country_evidence_url is
  'Public HTTPS source supplied by owner for country information; content is not verified.';
comment on column public.opportunities.payout_evidence_url is
  'Public HTTPS source supplied by owner for payout information; content is not verified.';
