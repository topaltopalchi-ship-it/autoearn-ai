import { withSupabase } from "npm:@supabase/server@^1";

const corsHeaders = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers": "authorization, x-client-info, apikey, content-type",
  "Access-Control-Allow-Methods": "POST, OPTIONS",
};

// Worldwide discovery is limited to online games and prize-based entertainment.
 // Availability is offer-specific; the UI must not imply every offer works in every country.
const SEARCHES = [
  { category: "game", query: 'free online games win real prizes no purchase worldwide' },
  { category: "game", query: 'free play games rewards cash prizes international' },
  { category: "game", query: 'juegos gratis ganar premios dinero sin compra' },
  { category: "sweepstakes", query: 'free online sweepstakes enter win prizes no purchase international' },
  { category: "sweepstakes", query: 'concursos sorteos gratis premios online sin compra' },
  { category: "wheel", query: 'free spin wheel win prizes daily no purchase online' },
  { category: "wheel", query: 'ruleta de premios gratis girar ganar premios online' },
  { category: "puzzle", query: 'free online puzzle contest win cash prizes skill challenge' },
  { category: "puzzle", query: 'free puzzle games competitions prizes online' },
  { category: "iq-test", query: 'free online brain games iq quiz challenge prize contest' },
  { category: "iq-test", query: 'free intelligence test puzzle competition prizes online' },
  { category: "instant-win", query: 'free instant win games scratch cards reveal win no purchase' },
  { category: "instant-win", query: 'juegos premios instantaneos gratis rasca y gana sin compra' },
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
              eligibility: "Worldwide discovery candidate. Country availability, age limits and prize eligibility are NOT verified. Confirm official rules and free-entry route before participating.",
              terms_url: "",
              status: "discovered",
              score: 0,
              notes: "Found by a game-and-prize focused search. Not verified or endorsed. Prioritize no-purchase entry; do not pay, deposit, buy tickets or share payment details. Check official rules, eligible countries, odds and prize delivery first.",
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
