const $ = (id) => document.getElementById(id);
const api = async (path, options={}) => {
  const response = await fetch(path, {headers:{"Content-Type":"application/json"}, ...options});
  const body = await response.json().catch(()=>({detail:"Unexpected server response"}));
  if (!response.ok) throw new Error(body.detail || "Request failed");
  return body;
};
const money = (n,c="USD") => new Intl.NumberFormat(undefined,{style:"currency",currency:c}).format(n);
function toast(message){const el=$("toast");el.textContent=message;el.classList.add("show");setTimeout(()=>el.classList.remove("show"),2600)}
function esc(s=""){return String(s).replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]))}
let opportunities=[];
async function refresh(){
  const [dash,opps,tasks,rewards,player]=await Promise.all([api("/api/dashboard"),api("/api/opportunities"),api("/api/tasks"),api("/api/rewards"),api("/api/player/status")]);
  opportunities=opps;
  $("stat-opps").textContent=dash.opportunities;$("stat-tasks").textContent=dash.tasks;
  $("stat-approval").textContent=dash.awaiting_approval;$("stat-paid").textContent=money(dash.paid_total);
  $("stat-pending").textContent="Pending: "+money(dash.pending_total);
  renderOpportunities();renderTasks(tasks);renderRewards(rewards);renderPlayerStatus(player);fillRewardOptions();fillGameOptions();refreshGameStats();
}

