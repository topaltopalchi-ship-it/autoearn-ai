import { withSupabase } from "npm:@supabase/server@^1";
import { evaluateCandidate } from "./filters.ts";

const corsHeaders = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers": "authorization, x-client-info, apikey, content-type",
  "Access-Control-Allow-Methods": "POST, OPTIONS",
};

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
    const ownerId = ctx.userClaims?.id;
    if (!ownerId) return json({ error: "Authenticated user identity is missing." }, 401);

    const found: Array<Record<string, unknown>> = [];
    const errors: string[] = [];
    const rejected = { invalid_url: 0, excluded_category: 0, no_accepted_wallet: 0, missing_reward_evidence: 0, missing_payout_evidence: 0 };
    let acceptedCandidates = 0;
    const searchStats: Array<{ category: string; query: string; results: number; status: number }> = [];

    for (let index = 0; index < SEARCHES.length; index++) {
      const search = SEARCHES[index];
      try {
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
          const rawUrl = String(item?.url || "");
          const title = String(Array.isArray(item?.title)
            ? item.title.map((part: { value?: string }) => part.value || "").join("")
            : item?.title || "").trim().slice(0, 160);
          const description = String(Array.isArray(item?.extract)
            ? item.extract.map((part: { value?: string }) => part.value || "").join("")
            : item?.extract || "No reward details provided by search result.").trim().slice(0, 900);
          if (title.length < 2) continue;

          const decision = evaluateCandidate(rawUrl, title, description);
          if (!decision.accepted) {
            rejected[decision.reason]++;
            continue;
          }

          acceptedCandidates++;
          const hostname = new URL(decision.url).hostname.replace(/^www\./, "");
          const walletMatches = decision.wallets;
          found.push({
            owner_id: ownerId,
            title,
            platform: hostname.slice(0, 100),
            url: decision.url,
            category: search.category,
            reward_description: description,
            eligibility: `Payout wallet mentioned in search result: ${walletMatches.join(", ")}. This is NOT confirmation that withdrawals are supported in your country; verify on the official payout and terms pages.`,
            terms_url: "",
            status: "discovered",
            score: 0,
            notes: `Accepted wallet keyword(s) found in search snippet: ${walletMatches.join(", ")}. Wallet support and country eligibility are unverified. Confirm minimum withdrawal, fees, KYC and official rules. Never deposit or pay to unlock a prize.`,
          });
        }
      } catch (error) {
        errors.push(`${search.category}: ${String(error).slice(0, 180)}`);
      }
    }

    const unique = [...new Map(found.map((row) => [row.url, row])).values()];
    const diagnostics = {
      accepted_candidates: acceptedCandidates,
      rejected,
      searches: searchStats,
      errors,
    };

    if (!unique.length) {
      return json({
        saved: 0,
        scanned: 0,
        ...diagnostics,
        message: "No candidate pages found. Search diagnostics are included.",
      });
    }

    const { data, error } = await ctx.supabase
      .from("opportunities")
      .upsert(unique, { onConflict: "owner_id,url", ignoreDuplicates: true })
      .select("id");

    if (error) return json({ error: error.message }, 500);
    return json({
      saved: data?.length || 0,
      scanned: unique.length,
      ...diagnostics,
      categories: [...new Set(SEARCHES.map((item) => item.category))],
      message: "Candidates saved for your review. They are not verified offers.",
    });
  })(req);
});
