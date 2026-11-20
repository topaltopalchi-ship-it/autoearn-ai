import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const html = readFileSync(new URL("../static/index.html", import.meta.url), "utf8");
const app = readFileSync(new URL("../static/app.js", import.meta.url), "utf8");

test("every literal app.js getElementById helper reference exists in the workspace HTML", () => {
  const ids = new Set([...html.matchAll(/\bid=["']([^"']+)["']/g)].map((match) => match[1]));
  const referenced = new Set([...app.matchAll(/\$\(["']([^"']+)["']\)/g)].map((match) => match[1]));
  const missing = [...referenced].filter((id) => !ids.has(id));
  assert.deepEqual(missing, [], `Missing workspace element IDs: ${missing.join(", ")}`);
});

test("owner-only access and manual task controls remain visible in the HTML contract", () => {
  assert.match(html, /id="auth-form"/);
  assert.match(html, /id="auth-email"/);
  assert.match(html, /id="auth-password"/);
  assert.match(html, /New account registration is intentionally unavailable/);
  assert.match(html, /id="discover-opportunities"/);
  assert.match(html, /id="opportunity-dialog"/);
  assert.match(html, /id="reward-dialog"/);
  assert.match(html, /id="sign-out"/);
  assert.doesNotMatch(html, /service_role|SUPABASE_SERVICE_ROLE_KEY/i);
});

test("single-owner workspace exposes password sign-in only, never public sign-up", () => {
  assert.match(html, /OWNER ACCESS ONLY/);
  assert.match(html, /Sign in with the owner account created in Supabase/);
  assert.match(app, /supabase\.auth\.signInWithPassword/);
  assert.match(app, /supabase\.auth\.signOut/);
  assert.doesNotMatch(app, /supabase\.auth\.(?:signUp|signInWithOtp|signInWithOAuth)\s*\(/);
  assert.doesNotMatch(html, /name=["'](?:register|signup)["']|id=["'][^"']*(?:register|signup)[^"']*["']/i);
});

test("metadata and local helper scripts load before the application controller", () => {
  const ordered = [
    /src="\.\/config\.js(?:\?[^"]*)?"/,
    /src="\.\/reward-ledger\.js(?:\?[^"]*)?"/,
    /src="\.\/due-diligence\.js(?:\?[^"]*)?"/,
    /src="\.\/discovery-provenance\.js(?:\?[^"]*)?"/,
    /src="\.\/opportunity-economics\.js(?:\?[^"]*)?"/,
    /src="\.\/app\.js(?:\?[^"]*)?"/,
    /src="\.\/game-agent\.js(?:\?[^"]*)?"/,
    /src="\.\/puzzle\.js(?:\?[^"]*)?"/,
  ];
  let previous = -1;
  for (const marker of ordered) {
    const match = marker.exec(html);
    assert.ok(match, `Missing script reference: ${marker}`);
    const index = match.index;
    assert.ok(index > previous, `Script order violation at: ${marker}`);
    previous = index;
  }
});

const netlify = readFileSync(new URL("../netlify.toml", import.meta.url), "utf8");
const deploy = readFileSync(new URL("../.github/workflows/netlify-deploy.yml", import.meta.url), "utf8");

test("Netlify response headers retain the static app security baseline", () => {
  for (const header of [
    "X-Content-Type-Options = \"nosniff\"",
    "X-Frame-Options = \"DENY\"",
    "frame-ancestors 'none'",
    "object-src 'none'",
    "base-uri 'self'",
    "Cache-Control = \"no-store\"",
  ]) assert.ok(netlify.includes(header), `Missing security header/directive: ${header}`);
  assert.match(netlify, /publish = "static"/);
});

test("production hosting deploy stays manual and restricted to develop", () => {
  assert.match(deploy, /workflow_dispatch:/);
  assert.match(deploy, /if: github\.ref == 'refs\/heads\/develop'/);
  assert.match(deploy, /netlify-cli@27\.20\.1/);
  assert.match(deploy, /NETLIFY_AUTH_TOKEN/);
  assert.match(deploy, /NETLIFY_SITE_ID/);
  assert.doesNotMatch(deploy, /on:\s*\n\s*push:/);
});