function renderPlayerStatus(player){
  $("player-attempts").textContent=player.game_attempts;
  $("player-solve-rate").textContent=player.local_solve_rate===null?"—":Math.round(player.local_solve_rate*100)+"%";
  $("player-observations").textContent=player.strategy_observations;
  $("player-game-types").textContent=player.strategy_game_types;
  $("player-safety-note").textContent=player.external_gameplay_enabled
    ? "External gameplay status requires separate platform authorization."
    : "External gameplay and automated payments are disabled. Local solve rate is not a real-world win rate or earnings forecast.";
}
\nfunction renderOpportunities(){
  const q=$("search").value.toLowerCase(),status=$("filter").value,automation=$("automation-filter").value;
  const rows=opportunities.filter(o=>(!status||o.status===status)&&(!automation||o.automation_eligibility===automation)&&[o.title,o.platform,o.category,o.opportunity_category].some(x=>x.toLowerCase().includes(q)));
  $("opportunity-list").innerHTML=rows.length?rows.map(o=>`<div class="item"><div><h3>${esc(o.title)} <span class="pill">${esc(o.status)}</span></h3><p>${esc(o.platform)} · ${esc(o.category)} · Review score ${o.score}/100<br><span class="pill">Policy: ${esc(o.automation_policy)}</span> <span class="pill">CAPTCHA: ${o.captcha_required===null?'unknown':(o.captcha_required?'yes':'no')}</span> <span class="pill">Automation: ${esc(o.automation_eligibility)}</span><br>Type: ${esc(o.opportunity_category)} · Evidence: ${esc(o.policy_source)}<br><a href="${esc(o.url)}" target="_blank" rel="noopener noreferrer">Open platform ↗</a> ${o.terms_url?'· <a href="'+esc(o.terms_url)+'" target="_blank" rel="noopener noreferrer">Terms ↗</a>':''} ${o.policy_evidence_url?'· <a href="'+esc(o.policy_evidence_url)+'" target="_blank" rel="noopener noreferrer">Policy evidence ↗</a>':''}<br>${esc(o.reward_description||"No reward details entered")}</p></div><div class="item-actions"><button class="secondary" data-task="${o.id}">Create task</button><button class="secondary" data-status="${o.id}" data-next="reviewing">Review</button></div></div>`).join(""):'<div class="empty">No matching opportunities.</div>';
  $("opportunity-list").querySelectorAll("[data-task]").forEach(b=>b.onclick=()=>createTask(Number(b.dataset.task)));
  $("opportunity-list").querySelectorAll("[data-status]").forEach(b=>b.onclick=()=>setStatus(Number(b.dataset.status),b.dataset.next));
}
async function createTask(id){const description=prompt("Describe the activity you plan to do. The assistant will not play or submit anything without your approval:");if(!description)return;try{await api("/api/tasks",{method:"POST",body:JSON.stringify({opportunity_id:id,description})});toast("Task added to approval queue");refresh()}catch(e){toast(e.message)}}
async function setStatus(id,status){try{await api(`/api/opportunities/${id}/status?status=${status}`,{method:"PATCH"});refresh()}catch(e){toast(e.message)}}
function renderTasks(tasks){$("task-list").innerHTML=tasks.length?tasks.map(t=>`<div class="item"><div><h3>${esc(t.description)}</h3><p>${esc(t.opportunity_title)} · ${esc(t.platform)} · ${esc(t.status)}</p></div><div class="item-actions">${t.status==="pending_approval"?'<button class="primary" data-approve="'+t.id+'">Approve task</button>':''}${(t.status==="approved"||t.status==="auto_queued")?'<button class="secondary" data-complete="'+t.id+'">Mark completed</button>':''}</div></div>`).join(""):'<div class="empty">No tasks yet. Create a task from an opportunity.</div>';
  $("task-list").querySelectorAll("[data-approve]").forEach(b=>b.onclick=async()=>{if(!confirm("Approve this task? You remain responsible for following the platform rules."))return;try{await api(`/api/tasks/${b.dataset.approve}/approve`,{method:"POST"});toast("Task approved")}catch(e){toast(e.message)}refresh()});
  $("task-list").querySelectorAll("[data-complete]").forEach(b=>b.onclick=async()=>{try{await api(`/api/tasks/${b.dataset.complete}/complete`,{method:"POST"});toast("Task marked completed")}catch(e){toast(e.message)}refresh()});
}
function renderRewards(rows){$("reward-list").innerHTML=rows.length?rows.map(r=>`<div class="item"><div><h3>${money(r.amount,r.currency)} <span class="pill">${esc(r.status)}</span></h3><p>${esc(r.opportunity_title||"Unlinked reward")} · ${esc(r.reference)}</p></div></div>`).join(""):'<div class="empty">No rewards recorded.</div>'}
function fillGameOptions(){
  const eligible=opportunities.filter(o=>o.opportunity_category==="skill_contest"&&o.automation_eligibility==="auto");
  $("game-opportunity").innerHTML='<option value="">Select a policy-cleared skill contest</option>'+eligible.map(o=>`<option value="${o.id}">${esc(o.title)} — ${esc(o.platform)}</option>`).join("");
}
async function refreshGameStats(){try{const s=await api("/api/games/stats");$("game-stats").textContent=s.attempts?`${s.solved}/${s.attempts} locally solved (${Math.round(s.solve_rate*100)}%)`:"No rounds analyzed";}catch(e){$("game-stats").textContent="Stats unavailable";}}
function fillRewardOptions(){$("reward-opportunity").innerHTML='<option value="">Not linked</option>'+opportunities.map(o=>'<option value="'+o.id+'">'+esc(o.title)+'</option>').join("")}
$("game-form").onsubmit=async e=>{
  e.preventDefault();
  try{
    const numbers=$("game-numbers").value.split(",").map(v=>Number(v.trim()));
    if(numbers.some(v=>!Number.isInteger(v)))throw new Error("Enter comma-separated whole numbers.");
    const result=await api("/api/games/solve",{method:"POST",body:JSON.stringify({opportunity_id:Number($("game-opportunity").value),numbers,target:Number($("game-target").value)})});
    $("game-result").textContent=result.solved?`${result.expression} = ${result.target}`:"No exact solution found for these tiles.";
    refreshGameStats();
  }catch(err){toast(err.message)}
};
$("add-opportunity").onclick=()=>$("opportunity-dialog").showModal();
$("prepare-automation").onclick=async()=>{try{const result=await api("/api/automation/prepare",{method:"POST"});toast(`${result.created_count} internal review task(s) prepared`);refresh()}catch(e){toast(e.message)}};
$("add-reward").onclick=()=>$("reward-dialog").showModal();
document.querySelectorAll("[data-close]").forEach(b=>b.onclick=()=>b.closest("dialog").close());
$("opportunity-form").onsubmit=async e=>{e.preventDefault();const data=Object.fromEntries(new FormData(e.target));data.captcha_required=data.captcha_required===""?null:data.captcha_required==="true";try{await api("/api/opportunities",{method:"POST",body:JSON.stringify(data)});e.target.closest("dialog").close();e.target.reset();toast("Opportunity saved");refresh()}catch(err){toast(err.message)}};
$("reward-form").onsubmit=async e=>{e.preventDefault();const data=Object.fromEntries(new FormData(e.target));data.opportunity_id=data.opportunity_id?Number(data.opportunity_id):null;data.amount=Number(data.amount);try{await api("/api/rewards",{method:"POST",body:JSON.stringify(data)});e.target.closest("dialog").close();e.target.reset();toast("Reward recorded");refresh()}catch(err){toast(err.message)}};
$("search").oninput=renderOpportunities;$("filter").onchange=renderOpportunities;$("automation-filter").onchange=renderOpportunities;
$("word-form").onsubmit=async e=>{
  e.preventDefault();
  try{
    const candidates=$("word-candidates").value.split(",").map(v=>v.trim()).filter(Boolean);
    const guesses=$("word-guesses").value.trim()?JSON.parse($("word-guesses").value):[];
    const result=await api("/api/games/word/filter",{method:"POST",body:JSON.stringify({
      opportunity_id:Number($("game-opportunity").value),candidates,guesses
    })});
    $("word-result").textContent=JSON.stringify(result,null,2);
  }catch(err){toast(err.message)}
};
$("logic-form").onsubmit=async e=>{
  e.preventDefault();
  try{
    const colors=$("logic-colors").value.split(",").map(v=>v.trim()).filter(Boolean);
    const history=$("logic-history").value.trim()?JSON.parse($("logic-history").value):[];
    const result=await api("/api/games/logic/mastermind",{method:"POST",body:JSON.stringify({
      opportunity_id:Number($("game-opportunity").value),colors,
      length:Number($("logic-length").value),history
    })});
    $("logic-result").textContent=JSON.stringify(result,null,2);
  }catch(err){toast(err.message)}
};
refresh().catch(e=>toast(e.message));
