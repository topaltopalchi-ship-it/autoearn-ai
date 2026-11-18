# AutoEarn AI

A private, owner-only opportunity discovery and reward-tracking workspace.

The web interface connects directly to Supabase Auth and the three owner-protected tables. The browser uses only the project's publishable key; Row Level Security remains the database authorization boundary. It does not promise income or automate clicks, gameplay, ad views, referrals, spam, account creation, or platform activity. The guided-session button only opens the official HTTPS page in a new tab and records that the owner started a session.

## Current implementation

- Supabase email/password sign-in (no public registration UI).
- Supabase-backed opportunities, tasks, and rewards.
- Owner ID is attached to every inserted record; database RLS validates ownership.
- Owner-started guided sessions open the official HTTPS page and are recorded as approved tasks; third-party gameplay remains manual.\n- Local 3×3 sliding-puzzle lab demonstrates automatic solving on a self-contained demo board; it has no rewards, external accounts, or platform interaction.\n- No automatic login, signup, personal-data submission, purchases, deposits, or gameplay. Any future platform-specific assistance must respect the platform terms and request consent before sensitive actions.\n- Human approval is required before a task can be marked completed.
- Explainable opportunity metadata score; not a guarantee of legitimacy or payment.
- The FastAPI host serves the static app and a health endpoint only; no unauthenticated SQLite CRUD API is exposed. User data is stored in Supabase.

## Supabase setup

1. In Supabase Dashboard, open **Authentication → Sign In / Providers** and turn off **Allow new users to sign up**. This makes the project invite-only; existing users can still sign in.
2. Open **Authentication → Users** and create/invite only your own email address.
3. Open **Project Settings → API Keys** and copy the **publishable** key (starts with `sb_publishable_`). Never copy a secret or service_role key into the website.
4. Put that publishable key in `static/config.js` as the value of `publishableKey`.
5. Deploy the static `static/` directory to a static host over HTTPS. Configure the host to serve `index.html` at the site root.

The Supabase project URL is already configured in `static/config.js`. No database password or service-role key is required in the browser.

## Development

Requires Python 3.10 or newer.

```bash
pip install -r requirements.txt
pytest -q
```

## Security

The `opportunities`, `tasks`, and `rewards` tables have Row Level Security policies that scope rows to `auth.uid()`. Do not weaken or disable these policies. A publishable key is not an authorization mechanism by itself; the authenticated user JWT and RLS policies control access.

## Scope and risk

Scores use only metadata entered by the owner. They are not proof that a platform is legitimate or that a reward will be paid. Verify eligibility, country restrictions, withdrawal thresholds, and platform terms before participating. Website discovery and analysis must respect site terms, robots policies, privacy, and applicable law.
