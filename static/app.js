const $ = (id) => document.getElementById(id);
const cfg = window.AUTOEARN_CONFIG || {};
const configured = Boolean(cfg.url && cfg.publishableKey && !cfg.publishableKey.includes("PASTE_"));
let supabase = null;
let currentUser = null;
let opportunities = [];
let tasks = [];
let rewards = [];
const DISCOVERY_CATEGORIES = new Set(["game","sweepstakes","wheel","raffle","prediction","puzzle","iq-test","instant-win"]);
const CATEGORY_LABELS = { game:"Game", sweepstakes:"Sweepstakes", wheel:"Spin wheel", raffle:"Raffle", prediction:"Prediction contest", puzzle:"Puzzle", "iq-test":"Quiz", "instant-win":"Instant win" };
function categoryLabel(category){ return CATEGORY_LABELS[category] || category || "Other"; }

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
  $("opportunity-list").innerHTML=rows.length?rows.map(o=>`<div class="item"><div><h3>${esc(o.title)} <span class="pill">${esc(o.status)}</span></h3><p>${esc(o.platform)} · ${esc(categoryLabel(o.category))} · Review score ${o.score}/60<br><a href="${esc(o.url)}" target="_blank" rel="noopener noreferrer">Open platform ↗</a> ${o.terms_url?'· <a href="'+esc(o.terms_url)+'" target="_blank" rel="noopener noreferrer">Terms ↗</a>':''}<br>${esc(o.reward_description||"No reward details entered")}</p></div><div class="item-actions">${o.status==="eligible"?'<button class="primary" data-task="'+o.id+'">Start guided session</button>':'<button class="secondary" data-review="'+o.id+'">Review eligibility</button>'}<button class="secondary" data-status="${o.id}" data-next="reviewing">Mark reviewing</button></div></div>`).join(""):'<div class="empty">No matching opportunities.</div>';
  $("opportunity-list").querySelectorAll("[data-task]").forEach(b=>b.onclick=()=>createTask(Number(b.dataset.task)));
  $("opportunity-list").querySelectorAll("[data-review]").forEach(b=>b.onclick=()=>verifyEligibility(Number(b.dataset.review)));
  $("opportunity-list").querySelectorAll("[data-status]").forEach(b=>b.onclick=()=>setStatus(Number(b.dataset.status),b.dataset.next));
}
async function verifyEligibility(id){
  const opportunity=opportunities.find(item=>Number(item.id)===Number(id));
  if(!opportunity)return toast("Opportunity not found. Refresh and try again.");
  if(!opportunity.terms_url)return toast("Add the official terms URL before eligibility review.");
  $("eligibility-opportunity-id").value=String(id);
  $("eligibility-form").reset();
  $("eligibility-opportunity-id").value=String(id);
  $("eligibility-dialog").showModal();
}
async function createTask(id){
  const opportunity=opportunities.find(item=>Number(item.id)===Number(id));
  if(!opportunity)return toast("Opportunity not found. Refresh and try again.");
  if(opportunity.status!=="eligible"||!opportunity.terms_url)return toast("This opportunity is not cleared. Review official terms, country eligibility and payout method first.");
  let target;
  try {
    target=new URL(opportunity.url);
    if(target.protocol!=="https:") throw new Error("Only secure HTTPS platform links can be opened.");
  } catch(error) { return toast(error.message||"Invalid platform URL."); }
  if(!confirm("Start a guided session for this opportunity? AutoEarn will only open the official HTTPS page and record the session. It will NOT sign up, log in, play automatically, submit information, or spend money."))return;
  const opened=window.open(target.href,"_blank","noopener,noreferrer");
  if(!opened){toast("Allow pop-ups for AutoEarn AI, then tap Start guided session again.");return;}
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
    const {error}=await supabase.from("opportunities").insert({...data,owner_id:currentUser.id,url:String(data.url).trim(),score:(data.terms_url?25:0)+(data.eligibility?20:0)+(data.reward_description?15:0)});
    if(error)return fail(error);e.target.closest("dialog").close();e.target.reset();toast("Opportunity saved");await loadData();
  };
  $("eligibility-form").onsubmit=async e=>{
    e.preventDefault();
    const data=Object.fromEntries(new FormData(e.target));
    const id=Number(data.opportunity_id);
    const opportunity=opportunities.find(item=>Number(item.id)===id);
    if(!opportunity)return toast("Opportunity not found. Refresh and try again.");
    for(const key of ["payout_source","automation_source"]){
      try{const u=new URL(data[key]);if(u.protocol!=="https:")throw new Error();data[key]=u.href}
      catch(_){return toast("Both evidence links must be valid HTTPS URLs.")}
    }
    const passed=data.country.trim()&&data.country_allowed==="yes"&&data.payment_method&&data.payment_method!=="Other / not specified"&&data.payment_confirmed==="yes"&&data.minimum.trim()&&data.fees.trim()&&data.kyc!=="unknown"&&data.free_entry==="yes"&&data.automation==="yes";
    const report={reviewed_at:new Date().toISOString(),country:data.country.trim(),country_allowed:data.country_allowed,payment_method:data.payment_method,payment_confirmed:data.payment_confirmed,minimum_withdrawal:data.minimum.trim(),fees:data.fees.trim(),kyc:data.kyc,free_entry:data.free_entry,automation_explicitly_allowed:data.automation,payout_source:data.payout_source,automation_source:data.automation_source};
    const note="\n\n[OWNER OFFICIAL ELIGIBILITY REVIEW]\n"+JSON.stringify(report,null,2);
    const {error}=await supabase.from("opportunities").update({status:passed?"eligible":"ineligible",notes:(opportunity.notes||"")+note}).eq("id",id);
    if(error)return fail(error);
    e.target.closest("dialog").close();
    toast(passed?"Review saved: eligible for guided review; no automatic gameplay is enabled.":"Review saved: this opportunity is not cleared.");
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
  $("search").oninput=renderOpportunities;$("filter").onchange=renderOpportunities;
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
