import { withSupabase } from "npm:@supabase/server@^1";

const corsHeaders = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers": "authorization, x-client-info, apikey, content-type",
  "Access-Control-Allow-Methods": "POST, OPTIONS",
};

// Worldwide discovery: search broadly in English and several major languages.
 // Availability is offer-specific; the UI must not imply every offer works in every country.
const SEARCHES = [
  // Short queries work better with a full-text index than long, restrictive phrases.
  { category: "game", query: 'play to earn' },
  { category: "game", query: 'paid games rewards' },
  { category: "game", query: 'juegos ganar dinero' },
  { category: "paid-task", query: 'microtasks' },
  { category: "paid-task", query: 'online paid tasks' },
  { category: "paid-task", query: 'micro tâches rémunérées' },
  { category: "survey", query: 'paid surveys' },
  { category: "survey", query: 'encuestas pagadas' },
  { category: "signup-offer", query: 'signup bonus' },
  { category: "signup-offer", query: 'referral rewards' },
  { category: "signup-offer", query: 'bonus parrainage' },
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
            found.push({
              owner_id: ownerId,
              title,
              platform: hostname.slice(0, 100),
              url: parsed.toString(),
              category: search.category,
              reward_description: description,
              eligibility: "Found through worldwide search. Country availability is not verified; confirm eligible countries, age limits, payout methods and restrictions on the official site.",
              terms_url: "",
              status: "discovered",
              score: 0,
              notes: "Automatically found through multilingual worldwide web search. Not verified or endorsed. Check the official terms, eligible countries, fees, payout conditions and current availability before participating.",
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
