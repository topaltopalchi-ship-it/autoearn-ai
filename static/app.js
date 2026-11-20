const $ = (id) => document.getElementById(id);
const cfg = window.AUTOEARN_CONFIG || {};
function safePublicHttpsUrl(value){
  return window.AutoEarnDueDiligence?.safePublicHttpsUrl(value) || null;
}
const configured = Boolean(cfg.url && cfg.publishableKey && !cfg.publishableKey.includes("PASTE_"));
let supabase = null;
let currentUser = null;
let opportunities = [];
let tasks = [];
let rewards = [];
const DISCOVERY_CATEGORIES = new Set(["game","sweepstakes","wheel","raffle","prediction","puzzle","iq-test","instant-win"]);
const CATEGORY_LABELS = { game:"Game", sweepstakes:"Sweepstakes", wheel:"Spin wheel", raffle:"Raffle", prediction:"Prediction contest", puzzle:"Puzzle", "iq-test":"Quiz", "instant-win":"Instant win" };
function categoryLabel(category){ return window.AutoEarnDueDiligence?.formatCategoryLabels(category,CATEGORY_LABELS) || "Other"; }
function discoveryProvenanceHtml(opportunity){
  const provenance=window.AutoEarnDiscoveryProvenance?.extractDiscoveryProvenance(opportunity.notes||"");
  if(!provenance)return "";
  const timestamp=Date.parse(provenance.discovered_at);
  const discovered=Number.isFinite(timestamp)?new Date(timestamp).toLocaleString():"date unavailable";
  return "<br><strong>Discovery source:</strong> "+esc(provenance.source||"Search")+
    " · "+esc(discovered)+(provenance.search_query?"<br><strong>Search query:</strong> "+esc(provenance.search_query):"")+
    (provenance.excerpt?"<details><summary>View original discovery excerpt</summary><small>"+esc(provenance.excerpt)+"</small></details>":"");
}
const money = (n,c="USD") => new Intl.NumberFormat(undefined,{style:"currency",currency:c}).format(Number(n||0));
function toast(message){const el=$("toast");el.textContent=message;el.classList.add("show");setTimeout(()=>el.classList.remove("show"),2600)}
function esc(s=""){return String(s).replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]))}
function showAuth(message=""){
  $("auth-screen").hidden=false;$("workspace").hidden=true;
  $("auth-message").textContent=message;
}
function showWorkspace(){
  $("auth-screen").hidden=true;$("workspace").hidden=false;
  $("signed-in-as").textContent=currentUser?.email||"";
}
function fail(error){console.error(error);toast(error.message||"Something went wrong")}
async function loadData(){
  const [o,t,r]=await Promise.all([
    supabase.from("opportunities").select("*").order("created_at",{ascending:false}),
    supabase.from("tasks").select("*, opportunities(title,platform)").order("created_at",{ascending:false}),
    supabase.from("rewards").select("*, opportunities(title)").order("created_at",{ascending:false})
  ]);
  for(const result of [o,t,r]) if(result.error) throw result.error;
  const ownedCandidates=(o.data||[]).filter(item=>DISCOVERY_CATEGORIES.has(item.category));
  const pendingIds=ownedCandidates.filter(item=>["discovered","reviewing","ineligible"].includes(item.status)).map(item=>item.id);
  if(pendingIds.length){
    const {error}=await supabase.from("opportunities").update({status:"eligible"}).in("id",pendingIds).in("status",["discovered","reviewing","ineligible"]);
    if(error)throw error;
  }
  opportunities=ownedCandidates.map(item=>["discovered","reviewing","ineligible"].includes(item.status)?{...item,status:"eligible"}:item);tasks=t.data||[];rewards=r.data||[];
  render();
}
function formatRewardTotals(rows){
  const totals=AutoEarnRewardLedger.sumByCurrency(rows);
  return Object.entries(totals).sort(([a],[b])=>a.localeCompare(b)).map(([currency,total])=>money(total,currency)).join(" · ")||"—";
}
function render(){
  const awaiting=tasks.filter(t=>t.status==="pending_approval").length;
  const ledger=AutoEarnRewardLedger.summarize(rewards);
  $("stat-opps").textContent=opportunities.length;$("stat-tasks").textContent=tasks.length;
  $("stat-approval").textContent=awaiting;$("stat-paid").textContent=formatRewardTotals(ledger.paid);
  $("stat-pending").textContent="Pending: "+formatRewardTotals(ledger.pending);
  $("stat-confirmed").textContent="Confirmed: "+formatRewardTotals(ledger.confirmed);
  renderOpportunities();renderTasks();renderRewards();fillRewardOptions();
}
function renderOpportunities(){
  const q=$("search").value.toLowerCase(),status=$("filter").value;
  const rows=opportunities.filter(o=>(!status||o.status===status)&&[o.title,o.platform,o.category].some(x=>(x||"").toLowerCase().includes(q)));
  const sortMode=$("opportunity-sort")?.value||"evidence";
  const sortedRows=sortMode==="economics"?window.AutoEarnOpportunityEconomics.sortByExpectedHourlyValue(rows):window.AutoEarnDueDiligence.sortOpportunities(rows,sortMode);
  const summary=window.AutoEarnDueDiligence.summarizeOpportunities(rows);
  $("opportunity-summary").textContent=summary.total
    ? `Showing ${summary.total} opportunities · ${summary.scored} scored · Average evidence completeness: ${summary.averageScore===null?"—":summary.averageScore+"/100"} · High: ${summary.counts.high} · Medium: ${summary.counts.medium} · Low disclosure: ${summary.counts.low} · Unscored: ${summary.counts.unscored}`
    : "No opportunities match the current search and status filters.";
  $("opportunity-list").innerHTML=sortedRows.length?sortedRows.map(o=>{
    const platformUrl=safePublicHttpsUrl(o.url);
    const termsUrl=o.terms_url?safePublicHttpsUrl(o.terms_url):null;
    const platformLink=platformUrl?'<a href="'+esc(platformUrl)+'" target="_blank" rel="noopener noreferrer">Open platform ↗</a>':'<span>Platform link unavailable (invalid HTTPS URL)</span>';
    const termsLink=termsUrl?' · <a href="'+esc(termsUrl)+'" target="_blank" rel="noopener noreferrer">Terms ↗</a>':'';
    const economics=window.AutoEarnOpportunityEconomics.extractOwnerEstimate(o.notes||"");
    const economicsLine=economics?"<br><strong>Owner-estimated net value:</strong> "+money(economics.expectedNetPerHour,economics.currency)+"/hour · "+money(economics.expectedNet,economics.currency)+" total expected net (not verified or guaranteed)":"";
    return `<div class="item"><div><h3>${esc(o.title)} <span class="pill">${esc(o.status==="eligible"?"Auto-approved · not verified":o.status)}</span></h3><p>${esc(o.platform)} · ${esc(categoryLabel(o.category))} · Metadata score ${esc(o.score)}/60<br>${platformLink}${termsLink}<br>${esc(o.reward_description||"No reward details entered")}${economicsLine}${discoveryProvenanceHtml(o)}<br><strong>Access:</strong> Approved for manual opening only; payout and legitimacy are not verified.</p></div><div class="item-actions"><button class="primary" data-start="${esc(o.id)}" ${!AutoEarnDueDiligence.canStartGuidedSession(o)?"disabled":""}>Open manually</button></div></div>`;
  }).join(""):'<div class="empty">No matching opportunities.</div>';
  $("opportunity-list").querySelectorAll("[data-start]").forEach(b=>b.onclick=()=>createTask(Number(b.dataset.start)));
}
async function createTask(id){
  const opportunity=opportunities.find(item=>Number(item.id)===Number(id));
  if(!opportunity)return toast("Opportunity not found. Refresh and try again.");
  if(!AutoEarnDueDiligence.canStartGuidedSession(opportunity))return toast("This opportunity is not available for manual access.");
  let target;
  try {
    const safeUrl=safePublicHttpsUrl(opportunity.url);
    if(!safeUrl) throw new Error("Only public HTTPS platform links can be opened.");
    target=new URL(safeUrl);
  } catch(error) { return toast(error.message||"Invalid platform URL."); }
  if(!confirm("Start a guided session for this opportunity? AutoEarn will only open the official HTTPS page and record the session. It will NOT sign up, log in, play automatically, submit information, or spend money."))return;
  const opened=window.open(target.href,"_blank");
  if(!opened){toast("Allow pop-ups for AutoEarn AI, then tap Open manually again.");return;}
  opened.opener=null;
  const description="Guided session opened by owner. Follow platform rules manually; no automated gameplay or spending.";
  const {error}=await supabase.from("tasks").insert({
    owner_id:currentUser.id,
    opportunity_id:id,
    description,
    status:"pending_approval"
  });
  if(error)return fail(error);
  toast("Guided session recorded. Follow the platform rules manually.");
  await loadData();
}
function openRewardForOpportunity(id){
  const opportunity=opportunities.find(item=>Number(item.id)===Number(id));
  if(!opportunity)return toast("Opportunity not found. Refresh and try again.");
  const form=$("reward-form");
  form.reset();
  $("reward-opportunity").value=String(id);
  form.elements.status.value="pending";
  $("reward-dialog").showModal();
}
async function transitionTask(id,expectedStatus,nextStatus,timestampField){
  const allowed={pending_approval:{approved:"approved_at"},approved:{completed:"completed_at"}};
  if(!Object.hasOwn(allowed[expectedStatus]||{},nextStatus)||allowed[expectedStatus][nextStatus]!==timestampField){
    return toast("Invalid task status transition.");
  }
  const {data,error}=await supabase.from("tasks").update({status:nextStatus,[timestampField]:new Date().toISOString()}).eq("id",id).eq("status",expectedStatus).select("id").maybeSingle();
  if(error)return fail(error);
  if(!data)return toast("Task status changed elsewhere. Refresh and try again.");
  await loadData();
}
function renderTasks(){
  $("task-list").innerHTML=tasks.length?tasks.map(t=>{
    const completedAt=t.completed_at?new Date(t.completed_at).toLocaleString():"";
    const dateLine=t.status==="completed"&&completedAt?"<br><strong>Completed:</strong> "+esc(completedAt):"";
    const rewardAction=t.status==="completed"&&t.opportunity_id?'<button class="secondary" data-reward-opportunity="'+esc(t.opportunity_id)+'">Record actual reward</button>':"";
    return `<div class="item"><div><h3>${esc(t.description)}</h3><p>${esc(t.opportunities?.title||"Opportunity")} · ${esc(t.opportunities?.platform||"")} · ${esc(t.status)}${dateLine}</p></div><div class="item-actions">${t.status==="pending_approval"?'<button class="primary" data-approve="'+esc(t.id)+'">Approve task</button>':''}${t.status==="approved"?'<button class="secondary" data-complete="'+esc(t.id)+'">Mark completed</button>':''}${rewardAction}</div></div>`;
  }).join(""):'<div class="empty">No tasks yet. Create a task from an opportunity.</div>';
  $("task-list").querySelectorAll("[data-approve]").forEach(b=>b.onclick=async()=>{if(!confirm("Approve this task? You remain responsible for following platform rules."))return;await transitionTask(b.dataset.approve,"pending_approval","approved","approved_at")});
  $("task-list").querySelectorAll("[data-complete]").forEach(b=>b.onclick=async()=>{await transitionTask(b.dataset.complete,"approved","completed","completed_at")});
  $("task-list").querySelectorAll("[data-reward-opportunity]").forEach(b=>b.onclick=()=>openRewardForOpportunity(Number(b.dataset.rewardOpportunity)));
}
function renderRewards(){
  const ledger=window.AutoEarnRewardLedger;
  const summary=ledger?.summarize(rewards)||{paid:[],pending:[],confirmed:[]};
  const paidTotals=ledger?.sumByCurrency(summary.paid)||{};
  const pendingTotals=ledger?.sumByCurrency(summary.pending)||{};
  const confirmedTotals=ledger?.sumByCurrency(summary.confirmed)||{};
  const currencies=[...new Set([...Object.keys(paidTotals),...Object.keys(pendingTotals),...Object.keys(confirmedTotals)])].sort();
  $("reward-summary").innerHTML=currencies.length?currencies.map(currency=>`<div class="item"><div><strong>${esc(currency)}</strong><p>Paid with reference: ${money(paidTotals[currency]||0,currency)} · Confirmed: ${money(confirmedTotals[currency]||0,currency)} · Pending: ${money(pendingTotals[currency]||0,currency)}</p></div></div>`).join(""):'<p class="translator-privacy">No validated reward totals yet. Paid totals include only records with a payment reference; all figures are manually entered, not bank-verified.</p>';
  const monthly=ledger?.summarizeByMonth(rewards)||[];
  $("reward-monthly").innerHTML=monthly.length?monthly.slice(0,6).map(group=>{
    const label=new Intl.DateTimeFormat(undefined,{month:"long",year:"numeric",timeZone:"UTC"}).format(new Date(group.month+"-01T00:00:00Z"));
    const detail=Object.entries(group.currencies).map(([currency,total])=>`${esc(currency)} · Paid ${money(total.paid,currency)} · Confirmed ${money(total.confirmed,currency)} · Pending ${money(total.pending,currency)}`).join("<br>");
    return `<div class="item"><div><strong>${esc(label)}</strong><p>${detail}</p></div></div>`;
  }).join(""):'<p class="translator-privacy">Monthly totals will appear after rewards with valid dates are recorded.</p>';
  $("reward-list").innerHTML=rewards.length?rewards.map(r=>{const recordedPaid=r.status==="paid"&&(r.reference||"").trim();const label=recordedPaid?"Paid (reference recorded)":r.status==="paid"?"Paid status missing reference":r.status;return `<div class="item"><div><h3>${money(r.amount,r.currency)} <span class="pill">${esc(label)}</span></h3><p>${esc(r.opportunities?.title||"Unlinked reward")} · ${esc(r.reference||"No transaction reference recorded")}</p></div></div>`}).join(""):'<div class="empty">No rewards recorded.</div>';
}
function fillRewardOptions(){$("reward-opportunity").innerHTML='<option value="">Not linked</option>'+opportunities.map(o=>'<option value="'+esc(o.id)+'">'+esc(o.title)+'</option>').join("")}
function bindTranslator(){
  const source=$("translate-source"),target=$("translate-target"),input=$("translate-input"),output=$("translate-output"),button=$("translate-button"),status=$("translate-status");
  input.addEventListener("input",()=>$("translate-count").textContent=`${input.value.length} / 5000`);
  $("swap-languages").onclick=()=>{if(source.value==="auto"){toast("Choose a source language before swapping.");return}const old=source.value;source.value=target.value;target.value=old;const oldText=input.value;input.value=output.value;output.value=oldText;$("translate-count").textContent=`${input.value.length} / 5000`};
  $("copy-translation").onclick=async()=>{if(!output.value)return toast("There is no translation to copy.");try{await navigator.clipboard.writeText(output.value);toast("Translation copied.")}catch(_){output.focus();output.select();toast("Select the translation and copy it.")}};
  button.onclick=async()=>{
    const text=input.value.trim();if(!text)return toast("Enter text to translate.");if(text.length>5000)return toast("Text is too long.");if(source.value!=="auto"&&source.value===target.value)return toast("Choose two different languages.");
    button.disabled=true;button.textContent="Translating…";status.textContent="Connecting to translation service…";output.value="";
    try{const response=await fetch("https://translate.astian.org/translate",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({q:text,source:source.value,target:target.value,format:"text"})});if(!response.ok)throw new Error(response.status===429?"Translation limit reached. Try again later.":`Translation service error (${response.status}).`);const data=await response.json();if(!data.translatedText)throw new Error("The translation service returned no translation.");output.value=data.translatedText;status.textContent=`Translated${data.detectedLanguage?.language?` · detected: ${data.detectedLanguage.language}`:""}. Check important translations before relying on them.`}
    catch(error){status.textContent=error.message||"Translation failed. Check your connection and try again.";toast(status.textContent)}finally{button.disabled=false;button.textContent="Translate"}
  };
}
function bindWorkspace(){
  bindTranslator();
  $("add-opportunity").onclick=()=> $("opportunity-dialog").showModal();
  $("discover-opportunities").onclick=async()=>{
    const button=$("discover-opportunities");
    button.disabled=true;button.textContent="Searching worldwide…";
    try {
      const {data,error}=await supabase.functions.invoke("discover-opportunities",{body:{}});
      if(error) throw error;
      if(data?.needsSetup) throw new Error(data.error);
      if(data?.error) throw new Error(data.error);
      const rejected = data.rejected || {};
      const summary = `Discovery summary: ${data.accepted_candidates || 0} candidates found; ${rejected.invalid_url || 0} invalid URLs; ${rejected.excluded_category || 0} excluded categories.`;
      if ((data.saved || 0) === 0) {
        const details = Array.isArray(data.searches)
          ? data.searches.map(item => `${item.query}: ${item.results} results (HTTP ${item.status})`).join("\\n")
          : "No search diagnostics returned."; 
        const issues = Array.isArray(data.errors) && data.errors.length ? `\\nIssues: ${data.errors.join("; ")}` : "";
        alert(`No new opportunities were saved. ${summary}\\nSearch diagnostics:\\n${details}${issues}`);
      } else {
        toast(`Saved ${data.saved} new candidates. ${summary} Auto-approved for manual access; not verified.`);
      }
      await loadData();
    } catch(error) { fail(error); }
    finally { button.disabled=false;button.textContent="Find new opportunities"; }
  };
  $("add-reward").onclick=()=> $("reward-dialog").showModal();
  document.querySelectorAll("[data-close]").forEach(b=>b.onclick=()=>b.closest("dialog").close());
  $("opportunity-form").onsubmit=async e=>{
    e.preventDefault();const data=Object.fromEntries(new FormData(e.target));
    const safeUrl=safePublicHttpsUrl(data.url);
    if(!safeUrl)return toast("Enter a valid public HTTPS platform URL (no IP address, local host, credentials, or custom port).");
    if(data.terms_url&&!safePublicHttpsUrl(data.terms_url))return toast("The official terms link must be a valid public HTTPS URL.");
    const {error}=await supabase.from("opportunities").insert({...data,owner_id:currentUser.id,status:"eligible",url:safeUrl,terms_url:data.terms_url?safePublicHttpsUrl(data.terms_url):"",score:(data.terms_url?25:0)+(data.eligibility?20:0)+(data.reward_description?15:0)});
    if(error)return fail(error);e.target.closest("dialog").close();e.target.reset();toast("Opportunity saved");await loadData();
  };
  $("reward-form").onsubmit=async e=>{
    e.preventDefault();const data=Object.fromEntries(new FormData(e.target));
    data.owner_id=currentUser.id;data.opportunity_id=data.opportunity_id?Number(data.opportunity_id):null;data.amount=Number(data.amount);data.currency=(data.currency||"").trim().toUpperCase();data.reference=(data.reference||"").trim();
    const validation=AutoEarnRewardLedger.validateReward(data);
    if(validation)return toast(validation);
    const {error}=await supabase.from("rewards").insert(data);
    if(error)return fail(error);e.target.closest("dialog").close();e.target.reset();toast("Reward recorded");await loadData();
  };
  $("search").oninput=renderOpportunities;$("filter").onchange=renderOpportunities;$("opportunity-sort").onchange=renderOpportunities;
  $("sign-out").onclick=async()=>{const {error}=await supabase.auth.signOut();if(error)return fail(error);currentUser=null;showAuth("You have signed out.")};
}
async function boot(){
  if(!configured){showAuth("Setup required: add your Supabase publishable key in static/config.js. This is a public client key; never put a service-role or secret key here.");$("auth-form").hidden=true;return}
  if(!window.supabase){showAuth("Authentication library could not be loaded. Check your connection and reload.");return}
  supabase=window.supabase.createClient(cfg.url,cfg.publishableKey);
  bindWorkspace();
  $("auth-form").onsubmit=async e=>{
    e.preventDefault();$("auth-submit").disabled=true;
    const {data,error}=await supabase.auth.signInWithPassword({email:$("auth-email").value.trim(),password:$("auth-password").value});
    $("auth-submit").disabled=false;
    if(error){console.error("Supabase sign-in failed:",error);$("auth-message").textContent="Login failed: "+(error.message||"Unknown authentication error");return}
    currentUser=data.user;showWorkspace();try{await loadData()}catch(err){fail(err)}
  };
  const {data,error}=await supabase.auth.getSession();
  if(error){showAuth("Could not restore your session. Please sign in.");return}
  if(data.session){currentUser=data.session.user;showWorkspace();try{await loadData()}catch(err){fail(err)}}else showAuth();
  supabase.auth.onAuthStateChange((_event,session)=>{if(!session){currentUser=null;showAuth()}});
}
boot();
