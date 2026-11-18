import { withSupabase } from "npm:@supabase/server@^1";

const corsHeaders = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers": "authorization, x-client-info, apikey, content-type",
  "Access-Control-Allow-Methods": "POST, OPTIONS",
};

// Worldwide discovery is limited to online games and prize-based entertainment.
 // Availability is offer-specific; the UI must not imply every offer works in every country.
const SEARCHES = [
  { category: "game", query: 'online games prizes paid via PayPal' },
  { category: "game", query: 'play to earn games PayPal rewards withdrawal' },
  { category: "game", query: 'online games prizes Skrill payout' },
  { category: "game", query: 'online games prizes Neteller payout' },
  { category: "game", query: 'online games rewards Payoneer payout' },
  { category: "game", query: 'online games rewards WebMoney payout' },
  { category: "game", query: 'online games prizes Payeer payout' },
  { category: "game", query: 'crypto games rewards Bitcoin USDT payout no deposit' },
  { category: "sweepstakes", query: 'free sweepstakes prize PayPal payout no purchase' },
  { category: "sweepstakes", query: 'online prize draw Skrill Neteller payout free entry' },
  { category: "sweepstakes", query: 'free online prize draw Payoneer WebMoney payout' },
  { category: "sweepstakes", query: 'crypto prize giveaway Bitcoin USDT free entry official rules' },
  { category: "wheel", query: 'spin wheel prizes PayPal cash out free' },
  { category: "wheel", query: 'lucky wheel Skrill Neteller Payeer rewards' },
  { category: "wheel", query: 'crypto spin wheel Bitcoin USDT rewards no deposit' },
  { category: "puzzle", query: 'puzzle contest prizes PayPal payout' },
  { category: "puzzle", query: 'brain games competition Skrill Neteller payout' },
  { category: "puzzle", query: 'puzzle competition crypto Bitcoin USDT prizes' },
  { category: "iq-test", query: 'IQ quiz contest PayPal prize payout' },
  { category: "iq-test", query: 'brain test competition Skrill Neteller prizes' },
  { category: "instant-win", query: 'free instant win game PayPal prize no purchase' },
  { category: "instant-win", query: 'scratch game prizes crypto Bitcoin USDT free entry' },
];

function json(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { ...corsHeaders, "Content-Type": "application/json" },
  });
}

Deno.serve((req: Request) => {
  if (req.method === "OPTIONS") return new Response("ok", { headers: corsHeaders });
  if (req.method !== "POST") return json({ error: "Method not allowed" }, 405);

  return withSupabase({ auth: "user" }, async (_req, ctx) => {
    // @supabase/server exposes the authenticated user ID as userClaims.id.
    const ownerId = ctx.userClaims?.id;
    if (!ownerId) return json({ error: "Authenticated user identity is missing." }, 401);

    const found: Array<Record<string, unknown>> = [];
    const errors: string[] = [];
    const searchStats: Array<{ category: string; query: string; results: number; status: number }> = [];

    for (let index = 0; index < SEARCHES.length; index++) {
      const search = SEARCHES[index];
      try {
        // Anonymous Mwmbl access is limited to one request per second per IP.
        if (index > 0) await new Promise((resolve) => setTimeout(resolve, 1100));
        const endpoint = new URL("https://api.mwmbl.org/api/v1/search/");
        endpoint.searchParams.set("s", search.query);
        const response = await fetch(endpoint, { headers: { "Accept": "application/json" } });
        if (!response.ok) {
          errors.push(`${search.category} (${search.query}): Mwmbl returned ${response.status}`);
          searchStats.push({ category: search.category, query: search.query, results: 0, status: response.status });
          continue;
        }
        const payload = await response.json();
        const results = Array.isArray(payload) ? payload : [];
        searchStats.push({ category: search.category, query: search.query, results: results.length, status: response.status });
        if (!Array.isArray(payload)) errors.push(`${search.query}: unexpected response format`);
        for (const item of results) {
          try {
            const parsed = new URL(item.url);
            if (parsed.protocol !== "https:") continue;
            const hostname = parsed.hostname.replace(/^www\./, "");
            const title = String(Array.isArray(item.title) ? item.title.map((part: { value?: string }) => part.value || "").join("") : item.title || hostname).trim().slice(0, 160);
            const description = String(Array.isArray(item.extract) ? item.extract.map((part: { value?: string }) => part.value || "").join("") : item.extract || "No reward details provided by search result.").trim().slice(0, 900);
            if (title.length < 2) continue;
            const payoutText = (title + " " + description + " " + item.url).toLowerCase();
            const walletMatches = [
              /\bpaypal\b/.test(payoutText) ? "PayPal" : null,
              /\bskrill\b/.test(payoutText) ? "Skrill" : null,
              /\bneteller\b/.test(payoutText) ? "Neteller" : null,
              /\bpayeer\b/.test(payoutText) ? "Payeer" : null,
              /\bpayoneer\b/.test(payoutText) ? "Payoneer" : null,
              /\bwebmoney\b/.test(payoutText) ? "WebMoney" : null,
              /bitcoin|\bbtc\b|\busdt\b|ethereum|\beth\b|crypto|cryptocurrency|tether|\busdc\b/.test(payoutText) ? "Crypto" : null,
            ].filter((value): value is string => Boolean(value));
            if (walletMatches.length === 0) continue;
            found.push({
              owner_id: ownerId,
              title,
              platform: hostname.slice(0, 100),
              url: parsed.toString(),
              category: search.category,
              reward_description: description,
              eligibility: `Payout wallet mentioned in search result: ${walletMatches.join(", ")}. This is NOT confirmation that withdrawals are supported in your country; verify on the official payout and terms pages.`,
              terms_url: "",
              status: "discovered",
              score: 0,
              notes: `Accepted wallet keyword(s) found in search snippet: ${walletMatches.join(", ")}. Wallet support and country eligibility are unverified. Confirm minimum withdrawal, fees, KYC and official rules. Never deposit or pay to unlock a prize.`,
            });
          } catch { /* Ignore malformed result URLs. */ }
        }
      } catch (error) {
        errors.push(`${search.category}: ${String(error).slice(0, 180)}`);
      }
    }

    const unique = [...new Map(found.map((row) => [row.url, row])).values()];
    if (!unique.length) return json({ saved: 0, scanned: 0, searches: searchStats, errors, message: "No candidate pages found. Search diagnostics are included." });

    const { data, error } = await ctx.supabase
      .from("opportunities")
      .upsert(unique, { onConflict: "owner_id,url", ignoreDuplicates: true })
      .select("id");

    if (error) return json({ error: error.message }, 500);
    return json({
      saved: data?.length || 0,
      scanned: unique.length,
      categories: [...new Set(SEARCHES.map((item) => item.category))],
      searches: searchStats,
      errors,
      message: "Candidates saved for your review. They are not verified offers.",
    });
  })(req);
});
