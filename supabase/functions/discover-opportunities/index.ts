import { withSupabase } from "npm:@supabase/server@^1";

const corsHeaders = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers": "authorization, x-client-info, apikey, content-type",
  "Access-Control-Allow-Methods": "POST, OPTIONS",
};

const SEARCHES = [
  { category: "game", query: 'Germany play games earn rewards app official offer Germany' },
  { category: "paid-task", query: 'Germany microtask paid tasks platform official signup' },
  { category: "survey", query: 'Germany paid online surveys official panel register' },
  { category: "signup-offer", query: 'Germany new user signup bonus reward offer official terms' },
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
    const apiKey = Deno.env.get("BRAVE_SEARCH_API_KEY");
    if (!apiKey) return json({
      error: "Discovery is not configured yet. Add BRAVE_SEARCH_API_KEY to Supabase Edge Function secrets.",
      needsSetup: true,
    }, 503);

    // @supabase/server exposes the authenticated user ID as userClaims.id.
    const ownerId = ctx.userClaims?.id;
    if (!ownerId) return json({ error: "Authenticated user identity is missing." }, 401);

    const found: Array<Record<string, unknown>> = [];
    const errors: string[] = [];

    for (const search of SEARCHES) {
      try {
        const endpoint = new URL("https://api.search.brave.com/res/v1/web/search");
        endpoint.searchParams.set("q", search.query);
        endpoint.searchParams.set("country", "DE");
        endpoint.searchParams.set("search_lang", "de");
        endpoint.searchParams.set("count", "8");
        const response = await fetch(endpoint, {
          headers: { "Accept": "application/json", "X-Subscription-Token": apiKey },
        });
        if (!response.ok) {
          errors.push(`${search.category}: search provider returned ${response.status}`);
          continue;
        }
        const payload = await response.json();
        for (const item of (payload.web?.results || [])) {
          try {
            const parsed = new URL(item.url);
            if (parsed.protocol !== "https:") continue;
            const hostname = parsed.hostname.replace(/^www\./, "");
            const title = String(item.title || hostname).trim().slice(0, 160);
            const description = String(item.description || "No reward details provided by search result.").trim().slice(0, 900);
            if (title.length < 2) continue;
            found.push({
              owner_id: ownerId,
              title,
              platform: hostname.slice(0, 100),
              url: parsed.toString(),
              category: search.category,
              reward_description: description,
              eligibility: "Germany-targeted search result. Confirm country, age, payout method and eligibility on the official site.",
              terms_url: "",
              status: "discovered",
              score: 0,
              notes: "Automatically found by web search. Not verified or endorsed. Check the official terms, fees, payout conditions and current availability before participating.",
            });
          } catch { /* Ignore malformed result URLs. */ }
        }
      } catch (error) {
        errors.push(`${search.category}: ${String(error).slice(0, 180)}`);
      }
    }

    const unique = [...new Map(found.map((row) => [row.url, row])).values()];
    if (!unique.length) return json({ saved: 0, scanned: 0, errors, message: "No candidate pages found. Try again later." });

    const { data, error } = await ctx.supabase
      .from("opportunities")
      .upsert(unique, { onConflict: "owner_id,url", ignoreDuplicates: true })
      .select("id");

    if (error) return json({ error: error.message }, 500);
    return json({
      saved: data?.length || 0,
      scanned: unique.length,
      categories: SEARCHES.map((item) => item.category),
      errors,
      message: "Candidates saved for your review. They are not verified offers.",
    });
  })(req);
});
