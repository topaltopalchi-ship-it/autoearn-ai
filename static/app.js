const $ = (id) => document.getElementById(id);
const cfg = window.AUTOEARN_CONFIG || {};
function safePublicHttpsUrl(value){
  try{
    const u=new URL(String(value||"").trim());
    const host=u.hostname.toLowerCase().replace(/\.$/,"");
    if(u.protocol!=="https:"||u.username||u.password||(u.port&&u.port!=="443"))return null;
    if(!host||host==="localhost"||host.endsWith(".localhost")||host.endsWith(".local")||host.startsWith("[")||/^\d{1,3}(?:\.\d{1,3}){3}$/.test(host))return null;
    const labels=host.split(".");
    if(labels.length<2||labels.some(label=>!label||label.length>63||!/^[a-z0-9](?:[a-z0-9-]*[a-z0-9])?$/.test(label)))return null;
    return u.href;
  }catch(_){return null}
}
const configured = Boolean(cfg.url && cfg.publishableKey && !cfg.publishableKey.includes("PASTE_"));
let supabase = null;
let currentUser = null;
let opportunities = [];
let tasks = [];
let rewards = [];
const DISCOVERY_CATEGORIES = new Set(["game","sweepstakes","wheel","raffle","prediction","puzzle","iq-test","instant-win"]);
const CATEGORY_LABELS = { game:"Game", sweepstakes:"Sweepstakes", wheel:"Spin wheel", raffle:"Raffle", prediction:"Prediction contest", puzzle:"Puzzle", "iq-test":"Quiz", "instant-win":"Instant win" };
function categoryLabel(category){ return String(category||"").split(",").map(value=>value.trim()).filter(Boolean).map(value=>CATEGORY_LABELS[value]||value).join(", ") || "Other"; }
function discoveryProvenanceHtml(opportunity){
  const provenance=window.AutoEarnDiscoveryProvenance?.extractDiscoveryProvenance(opportunity.notes||"");
  if(!provenance)return "";
  const timestamp=Date.parse(provenance.discovered_at);
  const discovered=Number.isFinite(timestamp)?new Date(timestamp).toLocaleString():"date unavailable";
  return "<br><strong>Discovery source:</strong> "+esc(provenance.source||"Search")+
    " · "+esc(discovered)+(provenance.search_query?"<br><strong>Search query:</strong> "+esc(provenance.search_query):"")+
    (provenance.excerpt?"<details><summary>View original discovery excerpt</summary><small>"+esc(provenance.excerpt)+"</small></details>":"");
}
function eligibilityReviewHtml(opportunity){
  const base=opportunity.eligibility||"Not reviewed; payout and automation details unknown.";
  const marker="[OWNER OFFICIAL ELIGIBILITY REVIEW]";
  const notes=String(opportunity.notes||"");
  const index=notes.lastIndexOf(marker);
  const dueFlags=window.AutoEarnDueDiligence.extractReviewFlags(notes);
  const evidence=window.AutoEarnDueDiligence.calculateEvidenceCompleteness(notes,opportunity.terms_url);
  let html=esc(base);
  if(dueFlags)html+="<br><strong>Review alerts:</strong> "+esc(dueFlags.replaceAll("_"," "));
  if(evidence)html+="<br><strong>Evidence completeness (text heuristic):</strong> "+evidence.score+"/100 · Not a legitimacy or payout guarantee.";
  if(index<0)return html;
  try{
    const report=JSON.parse(notes.slice(index+marker.length).trim());
    const yesNo=value=>value==="yes"?"Yes":value==="no"?"No":value||"Not stated";
    const automation=report.automation_explicitly_allowed==="yes"?"Explicitly permitted":report.automation_explicitly_allowed==="no"?"Prohibited":"Unclear / not stated";
    const details=[
      "Confirmed payment method: "+(report.payment_method||"Not stated"),
      "Official payout confirmation: "+yesNo(report.payment_confirmed),
      "Minimum withdrawal: "+(report.minimum_withdrawal||"Not stated"),
      "Withdrawal fees: "+(report.fees||"Not stated"),
      "Country eligibility: "+yesNo(report.country_eligible),
      "Minimum age: "+(report.minimum_age||"Not stated"),
      "KYC: "+(report.kyc==="required"?"Required":report.kyc==="not-required"?"Not required":"Unknown"),
      "Free entry / no deposit: "+yesNo(report.free_entry),
      "Automated gameplay: "+automation
    ];
    const sourceLinks=[["Official terms",opportunity.terms_url],["Payout evidence",report.payout_source],["Automation rules",report.automation_source]].map(([label,url])=>{const safe=safePublicHttpsUrl(url||"");return safe?'<a href="'+esc(safe)+'" target="_blank" rel="noopener noreferrer">'+label+'</a>':null;}).filter(Boolean);
    const reviewed=report.reviewed_at?new Date(report.reviewed_at).toLocaleString():"date not recorded";
    return html+"<br><strong>Owner's official review ("+esc(reviewed)+"):</strong> "+details.map(esc).join(" · ")+(sourceLinks.length?"<br><strong>Evidence:</strong> "+sourceLinks.join(" · "):"");
  }catch(_){return html;}
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
  opportunities=(o.data||[]).filter(item=>DISCOVERY_CATEGORIES.has(item.category));tasks=t.data||[];rewards=r.data||[];
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
  const sortedRows=window.AutoEarnDueDiligence.sortOpportunities(rows,sortMode);
  const summary=window.AutoEarnDueDiligence.summarizeOpportunities(rows);
  $("opportunity-summary").textContent=summary.total
    ? `Showing ${summary.total} opportunities · ${summary.scored} scored · Average evidence completeness: ${summary.averageScore===null?"—":summary.averageScore+"/100"} · High: ${summary.counts.high} · Medium: ${summary.counts.medium} · Needs review: ${summary.counts.low} · Unscored: ${summary.counts.unscored}`
    : "No opportunities match the current search and status filters.";
  $("opportunity-list").innerHTML=sortedRows.length?sortedRows.map(o=>`<div class="item"><div><h3>${esc(o.title)} <span class="pill">${esc(o.status==="eligible"?"Owner-cleared · not independently verified":o.status)}</span></h3><p>${esc(o.platform)} · ${esc(categoryLabel(o.category))} · Review score ${o.score}/60<br><a href="${esc(o.url)}" target="_blank" rel="noopener noreferrer">Open platform ↗</a> ${o.terms_url?'· <a href="'+esc(o.terms_url)+'" target="_blank" rel="noopener noreferrer">Terms ↗</a>':''}<br>${esc(o.reward_description||"No reward details entered")}${discoveryProvenanceHtml(o)}<br><strong>Eligibility review:</strong> ${eligibilityReviewHtml(o)}</p></div><div class="item-actions">${'<button class="secondary" data-review="'+o.id+'">Review eligibility</button>'}<button class="primary" data-start="${o.id}" ${["ineligible","archived"].includes(o.status)?"disabled":""}>Open manually</button><button class="secondary" data-status="${o.id}" data-next="reviewing">Mark reviewing</button></div></div>`).join(""):'<div class="empty">No matching opportunities.</div>';
  $("opportunity-list").querySelectorAll("[data-review]").forEach(b=>b.onclick=()=>verifyEligibility(Number(b.dataset.review)));
  $("opportunity-list").querySelectorAll("[data-start]").forEach(b=>b.onclick=()=>createTask(Number(b.dataset.start)));
  $("opportunity-list").querySelectorAll("[data-status]").forEach(b=>b.onclick=()=>setStatus(Number(b.dataset.status),b.dataset.next));
}
async function verifyEligibility(id){
  const opportunity=opportunities.find(item=>Number(item.id)===Number(id));
  if(!opportunity)return toast("Opportunity not found. Refresh and try again.");
  if(!safePublicHttpsUrl(opportunity.url))return toast("The platform link must be a public HTTPS website.");
  $("eligibility-opportunity-id").value=String(id);
  $("eligibility-form").reset();
  $("eligibility-opportunity-id").value=String(id);
  $("eligibility-form").elements.terms_url.value=opportunity.terms_url||"";
  $("eligibility-dialog").showModal();
}
async function createTask(id){
  const opportunity=opportunities.find(item=>Number(item.id)===Number(id));
  if(!opportunity)return toast("Opportunity not found. Refresh and try again.");
  if(["ineligible","archived"].includes(opportunity.status))return toast("This opportunity is marked ineligible or archived and cannot be opened from a guided session.");
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
    status:"approved",
    approved_at:new Date().toISOString()
  });
  if(error)return fail(error);
  toast("Guided session recorded. Follow the platform rules manually.");
  await loadData();
}
async function setStatus(id,status){
  const {error}=await supabase.from("opportunities").update({status}).eq("id",id);
  if(error)return fail(error);await loadData();
}
function renderTasks(){
  $("task-list").innerHTML=tasks.length?tasks.map(t=>`<div class="item"><div><h3>${esc(t.description)}</h3><p>${esc(t.opportunities?.title||"Opportunity")} · ${esc(t.opportunities?.platform||"")} · ${esc(t.status)}</p></div><div class="item-actions">${t.status==="pending_approval"?'<button class="primary" data-approve="'+t.id+'">Approve task</button>':''}${t.status==="approved"?'<button class="secondary" data-complete="'+t.id+'">Mark completed</button>':''}</div></div>`).join(""):'<div class="empty">No tasks yet. Create a task from an opportunity.</div>';
  $("task-list").querySelectorAll("[data-approve]").forEach(b=>b.onclick=async()=>{if(!confirm("Approve this task? You remain responsible for following platform rules."))return;const {error}=await supabase.from("tasks").update({status:"approved",approved_at:new Date().toISOString()}).eq("id",b.dataset.approve).eq("status","pending_approval");if(error)return fail(error);await loadData()});
  $("task-list").querySelectorAll("[data-complete]").forEach(b=>b.onclick=async()=>{const {error}=await supabase.from("tasks").update({status:"completed",completed_at:new Date().toISOString()}).eq("id",b.dataset.complete).eq("status","approved");if(error)return fail(error);await loadData()});
}
function renderRewards(){
  $("reward-list").innerHTML=rewards.length?rewards.map(r=>{const recordedPaid=r.status==="paid"&&(r.reference||"").trim();const label=recordedPaid?"Paid (reference recorded)":r.status==="paid"?"Paid status missing reference":r.status;return `<div class="item"><div><h3>${money(r.amount,r.currency)} <span class="pill">${esc(label)}</span></h3><p>${esc(r.opportunities?.title||"Unlinked reward")} · ${esc(r.reference||"No transaction reference recorded")}</p></div></div>`}).join(""):'<div class="empty">No rewards recorded.</div>';
}
function fillRewardOptions(){$("reward-opportunity").innerHTML='<option value="">Not linked</option>'+opportunities.map(o=>'<option value="'+o.id+'">'+esc(o.title)+'</option>').join("")}
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
      const summary = `Filter summary: ${data.accepted_candidates || 0} accepted candidates; ${rejected.invalid_url || 0} invalid URLs; ${rejected.excluded_category || 0} excluded categories; ${rejected.missing_free_entry_evidence || 0} without proof of free entry; ${rejected.missing_reward_evidence || 0} without clear prize evidence; ${rejected.missing_payout_evidence || 0} without clear payout evidence.`;
      if ((data.saved || 0) === 0) {
        const details = Array.isArray(data.searches)
          ? data.searches.map(item => `${item.query}: ${item.results} results (HTTP ${item.status})`).join("\\n")
          : "No search diagnostics returned."; 
        const issues = Array.isArray(data.errors) && data.errors.length ? `\\nIssues: ${data.errors.join("; ")}` : "";
        alert(`No new opportunities were saved. ${summary}\\nSearch diagnostics:\\n${details}${issues}`);
      } else {
        toast(`Saved ${data.saved} new candidates. ${summary} Please review them.`);
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
    const {error}=await supabase.from("opportunities").insert({...data,owner_id:currentUser.id,url:safeUrl,terms_url:data.terms_url?safePublicHttpsUrl(data.terms_url):"",score:(data.terms_url?25:0)+(data.eligibility?20:0)+(data.reward_description?15:0)});
    if(error)return fail(error);e.target.closest("dialog").close();e.target.reset();toast("Opportunity saved");await loadData();
  };
  $("eligibility-form").onsubmit=async e=>{
    e.preventDefault();
    const data=Object.fromEntries(new FormData(e.target));
    const id=Number(data.opportunity_id);
    const opportunity=opportunities.find(item=>Number(item.id)===id);
    if(!opportunity)return toast("Opportunity not found. Refresh and try again.");
    for(const key of ["terms_url","payout_source","automation_source"]){
      try{const safe=safePublicHttpsUrl(data[key]);if(!safe)throw new Error();data[key]=safe}
      catch(_){return toast("All three official evidence links must be valid public HTTPS URLs.")}
    }
    const passed=data.payment_method&&data.payment_method!=="Other / not specified"&&data.payment_confirmed==="yes"&&data.minimum.trim()&&data.fees.trim()&&data.country_eligible==="yes"&&data.minimum_age.trim()&&data.kyc!=="unknown"&&data.free_entry==="yes"&&data.automation==="yes";
    const report={reviewed_at:new Date().toISOString(),payment_method:data.payment_method,payment_confirmed:data.payment_confirmed,minimum_withdrawal:data.minimum.trim(),fees:data.fees.trim(),country_eligible:data.country_eligible,minimum_age:data.minimum_age.trim(),kyc:data.kyc,free_entry:data.free_entry,automation_explicitly_allowed:data.automation,payout_source:data.payout_source,automation_source:data.automation_source};
    const note="\n\n[OWNER OFFICIAL ELIGIBILITY REVIEW]\n"+JSON.stringify(report,null,2);
    const {error}=await supabase.from("opportunities").update({status:passed?"reviewing":"ineligible",terms_url:data.terms_url,notes:(opportunity.notes||"")+note}).eq("id",id);
    if(error)return fail(error);
    e.target.closest("dialog").close();
    toast(passed?"Owner checklist saved. This remains under review until official evidence is independently verified; guided sessions are not enabled.":"Review saved: this opportunity is not cleared.");
    await loadData();
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
