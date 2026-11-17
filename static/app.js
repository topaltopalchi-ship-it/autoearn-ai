const $ = (id) => document.getElementById(id);
const ownerToken = () => sessionStorage.getItem("autoearn_owner_token") || "";
const api = async (path, options={}) => {
  const headers = {"Content-Type":"application/json", ...(options.headers || {})};
  if (ownerToken()) headers["X-AutoEarn-Owner-Token"] = ownerToken();
  const response = await fetch(path, {...options, headers});
  const body = await response.json().catch(()=>({detail:"Unexpected server response"}));
  if (!response.ok) throw new Error(body.detail || "Request failed");
  return body;
};
const money = (n,c="USD") => new Intl.NumberFormat(undefined,{style:"currency",currency:c}).format(n);
function toast(message){const el=$("toast");el.textContent=message;el.classList.add("show");setTimeout(()=>el.classList.remove("show"),2600)}
function esc(s=""){return String(s).replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]))}
$("owner-token").value = ownerToken();
let opportunities=[];
let sources=[];
async function refresh(){
  const [dash,opps,tasks,rewards,sourceRows]=await Promise.all([api("/api/dashboard"),api("/api/opportunities"),api("/api/tasks"),api("/api/rewards"),api("/api/sources")]);
  opportunities=opps;sources=sourceRows;
  $("stat-opps").textContent=dash.opportunities;$("stat-tasks").textContent=dash.tasks;
  $("stat-approval").textContent=dash.awaiting_approval;$("stat-paid").textContent=money(dash.paid_total);
  $("stat-pending").textContent="Pending: "+money(dash.pending_total);
  renderOpportunities();renderSources();renderTasks(tasks);renderRewards(rewards);fillRewardOptions();
}
function renderOpportunities(){
  const q=$("search").value.toLowerCase(),status=$("filter").value,verification=$("verification-filter").value;
  const rows=opportunities.filter(o=>(!status||o.status===status)&&(!verification||o.verification_status===verification)&&[o.title,o.platform,o.category].some(x=>x.toLowerCase().includes(q)));
  $("opportunity-list").innerHTML=rows.length?rows.map(o=>`<div class="item"><div><h3>${esc(o.title)} <span class="pill">${esc(o.status)}</span></h3><p>${esc(o.platform)} · ${esc(o.category)} · Review score ${o.score}/100<br><a href="${esc(o.url)}" target="_blank" rel="noopener noreferrer">Open platform ↗</a> ${o.terms_url?'· <a href="'+esc(o.terms_url)+'" target="_blank" rel="noopener noreferrer">Terms ↗</a>':''}<br>${esc(o.reward_description||"No reward details entered")}</p><p>Verification: <b>${esc(o.verification_status||"pending")}</b> · Eligible: ${esc((o.eligible_countries||[]).join(", ")||"Not specified")} · Excluded: ${esc((o.excluded_countries||[]).join(", ")||"Not specified")}<br>Withdrawal: ${o.minimum_withdrawal_amount==null?"Not specified":esc(o.minimum_withdrawal_amount)+" "+esc(o.withdrawal_currency)} · Payout: ${esc((o.payout_methods||[]).join(", ")||"Not specified")}<br>${o.verification_notes?"Reviewer note: "+esc(o.verification_notes):"No reviewer note"}</p></div><div class="item-actions"><button class="secondary" data-task="${o.id}">Create task</button><button class="secondary" data-status="${o.id}" data-next="reviewing">Review</button><button class="secondary" data-verify="${o.id}">Verify</button></div></div>`).join(""):'<div class="empty">No matching opportunities.</div>';
  $("opportunity-list").querySelectorAll("[data-evaluate]").forEach(b=>b.onclick=()=>openEvaluation(Number(b.dataset.evaluate)));
  $("opportunity-list").querySelectorAll("[data-task]").forEach(b=>b.onclick=()=>createTask(Number(b.dataset.task)));
  $("opportunity-list").querySelectorAll("[data-status]").forEach(b=>b.onclick=()=>setStatus(Number(b.dataset.status),b.dataset.next));
  $("opportunity-list").querySelectorAll("[data-verify]").forEach(b=>b.onclick=()=>verifyOpportunity(Number(b.dataset.verify)));
}
async function createTask(id){const description=prompt("Describe the activity you plan to do. The assistant will not play or submit anything without your approval:");if(!description)return;try{await api("/api/tasks",{method:"POST",body:JSON.stringify({opportunity_id:id,description})});toast("Task added to approval queue");refresh()}catch(e){toast(e.message)}}
async function setStatus(id,status){try{await api(`/api/opportunities/${id}/status?status=${status}`,{method:"PATCH"});refresh()}catch(e){toast(e.message)}}
async function verifyOpportunity(id){const current=opportunities.find(o=>o.id===id);const status=prompt("Set human verification state: pending, verified, or rejected",current?.verification_status||"pending");if(!status)return;if(!["pending","verified","rejected"].includes(status)){toast("Choose pending, verified, or rejected");return}const notes=prompt("Reviewer note (what was checked):",current?.verification_notes||"");if(notes===null)return;try{await api(`/api/opportunities/${id}/verification`,{method:"PATCH",body:JSON.stringify({status,notes})});toast("Verification state updated");refresh()}catch(e){toast(e.message)}}
function openEvaluation(id){
  const opportunity=opportunities.find(item=>item.id===id);
  if(!opportunity)return;
  const host=new URL(opportunity.url).hostname.toLowerCase();
  const matching=sources.filter(source=>{
    try{return source.status==="approved" && new URL(source.url).hostname.toLowerCase()===host}
    catch{return false}
  });
  if(!matching.length){toast("Approve a source on the same website host before evaluation");return}
  $("evaluation-source").innerHTML=matching.map(source=>'<option value="'+source.id+'">'+esc(source.name)+'</option>').join("");
  $("evaluation-form").elements.opportunity_id.value=id;
  $("evaluation-form").elements.country.value="";
  $("evaluation-dialog").showModal();
}
function renderSources(){
  const status=$("source-filter").value;
  const rows=sources.filter(s=>!status||s.status===status);
  $("source-list").innerHTML=rows.length?rows.map(s=>`<div class="item"><div><h3>${esc(s.name)} <span class="pill">${esc(s.status)}</span></h3><p>${esc(s.category)} · <a href="${esc(s.url)}" target="_blank" rel="noopener noreferrer">Open source ↗</a> ${s.terms_url?'· <a href="'+esc(s.terms_url)+'" target="_blank" rel="noopener noreferrer">Terms ↗</a>':''}<br>Country notes: ${esc(s.country_notes||"Not provided")}<br>Payment notes: ${esc(s.payment_notes||"Not provided")}<br>Review note: ${esc(s.review_notes||"Not reviewed")}</p></div><div class="item-actions"><button class="secondary" data-source-review="${s.id}" data-review-state="approved">Approve</button><button class="secondary" data-source-review="${s.id}" data-review-state="rejected">Reject</button></div></div>`).join(""):'<div class="empty">No matching source candidates.</div>';
  $("source-list").querySelectorAll("[data-source-review]").forEach(b=>b.onclick=()=>reviewSource(Number(b.dataset.sourceReview),b.dataset.reviewState));
}
async function reviewSource(id,status){
  const source=sources.find(s=>s.id===id);
  const notes=prompt("Why is this source approved or rejected? Record what you checked:",source?.review_notes||"");
  if(notes===null)return;
  try{await api(`/api/sources/${id}/review`,{method:"PATCH",body:JSON.stringify({status,notes})});toast("Source review saved");refresh()}catch(e){toast(e.message)}
}
function renderTasks(tasks){$("task-list").innerHTML=tasks.length?tasks.map(t=>`<div class="item"><div><h3>${esc(t.description)}</h3><p>${esc(t.opportunity_title)} · ${esc(t.platform)} · ${esc(t.status)}</p></div><div class="item-actions">${t.status==="pending_approval"?'<button class="primary" data-approve="'+t.id+'">Approve task</button>':''}${t.status==="approved"?'<button class="secondary" data-complete="'+t.id+'">Mark completed</button>':''}</div></div>`).join(""):'<div class="empty">No tasks yet. Create a task from an opportunity.</div>';
  $("task-list").querySelectorAll("[data-approve]").forEach(b=>b.onclick=async()=>{if(!confirm("Approve this task? You remain responsible for following the platform rules."))return;try{await api(`/api/tasks/${b.dataset.approve}/approve`,{method:"POST"});toast("Task approved")}catch(e){toast(e.message)}refresh()});
  $("task-list").querySelectorAll("[data-complete]").forEach(b=>b.onclick=async()=>{try{await api(`/api/tasks/${b.dataset.complete}/complete`,{method:"POST"});toast("Task marked completed")}catch(e){toast(e.message)}refresh()});
}
function renderRewards(rows){$("reward-list").innerHTML=rows.length?rows.map(r=>`<div class="item"><div><h3>${money(r.amount,r.currency)} <span class="pill">${esc(r.status)}</span></h3><p>${esc(r.opportunity_title||"Unlinked reward")} · ${esc(r.reference)}</p></div></div>`).join(""):'<div class="empty">No rewards recorded.</div>'}
function fillRewardOptions(){$("reward-opportunity").innerHTML='<option value="">Not linked</option>'+opportunities.map(o=>'<option value="'+o.id+'">'+esc(o.title)+'</option>').join("")}
$("add-opportunity").onclick=()=>$("opportunity-dialog").showModal();
$("add-source").onclick=()=>$("source-dialog").showModal();
$("save-owner-token").onclick=()=>{const value=$("owner-token").value.trim();if(!value){sessionStorage.removeItem("autoearn_owner_token");toast("Owner token cleared for this session");return}sessionStorage.setItem("autoearn_owner_token",value);toast("Owner token saved for this session");refresh().catch(e=>toast(e.message))};
$("discover-rss").onclick=async()=>{
  const feed_url=prompt("Public HTTPS RSS/Atom feed URL:");
  if(!feed_url)return;
  const domains=prompt("Exact allowed hostnames, comma-separated (include feed and listing hosts):");
  if(!domains)return;
  const category=prompt("Category: games_competitions, surveys_microtasks, freelancing_services, ai_content_products, other","surveys_microtasks");
  if(!category)return;
  try{
    const result=await api("/api/discovery/rss",{method:"POST",body:JSON.stringify({
      adapter_id:"manual-rss-"+Date.now(),display_name:"RSS feed: "+feed_url,
      feed_url,category,allowed_domains:domains.split(",").map(x=>x.trim()).filter(Boolean)
    })});
    toast("Found "+result.discovered_count+" listings; saved "+result.inserted_count+" pending candidates");
    refresh();
  }catch(e){toast(e.message)}
};
$("add-reward").onclick=()=>$("reward-dialog").showModal();
document.querySelectorAll("[data-close]").forEach(b=>b.onclick=()=>b.closest("dialog").close());
$("opportunity-form").onsubmit=async e=>{e.preventDefault();const data=Object.fromEntries(new FormData(e.target));for(const key of ["eligible_countries","excluded_countries","payout_methods"])data[key]=String(data[key]||"").split(",").map(x=>x.trim()).filter(Boolean);data.minimum_withdrawal_amount=data.minimum_withdrawal_amount===""?null:Number(data.minimum_withdrawal_amount);try{await api("/api/opportunities",{method:"POST",body:JSON.stringify(data)});e.target.closest("dialog").close();e.target.reset();toast("Opportunity saved");refresh()}catch(err){toast(err.message)}};
$("source-form").onsubmit=async e=>{e.preventDefault();const data=Object.fromEntries(new FormData(e.target));try{await api("/api/sources",{method:"POST",body:JSON.stringify(data)});e.target.closest("dialog").close();e.target.reset();toast("Source saved as pending review");refresh()}catch(err){toast(err.message)}};
$("evaluation-form").onsubmit=async e=>{
  e.preventDefault();
  const data=Object.fromEntries(new FormData(e.target));
  data.opportunity_id=Number(data.opportunity_id);
  data.source_id=Number(data.source_id);
  for(const field of ["reward_amount","estimated_minutes","payment_probability","risk_score"])
    data[field]=data[field]===""?null:Number(data[field]);
  data.estimated_cost=Number(data.estimated_cost||0);
  data.evidence=String(data.evidence||"").split("\n").map(x=>x.trim()).filter(Boolean);
  try{
    const result=await api("/api/opportunities/"+data.opportunity_id+"/evaluate",{method:"POST",body:JSON.stringify(data)});
    const value=result.evaluation;
    $("evaluation-dialog").close();
    alert("Eligibility: "+value.eligibility+
      "\nConfidence: "+value.confidence+"/100"+
      "\nRanking score: "+value.ranking_score+"/100"+
      "\nEstimated net reward: "+(value.net_reward_estimate==null?"unknown":value.net_reward_estimate+" "+value.currency)+
      "\nEstimated net hourly: "+(value.net_hourly_estimate==null?"unknown":value.net_hourly_estimate+" "+value.currency+"/h")+
      "\nExecution readiness: "+(value.execution_allowed?"prerequisites met":"blocked")+
      "\n\nWarnings:\n"+(value.risk_flags.join("\n")||"None")+
      "\n\nNo platform action was performed.");
  }catch(err){toast(err.message)}
};
$("reward-form").onsubmit=async e=>{e.preventDefault();const data=Object.fromEntries(new FormData(e.target));data.opportunity_id=data.opportunity_id?Number(data.opportunity_id):null;data.amount=Number(data.amount);try{await api("/api/rewards",{method:"POST",body:JSON.stringify(data)});e.target.closest("dialog").close();e.target.reset();toast("Reward recorded");refresh()}catch(err){toast(err.message)}};
$("source-filter").onchange=renderSources;$("search").oninput=renderOpportunities;$("filter").onchange=renderOpportunities;$("verification-filter").onchange=renderOpportunities;
refresh().catch(e=>toast(e.message));
