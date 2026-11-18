import { withSupabase } from "npm:@supabase/server@^1";

const corsHeaders = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers": "authorization, x-client-info, apikey, content-type",
  "Access-Control-Allow-Methods": "POST, OPTIONS",
};

const SEARCHES = [
  { category: "game", query: 'Deutschland Spiele Apps Geld verdienen Belohnungen Auszahlung' },
  { category: "paid-task", query: 'Deutschland Microtasks bezahlte Aufgaben Plattform Auszahlung' },
  { category: "survey", query: 'Deutschland bezahlte Umfragen seriös Auszahlung' },
  { category: "signup-offer", query: 'Deutschland Neukunden Bonus Prämie Anmeldung Teilnahmebedingungen' },
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

    for (let index = 0; index < SEARCHES.length; index++) {
      const search = SEARCHES[index];
      try {
        // Anonymous Mwmbl access is limited to one request per second per IP.
        if (index > 0) await new Promise((resolve) => setTimeout(resolve, 1100));
        const endpoint = new URL("https://api.mwmbl.org/api/v1/search/");
        endpoint.searchParams.set("s", search.query);
        const response = await fetch(endpoint, { headers: { "Accept": "application/json" } });
        if (!response.ok) {
          errors.push(`${search.category}: Mwmbl returned ${response.status}`);
          continue;
        }
        const payload = await response.json();
        for (const item of (Array.isArray(payload) ? payload : [])) {
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
