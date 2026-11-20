import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const html = readFileSync(new URL("../static/index.html", import.meta.url), "utf8");
const app = readFileSync(new URL("../static/app.js", import.meta.url), "utf8");

test("every literal app.js getElementById helper reference exists in the workspace HTML", () => {
  const ids = new Set([...html.matchAll(/\\bid=["']([^"']+)["']/g)].map((match) => match[1]));
  const referenced = new Set([...app.matchAll(/\\$\\(["']([^"']+)["']\\)/g)].map((match) => match[1]));
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

test("metadata and local helper scripts load before the application controller", () => {
  const ordered = [
    'src="./config.js"',
    'src="./reward-ledger.js"',
    'src="./due-diligence.js"',
    'src="./discovery-provenance.js"',
    'src="./opportunity-economics.js"',
    'src="./app.js"',
    'src="./game-agent.js"',
    'src="./puzzle.js"',
  ];
  let previous = -1;
  for (const marker of ordered) {
    const index = html.indexOf(marker);
    assert.notEqual(index, -1, `Missing script reference: ${marker}`);
    assert.ok(index > previous, `Script order violation at: ${marker}`);
    previous = index;
  }
});
