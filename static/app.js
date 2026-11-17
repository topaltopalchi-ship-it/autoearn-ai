const $ = (id) => document.getElementById(id);
const ownerToken = () => sessionStorage.getItem("autoearn_owner_token") || "";
const api = async (path, options={}) => {
  const headers = {"Content-Type":"application/json", ...(options.headers || {})};
  if (ownerToken()) headers["X-AutoEarn-Owner-Token"] = ownerToken();
  const response = await fetch(path, {...options, headers});
  const body = await response.json().catch(()=>({}));
  if (!response.ok) throw new Error("انجام درخواست با خطا روبه‌رو شد. اطلاعات و دسترسی را بررسی کنید.");
  return body;
};
const statusFa = (v) => ({game_rewards:"پاداش بازی",survey_rewards:"پاداش نظرسنجی",microtasks:"کارهای کوچک",freelance_jobs:"کارهای آزاد",digital_products:"محصولات دیجیتال",discovered:"کشف‌شده",reviewing:"در حال بررسی",eligible:"مجاز",ineligible:"غیرمجاز",archived:"بایگانی‌شده",pending:"در انتظار",approved:"تأییدشده",rejected:"ردشده",verified:"تأییدشده",pending_approval:"در انتظار تأیید",confirmed:"تأییدشده",paid:"پرداخت‌شده",estimated:"تخمینی",earned:"کسب‌شده",withdrawable:"قابل برداشت",manual:"دستی",assist:"با کمک دستیار",official_api:"رابط رسمی برنامه‌نویسی",games_competitions:"بازی و مسابقه",surveys_microtasks:"نظرسنجی و کارهای کوچک",freelancing_services:"فریلنسری و خدمات",ai_content_products:"محتوای هوش مصنوعی و محصولات دیجیتال",other:"سایر","unknown":"نامشخص",logic:"معما و منطق",coding:"برنامه‌نویسی",chess:"شطرنج",strategy:"استراتژی",general:"عمومی"})[v]||"نامشخص";
const currencyFa = (c) => ({EUR:"یورو",USD:"دلار آمریکا",GBP:"پوند",TRY:"لیر",IRR:"ریال",CAD:"دلار کانادا",AUD:"دلار استرالیا"})[String(c||"").toUpperCase()] || "واحد پول";
const money = (n,c="EUR") => new Intl.NumberFormat("fa-IR",{maximumFractionDigits:2}).format(Number(n||0))+" "+currencyFa(c);
function ledgerTotals(groups,states){const values=Object.entries(groups||{}).map(([currency,items])=>{const total=states.reduce((sum,state)=>sum+Number(items[state]||0),0);return total?money(total,currency):null}).filter(Boolean);return values.join(" · ")||money(0,"EUR")}
const riskFlagFa = (v) => ({
  "country explicitly excluded":"کشور محل اقامت شما صریحاً در فهرست کشورهای غیرمجاز قرار دارد",
  "country not in the explicit eligible-country list":"کشور محل اقامت شما در فهرست کشورهای مجاز ثبت نشده است",
  "country eligibility is not documented":"شرایط مجازبودن کشور مشخص نشده است",
  "evidence observation time is missing":"زمان ثبت مدارک مشخص نشده است",
  "evidence timestamp is in the future":"زمان ثبت مدارک در آینده قرار دارد",
  "evidence is stale":"مدارک قدیمی هستند و باید دوباره بررسی شوند",
  "evidence timestamp is invalid":"زمان ثبت مدارک معتبر نیست",
  "source has not been approved":"منبع هنوز تأیید نشده است",
  "opportunity has not been verified":"فرصت هنوز بررسی و تأیید نشده است",
  "no supporting evidence recorded":"مدرک پشتیبان ثبت نشده است",
  "payment probability is unknown":"احتمال پرداخت مشخص نیست",
  "estimated payment probability is zero":"احتمال تخمینی پرداخت صفر است؛ اجرای خودکار مسدود شد",
  "time estimate is missing or invalid":"برآورد زمان ثبت نشده یا معتبر نیست",
  "advertised reward is unknown":"مبلغ پاداش اعلام‌شده مشخص نیست",
  "risk assessment is missing":"ارزیابی ریسک انجام نشده است",
  "automatic execution is unavailable for this execution mode":"اجرای خودکار در روش انتخاب‌شده مجاز نیست",
  "minimum withdrawal threshold uses a different currency; conversion is unknown":"ارز حداقل برداشت با ارز پاداش متفاوت است؛ تبدیل ارز مشخص نیست"
})[v]||"هشدار دیگری ثبت شده است";
function toast(message){const el=$("toast");el.textContent=message;el.classList.add("show");setTimeout(()=>el.classList.remove("show"),2600)}
function esc(s=""){return String(s).replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]))}
$("owner-token").value = ownerToken();
let opportunities=[];
let sources=[];
let competitions=[];
let discoveryFeeds=[];
let discoveryLeads=[];
let discoveryScheduler={};
let discoveryHealth={};
async function refresh(){
  const [dash,opps,tasks,earnings,sourceRows,competitionRows,feedRows,leadRows,schedulerState,healthState]=await Promise.all([api("/api/dashboard"),api("/api/opportunities"),api("/api/tasks"),api("/api/earnings"),api("/api/sources"),api("/api/competitions"),api("/api/discovery/feeds"),api("/api/discovery/leads"),api("/api/discovery/scheduler"),api("/api/discovery/health")]);
  opportunities=opps;sources=sourceRows;competitions=competitionRows;discoveryFeeds=feedRows;discoveryLeads=leadRows;discoveryScheduler=schedulerState;discoveryHealth=healthState;
  $("stat-opps").textContent=dash.opportunities;$("stat-tasks").textContent=dash.tasks;
  $("stat-approval").textContent=dash.awaiting_approval;$("stat-paid").textContent=ledgerTotals(dash.earnings_totals,["paid"]);
  $("stat-pending").textContent="در جریان: "+ledgerTotals(dash.earnings_totals,["estimated","earned","pending","withdrawable"]);
  renderOpportunities();renderSources();renderDiscoveryFeeds();renderDiscoveryScheduler();renderDiscoveryHealth();renderDiscoveryLeads();renderCompetitions();renderTasks(tasks);renderEarnings(earnings);fillRewardOptions();
  // Keep the research-priority queue current whenever the owner dashboard refreshes.
  loadPrioritizedDiscovery().catch(()=>{});
}
function renderOpportunities(){
  const q=$("search").value.toLowerCase(),status=$("filter").value,verification=$("verification-filter").value;
  const rows=opportunities.filter(o=>(!status||o.status===status)&&(!verification||o.verification_status===verification)&&[o.title,o.platform,o.category].some(x=>x.toLowerCase().includes(q)));
  $("opportunity-list").innerHTML=rows.length?rows.map(o=>`<div class="item"><div><h3>${esc(o.title)} <span class="pill">${esc(statusFa(o.status))}</span></h3><p>${esc(o.platform)} · ${esc(statusFa(o.category))} · امتیاز بررسی ${o.score}/100<br><a href="${esc(o.url)}" target="_blank" rel="noopener noreferrer">بازکردن پلتفرم ↗</a> ${o.terms_url?'· <a href="'+esc(o.terms_url)+'" target="_blank" rel="noopener noreferrer">قوانین ↗</a>':''}<br>${esc(o.reward_description||"جزئیات پاداش وارد نشده است")}</p><p>وضعیت تأیید: <b>${esc(statusFa(o.verification_status||"pending"))}</b> · کشورهای مجاز: ${esc((o.eligible_countries||[]).join(", ")||"مشخص نشده")} · کشورهای غیرمجاز: ${esc((o.excluded_countries||[]).join(", ")||"مشخص نشده")}<br>حداقل برداشت: ${o.minimum_withdrawal_amount==null?"مشخص نشده":esc(o.minimum_withdrawal_amount)+" "+esc(currencyFa(o.withdrawal_currency))} · روش پرداخت: ${esc((o.payout_methods||[]).join(", ")||"مشخص نشده")}<br>${o.verification_notes?"یادداشت بررسی: "+esc(o.verification_notes):"یادداشتی از بررسی‌کننده ثبت نشده است"}</p></div><div class="item-actions"><button class="secondary" data-evaluate="${o.id}">ارزیابی</button><button class="secondary" data-history="${o.id}">سوابق</button><button class="secondary" data-task="${o.id}">ساخت کار</button><button class="secondary" data-status="${o.id}" data-next="reviewing">بررسی</button><button class="secondary" data-verify="${o.id}">تأیید</button></div></div>`).join(""):'<div class="empty">فرصتی با این مشخصات پیدا نشد.</div>';
  $("opportunity-list").querySelectorAll("[data-evaluate]").forEach(b=>b.onclick=()=>openEvaluation(Number(b.dataset.evaluate)));
  $("opportunity-list").querySelectorAll("[data-history]").forEach(b=>b.onclick=()=>showEvaluationHistory(Number(b.dataset.history)));
  $("opportunity-list").querySelectorAll("[data-task]").forEach(b=>b.onclick=()=>createTask(Number(b.dataset.task)));
  $("opportunity-list").querySelectorAll("[data-status]").forEach(b=>b.onclick=()=>setStatus(Number(b.dataset.status),b.dataset.next));
  $("opportunity-list").querySelectorAll("[data-verify]").forEach(b=>b.onclick=()=>verifyOpportunity(Number(b.dataset.verify)));
}
async function showEvaluationHistory(id){
  try{
    const rows=await api(`/api/opportunities/${id}/evaluations`);
    if(!rows.length){toast("هنوز سابقه‌ای برای ارزیابی ثبت نشده است");return}
    $("evaluation-history-list").innerHTML=rows.map((row,index)=>{
      const e=row.evaluation||{};
      return `<article class="item"><div>
        <h3>ارزیابی شمارهٔ ${new Intl.NumberFormat("fa-IR").format(index+1)}</h3>
        <p>زمان: ${esc(new Date(row.created_at).toLocaleString("fa-IR"))}<br>
        کشور: ${esc(row.country)}<br>
        وضعیت صلاحیت: ${esc(statusFa(e.eligibility))}<br>
        امتیاز: ${e.ranking_score??"—"} از ۱۰۰<br>
        پاداش خالص در صورت پرداخت: ${e.net_reward_estimate==null?"نامشخص":esc(e.net_reward_estimate)+" "+(e.currency?currencyFa(e.currency):"")}<br>
        درآمد مورد انتظار با احتمال پرداخت: ${e.expected_net_reward_estimate==null?"نامشخص":esc(e.expected_net_reward_estimate)+" "+(e.currency?currencyFa(e.currency):"")}<br>
        درآمد ساعتی مورد انتظار: ${e.expected_net_hourly_estimate==null?"نامشخص":esc(e.expected_net_hourly_estimate)+" "+(e.currency?currencyFa(e.currency):"")}<br>
        احتمال پرداخت ثبت‌شده: ${e.payment_probability_percent==null?"نامشخص":esc(e.payment_probability_percent)+"٪"}<br>
        روش مشارکت: ${esc(statusFa(row.execution_mode))}</p>
      </div></article>`;
    }).join("");
    $("evaluation-history-dialog").showModal();
  }catch(e){toast(e.message)}
}
async function createTask(id){const description=prompt("فعالیتی را که قصد انجامش را دارید شرح دهید. دستیار بدون تأیید شما بازی یا چیزی را ارسال نمی‌کند:");if(!description)return;try{await api("/api/tasks",{method:"POST",body:JSON.stringify({opportunity_id:id,description})});toast("کار به صف تأیید اضافه شد");refresh()}catch(e){toast(e.message)}}
async function setStatus(id,status){try{await api(`/api/opportunities/${id}/status?status=${status}`,{method:"PATCH"});refresh()}catch(e){toast(e.message)}}
async function verifyOpportunity(id){const current=opportunities.find(o=>o.id===id);const entered=prompt("وضعیت بررسی انسانی را وارد کنید: در انتظار، تأییدشده یا ردشده",({pending:"در انتظار",verified:"تأییدشده",rejected:"ردشده"})[current?.verification_status]||"در انتظار");if(!entered)return;const status=({"در انتظار":"pending","تأییدشده":"verified","ردشده":"rejected"})[entered.trim()];if(!status){toast("یکی از عبارت‌های در انتظار، تأییدشده یا ردشده را وارد کنید");return}const notes=prompt("یادداشت بررسی‌کننده (چه چیزی بررسی شد):",current?.verification_notes||"");if(notes===null)return;try{await api(`/api/opportunities/${id}/verification`,{method:"PATCH",body:JSON.stringify({status,notes})});toast("وضعیت تأیید به‌روزرسانی شد");refresh()}catch(e){toast(e.message)}}
function openEvaluation(id){
  const opportunity=opportunities.find(item=>item.id===id);
  if(!opportunity)return;
  const host=new URL(opportunity.url).hostname.toLowerCase();
  const matching=sources.filter(source=>{
    try{return source.status==="approved" && new URL(source.url).hostname.toLowerCase()===host}
    catch{return false}
  });
  if(!matching.length){toast("پیش از ارزیابی، منبعی از همان دامنهٔ وب‌سایت را تأیید کنید");return}
  $("evaluation-source").innerHTML=matching.map(source=>'<option value="'+source.id+'">'+esc(source.name)+'</option>').join("");
  $("evaluation-form").elements.opportunity_id.value=id;
  $("evaluation-form").elements.country.value="";
  $("evaluation-dialog").showModal();
}
async function loadRankedOpportunities(){
  const country=$("rank-country").value.trim();
  if(country.length<2){toast("نام کشور را کامل وارد کنید");return}
  const host=$("ranked-opportunity-list");
  host.textContent="در حال محاسبهٔ اولویت‌ها…";
  try{
    const result=await api("/api/opportunities/ranked?country="+encodeURIComponent(country));
    if(!result.total){host.innerHTML='<div class="empty">برای این کشور هنوز ارزیابی ثبت نشده است. ابتدا فرصت‌ها را ارزیابی کنید.</div>';return}
    const tierLabels={priority_candidate:"اولویت بالاتر",needs_review:"نیازمند بررسی بیشتر",low_priority:"اولویت پایین"};
    const aiLabels={bounded_ai_draft_candidate:"مناسب تهیهٔ پیش‌نویس با AI",policy_blocked:"استفاده از AI مسدود",human_review_or_policy_check:"نیازمند بررسی انسانی یا قوانین"};
    host.innerHTML=result.groups.map(group=>'<div class="rank-currency"><h3>گروه '+esc(currencyFa(group.currency))+' · '+group.count+' فرصت</h3>'+
      group.items.map(item=>{
        const e=item.evaluation||{};
        return '<article class="item"><div><h3>#'+item.rank_in_currency+' · '+esc(item.title)+' <span class="pill">'+esc(tierLabels[item.priority_tier]||item.priority_tier)+'</span></h3>'+
          '<p>'+esc(item.platform)+' · امتیاز '+item.ranking_score+'/100 · '+esc(e.eligibility||"نامشخص")+'<br>'+
          'خالص در صورت پرداخت: '+(e.net_reward_estimate==null?"نامشخص":esc(e.net_reward_estimate)+" "+esc(currencyFa(e.currency)))+'<br>'+
          'درآمد مورد انتظار: '+(e.expected_net_reward_estimate==null?"نامشخص":esc(e.expected_net_reward_estimate)+" "+esc(currencyFa(e.currency)))+
          ' · ساعتی مورد انتظار: '+(e.expected_net_hourly_estimate==null?"نامشخص":esc(e.expected_net_hourly_estimate)+" "+esc(currencyFa(e.currency)))+'<br>'+
          'احتمال پرداخت: '+(e.payment_probability_percent==null?"نامشخص":esc(e.payment_probability_percent)+"٪")+'<br>'+
          'تناسب AI: '+esc(aiLabels[item.ai_fit]||item.ai_fit)+' · مجوز اقدام واقعی: خیر<br>'+
          'هشدارها: '+(Array.isArray(e.risk_flags)?e.risk_flags.length:0)+'</p>'+
          '<a href="'+esc(item.url)+'" target="_blank" rel="noopener noreferrer">بازکردن فرصت ↗</a></div></article>';
      }).join("")+'</div>').join("")+'<p class="muted">'+esc(result.comparison_note)+'</p>';
  }catch(error){host.textContent="دریافت رتبه‌بندی ناموفق بود: "+error.message}
}
function renderCompetitions(){
  const host=$("competition-list");
  host.innerHTML=competitions.length?competitions.map(c=>`<div class="item"><div><h3>${esc(c.title)} <span class="pill">${esc(statusFa(c.eligibility))}</span></h3><p>${esc(c.country)} · نوع: ${esc(statusFa(c.task_type))}<br><a href="${esc(c.url)}" target="_blank" rel="noopener noreferrer">صفحه مسابقه ↗</a> · <a href="${esc(c.rules_url)}" target="_blank" rel="noopener noreferrer">قوانین ↗</a><br>بررسی قوانین: ${c.terms_verified?"بله":"خیر"} · اجازه ربات: ${c.automated_agents_allowed?"بله":"خیر"} · API رسمی: ${c.official_api?"بله":"خیر"}</p></div><div class="item-actions"><button class="secondary" data-comp-plan="${c.id}">ساخت استراتژی</button><button class="secondary" data-comp-dry="${c.id}">تمرین آزمایشی</button></div></div>`).join(""):'<div class="empty">هنوز مسابقه‌ای ثبت نشده است.</div>';
  host.querySelectorAll("[data-comp-plan]").forEach(b=>b.onclick=async()=>{
    const objective=prompt("هدف یا شرح مسئلهٔ مسابقه را بنویسید (اختیاری):")||"";
    try{const result=await api(`/api/competitions/${b.dataset.compPlan}/plan`,{method:"POST",body:JSON.stringify({objective})});const p=result.plan;alert("استراتژی آماده شد\n\nروش: "+p.approach+"\n\nمراحل:\n"+p.steps.join("\n")+"\n\nبررسی‌ها:\n"+p.validation_checks.join("\n")+"\n\n"+(p.provider==="heuristic-baseline"?"برنامه‌ریز پایه فعال است؛ برای استفاده از مدل هوش مصنوعی باید کلید API در تنظیمات سرور قرار گیرد.":"برنامه با مدل هوش مصنوعی "+p.provider+" ساخته شده است."));}catch(e){toast(e.message)}
  });
  host.querySelectorAll("[data-comp-dry]").forEach(b=>b.onclick=async()=>{
    try{const result=await api(`/api/competitions/${b.dataset.compDry}/dry-run`,{method:"POST"});alert("نتیجه تمرین آزمایشی\n\nارسال واقعی: خیر\nآمادگی: "+(result.readiness?"بله":"خیر")+"\nموانع:\n"+(result.blockers.join("\n")||"ندارد")+"\n\n"+result.message);}catch(e){toast(e.message)}
  });
}
function renderSources(){
  const status=$("source-filter").value;
  const rows=sources.filter(s=>!status||s.status===status);
  $("source-list").innerHTML=rows.length?rows.map(s=>`<div class="item"><div><h3>${esc(s.name)} <span class="pill">${esc(statusFa(s.status))}</span></h3><p>${esc(statusFa(s.category))} · <a href="${esc(s.url)}" target="_blank" rel="noopener noreferrer">بازکردن منبع ↗</a> ${s.terms_url?'· <a href="'+esc(s.terms_url)+'" target="_blank" rel="noopener noreferrer">قوانین ↗</a>':''}<br>یادداشت کشور: ${esc(s.country_notes||"ارائه نشده")}<br>یادداشت پرداخت: ${esc(s.payment_notes||"ارائه نشده")}<br>یادداشت بررسی: ${esc(s.review_notes||"بررسی نشده")}</p></div><div class="item-actions"><button class="secondary" data-source-review="${s.id}" data-review-state="approved">تأیید</button><button class="secondary" data-source-review="${s.id}" data-review-state="rejected">رد</button></div></div>`).join(""):'<div class="empty">منبعی با این مشخصات پیدا نشد.</div>';
  $("source-list").querySelectorAll("[data-source-review]").forEach(b=>b.onclick=()=>reviewSource(Number(b.dataset.sourceReview),b.dataset.reviewState));
}
async function reviewSource(id,status){
  const source=sources.find(s=>s.id===id);
  const notes=prompt("چرا این منبع را تأیید یا رد می‌کنید؟ موارد بررسی‌شده را بنویسید:",source?.review_notes||"");
  if(notes===null)return;
  try{await api(`/api/sources/${id}/review`,{method:"PATCH",body:JSON.stringify({status,notes})});toast("نتیجهٔ بررسی منبع ذخیره شد");refresh()}catch(e){toast(e.message)}
}
function renderDiscoveryScheduler(){
  const enabled=$("discovery-scheduler-enabled");
  if(!enabled)return;
  enabled.checked=!!discoveryScheduler.enabled;
  $("discovery-scheduler-interval").value=String(discoveryScheduler.interval_minutes||360);
  const result=discoveryScheduler.last_result||{};
  const last=discoveryScheduler.last_completed_at?new Date(discoveryScheduler.last_completed_at).toLocaleString():"هنوز اجرا نشده";
  const next=discoveryScheduler.enabled&&discoveryScheduler.next_run_at?new Date(discoveryScheduler.next_run_at).toLocaleString():"غیرفعال";
  const error=discoveryScheduler.last_error?" · خطای آخر: "+discoveryScheduler.last_error:"";
  $("discovery-scheduler-status").textContent=
    "وضعیت: "+(discoveryScheduler.enabled?"فعال":"غیرفعال")+
    " · خبرخوان تأییدشده: "+(discoveryScheduler.approved_feed_count||0)+
    " · آخرین بررسی: "+last+
    " · مورد تازه: "+(result.inserted_count||0)+
    " · بررسی بعدی: "+next+error;
}
function renderDiscoveryHealth(){
  const host=$("discovery-health-panel");
  if(!host)return;
  const c=discoveryHealth.counts||{};
  const labels={healthy:"سالم",error:"دارای خطا",stale:"قدیمی",never_checked:"بررسی‌نشده",pending_review:"در انتظار تأیید",rejected:"ردشده"};
  const summary=["healthy","error","stale","never_checked","pending_review","rejected"].map(k=>labels[k]+": "+Number(c[k]||0)).join(" · ");
  const rows=(discoveryHealth.feeds||[]).filter(f=>f.review_status==="approved");
  host.innerHTML='<div><b>سلامت خبرخوان‌ها</b><p>'+esc(summary||"هنوز منبعی ثبت نشده است")+'</p></div>'+
    (rows.length?'<div>'+rows.map(f=>'<p><b>'+esc(f.name)+'</b> · '+esc(labels[f.health]||"غیرفعال")+' · قابلیت اتکا: '+(f.reliability_percent===null?'داده کافی نیست':Number(f.reliability_percent).toFixed(1)+'٪')+' ('+Number(f.total_successes||0)+' موفق از '+Number(f.total_checks||0)+' بررسی؛ '+(f.reliability_sample==='established'?'نمونه کافی':'نمونه محدود')+') · خطاهای متوالی: '+Number(f.consecutive_failures||0)+(f.last_error?' · '+esc(f.last_error):'')+'</p>').join('')+'</div>':'');
}
function renderDiscoveryFeeds(){
  const host=$("discovery-feed-list");
  host.innerHTML=discoveryFeeds.length?discoveryFeeds.map(feed=>`<div class="item"><div><h3>${esc(feed.name)} <span class="pill">${esc(statusFa(feed.status))}</span></h3><p><a href="${esc(feed.feed_url)}" target="_blank" rel="noopener noreferrer">نشانی خبرخوان ↗</a><br>دامنه‌های مجاز: ${esc((feed.allowed_domains||[]).join(", "))} · آخرین بررسی: ${esc(feed.last_checked_at||"هنوز بررسی نشده")} ${feed.last_error?"<br>خطا: "+esc(feed.last_error):""}</p></div><div class="item-actions">${feed.status!=="approved"?'<button class="secondary" data-feed-review="'+feed.id+'" data-feed-state="approved">تأیید خبرخوان</button>':""}${feed.status!=="rejected"?'<button class="secondary" data-feed-review="'+feed.id+'" data-feed-state="rejected">رد</button>':""}</div></div>`).join(""):'<div class="empty">خبرخوان پایداری ثبت نشده است.</div>';
  host.querySelectorAll("[data-feed-review]").forEach(button=>button.onclick=async()=>{
    try{await api("/api/discovery/feeds/"+button.dataset.feedReview+"/review",{method:"PATCH",body:JSON.stringify({status:button.dataset.feedState})});toast("وضعیت خبرخوان ذخیره شد");refresh()}catch(error){toast(error.message)}
  });
}
function renderDiscoveryLeads(){
  const host=$("discovery-lead-list");
  const pending=discoveryLeads.filter(lead=>lead.status==="pending");
  host.innerHTML=pending.length?pending.map(lead=>`<div class="item"><div><h3>${esc(lead.title)} <span class="pill">در انتظار بررسی</span></h3><p>منبع: ${esc(lead.source_name)} · دسته: ${esc(statusFa(lead.category))}<br><a href="${esc(lead.url)}" target="_blank" rel="noopener noreferrer">مشاهده فرصت ↗</a> ${lead.terms_url?'· <a href="'+esc(lead.terms_url)+'" target="_blank" rel="noopener noreferrer">قوانین ↗</a>':''}<br>${esc(lead.summary||"توضیحی ثبت نشده است")}<br>آخرین مشاهده: ${esc(lead.last_seen_at||lead.observed_at)}</p></div><div class="item-actions"><button class="primary" data-promote-lead="${lead.id}">انتقال به فرصت‌ها</button><button class="secondary" data-reject-lead="${lead.id}">رد فرصت</button></div></div>`).join(""):'<div class="empty">فرصت تازه‌ای در انتظار بررسی نیست.</div>';
  host.querySelectorAll("[data-promote-lead]").forEach(button=>button.onclick=async()=>{
    if(!confirm("این مورد به فهرست فرصت‌ها منتقل شود؟ وضعیت آن همچنان کشف‌شده و تأییدنشده می‌ماند."))return;
    try{const result=await api("/api/discovery/leads/"+button.dataset.promoteLead+"/promote",{method:"POST"});toast("فرصت به فهرست اصلی منتقل شد؛ بررسی و تأیید آن هنوز لازم است");refresh()}catch(error){toast(error.message)}
  });
  host.querySelectorAll("[data-reject-lead]").forEach(button=>button.onclick=async()=>{
    const notes=prompt("دلیل رد این فرصت را وارد کنید (اختیاری):")||"";
    try{await api("/api/discovery/leads/"+button.dataset.rejectLead+"/review",{method:"PATCH",body:JSON.stringify({status:"rejected",notes})});toast("فرصت رد شد");refresh()}catch(error){toast(error.message)}
  });
}
async function loadPrioritizedDiscovery(){
  const host=$("prioritized-discovery-list");
  host.textContent="در حال مرتب‌سازی فرصت‌های تازه…";
  try{
    const result=await api("/api/discovery/leads/prioritized");
    if(!result.total){host.innerHTML='<div class="empty">فرصت تازه‌ای در صف بررسی نیست.</div>';return}
    const labels={research_first:"بررسی در اولویت",review:"بررسی معمولی",low_signal:"اطلاعات ناکافی"};
    host.innerHTML=result.items.map(item=>'<article class="item"><div><h3>'+esc(item.title)+' <span class="pill">'+esc(labels[item.research_priority]||item.research_priority)+'</span></h3>'+
      '<p>امتیاز اولویت تحقیق: '+item.research_priority_score+'/100 · منبع: '+esc(item.source_name)+'<br>'+
      'سابقهٔ خبرخوان: '+(item.feed_reliability_percent==null?"نمونهٔ ناکافی":item.feed_reliability_percent+"٪")+
      ' · قوانین: '+(item.terms_url?'<a href="'+esc(item.terms_url)+'" target="_blank" rel="noopener noreferrer">مشاهده ↗</a>':"ثبت نشده")+'<br>'+
      'صلاحیت کشور: هنوز بررسی نشده · پرداخت: هنوز بررسی نشده · مجوز AI: نامشخص<br>'+
      esc(item.research_reasons.join("؛ "))+'<br><a href="'+esc(item.url)+'" target="_blank" rel="noopener noreferrer">بازکردن فرصت ↗</a></p></div></article>'
    ).join("")+'<p class="muted">'+esc(result.note)+'</p>';
  }catch(error){host.textContent="مرتب‌سازی صف ناموفق بود: "+error.message}
}
function renderTasks(tasks){$("task-list").innerHTML=tasks.length?tasks.map(t=>`<div class="item"><div><h3>${esc(t.description)}</h3><p>${esc(t.opportunity_title)} · ${esc(t.platform)} · ${esc(statusFa(t.status))}</p></div><div class="item-actions">${t.status==="pending_approval"?'<button class="primary" data-approve="'+t.id+'">تأیید کار</button>':''}${t.status==="approved"?'<button class="secondary" data-complete="'+t.id+'">علامت‌گذاری به‌عنوان تکمیل‌شده</button>':''}</div></div>`).join(""):'<div class="empty">هنوز کاری ثبت نشده است. از یک فرصت، کار جدید بسازید.</div>';
  $("task-list").querySelectorAll("[data-approve]").forEach(b=>b.onclick=async()=>{if(!confirm("این کار را تأیید می‌کنید؟ مسئولیت رعایت قوانین پلتفرم همچنان با شماست."))return;try{await api(`/api/tasks/${b.dataset.approve}/approve`,{method:"POST"});toast("کار تأیید شد")}catch(e){toast(e.message)}refresh()});
  $("task-list").querySelectorAll("[data-complete]").forEach(b=>b.onclick=async()=>{try{await api(`/api/tasks/${b.dataset.complete}/complete`,{method:"POST"});toast("کار به‌عنوان تکمیل‌شده ثبت شد")}catch(e){toast(e.message)}refresh()});
}
function renderEarnings(rows){
  const next={estimated:["earned","pending"],earned:["pending","withdrawable"],pending:["withdrawable"],withdrawable:["paid"],paid:[]};
  const labels={earned:"ثبت کسب درآمد",pending:"در انتظار پرداخت",withdrawable:"قابل برداشت",paid:"ثبت پرداخت"};
  $("reward-list").innerHTML=rows.length?rows.map(r=>`<div class="item"><div><h3>${money(r.amount,r.currency)} <span class="pill">${esc(statusFa(r.state))}</span></h3><p>${esc(r.opportunity_title||"درآمد بدون پیوند")} · ${esc(r.reference||"بدون توضیح")}<br>${r.evidence?"مدرک: "+esc(r.evidence):"مدرکی پیوست نشده است"}</p></div><div class="item-actions">${next[r.state].map(s=>'<button class="secondary" data-earning-state="'+r.id+'" data-next-state="'+s+'">'+labels[s]+'</button>').join("")}<button class="secondary" data-earning-history="${r.id}">سوابق</button></div></div>`).join(""):'<div class="empty">هنوز درآمدی ثبت نشده است.</div>';
  $("reward-list").querySelectorAll("[data-earning-state]").forEach(b=>b.onclick=()=>setEarningState(Number(b.dataset.earningState),b.dataset.nextState));
  $("reward-list").querySelectorAll("[data-earning-history]").forEach(b=>b.onclick=()=>showEarningHistory(Number(b.dataset.earningHistory)));
}
async function setEarningState(id,state){
  const note=prompt("یادداشت این تغییر را وارد کنید (اختیاری):")||"";
  try{await api(`/api/earnings/${id}/state`,{method:"PATCH",body:JSON.stringify({state,note})});toast("وضعیت درآمد به‌روزرسانی شد");refresh()}catch(e){toast(e.message)}
}
async function showEarningHistory(id){
  try{
    const rows=await api(`/api/earnings/${id}/history`);
    $("earnings-history-list").innerHTML=rows.length?rows.map(r=>`<div class="item"><div><b>${esc(statusFa(r.to_state))}</b><p>${esc(r.note||"بدون یادداشت")} · ${esc(new Date(r.created_at).toLocaleString("fa-IR"))}</p></div></div>`).join(""):'<div class="empty">سابقه‌ای ثبت نشده است.</div>';
    $("earnings-history-dialog").showModal();
  }catch(e){toast(e.message)}
}
function fillRewardOptions(){$("reward-opportunity").innerHTML='<option value="">بدون پیوند به فرصت</option>'+opportunities.map(o=>'<option value="'+o.id+'">'+esc(o.title)+'</option>').join("")}
$("competition-form").onsubmit=async e=>{
  e.preventDefault();
  const form=e.target,data=Object.fromEntries(new FormData(form));
  for(const key of ["terms_verified","automated_agents_allowed","official_api"])data[key]=form.elements[key].checked;
  data.prize_amount=data.prize_amount===""?null:Number(data.prize_amount);
  try{await api("/api/competitions",{method:"POST",body:JSON.stringify(data)});form.reset();toast("مسابقه ثبت شد؛ اکنون استراتژی بسازید");refresh()}catch(err){toast(err.message)}
};
$("add-opportunity").onclick=()=>$("opportunity-dialog").showModal();
$("add-source").onclick=()=>$("source-dialog").showModal();
$("save-owner-token").onclick=()=>{const value=$("owner-token").value.trim();if(!value){sessionStorage.removeItem("autoearn_owner_token");toast("رمز مالک برای این نشست پاک شد");return}sessionStorage.setItem("autoearn_owner_token",value);toast("رمز مالک برای این نشست ذخیره شد");refresh().catch(e=>toast(e.message))};
$("add-discovery-feed").onclick=async()=>{
  const name=prompt("نام این خبرخوان را وارد کنید:");
  if(!name)return;
  const feed_url=prompt("نشانی مستقیم RSS یا Atom با HTTPS:");
  if(!feed_url)return;
  const domains=prompt("دامنهٔ دقیق خبرخوان و دامنهٔ لینک‌های داخل آن (با ویرگول جدا کنید):");
  if(!domains)return;
  const categoryChoice=prompt("دسته‌بندی: ۱ مسابقه، ۲ نظرسنجی و کارهای کوچک، ۳ فریلنسری، ۴ محصولات دیجیتال، ۵ سایر","۲");
  const category=({"۱":"games_competitions","1":"games_competitions","۲":"surveys_microtasks","2":"surveys_microtasks","۳":"freelancing_services","3":"freelancing_services","۴":"ai_content_products","4":"ai_content_products","۵":"other","5":"other"})[(categoryChoice||"").trim()];
  if(!category){toast("دسته‌بندی معتبر نیست");return;}
  try{
    await api("/api/discovery/feeds",{method:"POST",body:JSON.stringify({name,feed_url,category,allowed_domains:domains.split(",").map(x=>x.trim()).filter(Boolean),max_items:30})});
    toast("خبرخوان ثبت شد و تا زمان تأیید شما غیرفعال می‌ماند");refresh();
  }catch(error){toast(error.message)}
};
$("save-discovery-scheduler").onclick=async()=>{
  try{
    discoveryScheduler=await api("/api/discovery/scheduler",{method:"PATCH",body:JSON.stringify({
      enabled:$("discovery-scheduler-enabled").checked,
      interval_minutes:Number($("discovery-scheduler-interval").value)
    })});
    renderDiscoveryScheduler();
    toast("تنظیمات کشف خودکار ذخیره شد");
  }catch(error){toast(error.message)}
};
$("run-discovery").onclick=async()=>{
  if(!confirm("همهٔ خبرخوان‌های تأییدشده بررسی شوند؟ موارد تازه فقط به صف بررسی اضافه می‌شوند."))return;
  try{
    const result=await api("/api/discovery/run",{method:"POST"});
    toast("بررسی تمام شد؛ منابع تازه: "+result.inserted_count+"، تکراری: "+result.duplicate_count+"، خبرخوان موفق: "+result.successful_feed_count);
    refresh();
  }catch(error){toast(error.message)}
};
$("discover-rss").onclick=async()=>{
  const feed_url=prompt("نشانی فهرست خبرخوان عمومی با اتصال امن:");
  if(!feed_url)return;
  const domains=prompt("نام دقیق دامنه‌های مجاز، جداشده با ویرگول (دامنهٔ فهرست و آگهی‌ها را وارد کنید):");
  if(!domains)return;
  const categoryChoice=prompt("شمارهٔ دسته‌بندی را وارد کنید:\n۱. بازی و مسابقه\n۲. نظرسنجی و کارهای کوچک\n۳. فریلنسری و خدمات\n۴. محتوای هوش مصنوعی و محصولات دیجیتال\n۵. سایر","۲");
  if(!categoryChoice)return;
  const category=({"۱":"games_competitions","1":"games_competitions","۲":"surveys_microtasks","2":"surveys_microtasks","۳":"freelancing_services","3":"freelancing_services","۴":"ai_content_products","4":"ai_content_products","۵":"other","5":"other"})[categoryChoice.trim()];
  if(!category){toast("شماره‌ای بین ۱ تا ۵ وارد کنید");return;}
  try{
    const result=await api("/api/discovery/rss",{method:"POST",body:JSON.stringify({
      adapter_id:"manual-feed-"+Date.now(),display_name:"فهرست خبرخوان: "+feed_url,
      feed_url,category,allowed_domains:domains.split(",").map(x=>x.trim()).filter(Boolean)
    })});
    toast("تعداد موارد پیدا‌شده: "+result.discovered_count+" مورد؛ ذخیره‌شده به‌عنوان منبع در انتظار بررسی: "+result.inserted_count+"");
    refresh();
  }catch(e){toast(e.message)}
};
$("add-reward").onclick=()=>$("reward-dialog").showModal();
document.querySelectorAll("[data-close]").forEach(b=>b.onclick=()=>b.closest("dialog").close());
$("opportunity-form").onsubmit=async e=>{e.preventDefault();const data=Object.fromEntries(new FormData(e.target));for(const key of ["eligible_countries","excluded_countries","payout_methods"])data[key]=String(data[key]||"").split(",").map(x=>x.trim()).filter(Boolean);data.minimum_withdrawal_amount=data.minimum_withdrawal_amount===""?null:Number(data.minimum_withdrawal_amount);try{await api("/api/opportunities",{method:"POST",body:JSON.stringify(data)});e.target.closest("dialog").close();e.target.reset();toast("فرصت ذخیره شد");refresh()}catch(err){toast(err.message)}};
$("source-form").onsubmit=async e=>{e.preventDefault();const data=Object.fromEntries(new FormData(e.target));try{await api("/api/sources",{method:"POST",body:JSON.stringify(data)});e.target.closest("dialog").close();e.target.reset();toast("منبع برای بررسی ذخیره شد");refresh()}catch(err){toast(err.message)}};
$("evaluation-form").onsubmit=async e=>{
  e.preventDefault();
  const data=Object.fromEntries(new FormData(e.target));
  data.opportunity_id=Number(data.opportunity_id);
  data.source_id=Number(data.source_id);
  for(const field of ["reward_amount","estimated_minutes","payment_probability","risk_score"])
    data[field]=data[field]===""?null:Number(data[field]);
  for(const field of ["estimated_cost","payout_fee_fixed","payout_fee_percent","conversion_fee_percent"])
    data[field]=Number(data[field]||0);
  data.evidence=String(data.evidence||"").split("\n").map(x=>x.trim()).filter(Boolean);
  const form=e.target;
  const aiFields=[
    "requires_physical_presence","requires_personal_experience",
    "requires_identity_attestation","requires_captcha",
    "requires_live_human_interaction","contains_sensitive_personal_data",
    "repetitive_information_processing","output_is_objectively_verifiable",
    "human_signoff_required"
  ];
  data.ai_task_profile={title:opportunities.find(o=>o.id===data.opportunity_id)?.title||"Opportunity task",
    ai_permission:data.ai_permission||"unknown"};
  for(const field of aiFields)data.ai_task_profile[field]=form.elements[field].checked;
  delete data.ai_permission;
  try{
    const result=await api("/api/opportunities/"+data.opportunity_id+"/evaluate",{method:"POST",body:JSON.stringify(data)});
    const value=result.evaluation;
    $("evaluation-dialog").close();
    alert("وضعیت صلاحیت: "+statusFa(value.eligibility)+
      "\nمیزان اطمینان: "+value.confidence+"/100"+
      "\nامتیاز رتبه‌بندی: "+value.ranking_score+"/100"+
      "\nخالص در صورت پرداخت: "+(value.net_reward_estimate==null?"نامشخص":value.net_reward_estimate+" "+currencyFa(value.currency))+
      "\nدرآمد مورد انتظار با احتمال پرداخت: "+(value.expected_net_reward_estimate==null?"نامشخص":value.expected_net_reward_estimate+" "+currencyFa(value.currency))+
      "\nدرآمد ساعتی مورد انتظار: "+(value.expected_net_hourly_estimate==null?"نامشخص":value.expected_net_hourly_estimate+" "+currencyFa(value.currency)+" در ساعت")+
      "\nاحتمال پرداخت ثبت‌شده: "+(value.payment_probability_percent==null?"نامشخص":value.payment_probability_percent+"٪")+
      "\nدرآمد خالص ساعتی در صورت پرداخت: "+(value.net_hourly_estimate==null?"نامشخص":value.net_hourly_estimate+" "+currencyFa(value.currency)+" در ساعت")+
      "\nکارمزد برداشت تخمینی: "+money(value.payout_fee_estimate,value.currency)+
      "\nکارمزد تبدیل تخمینی: "+money(value.conversion_fee_estimate,value.currency)+
      "\nوضعیت حداقل برداشت: "+(value.withdrawal_threshold_currency_mismatch?"نامشخص؛ ارز متفاوت است":value.withdrawal_reachable_estimate===null?"حداقل برداشت قابل محاسبه نیست":value.withdrawal_reachable_estimate?"قابل دستیابی":"کمتر از حداقل برداشت")+
      "\nآمادگی اجرا: "+(value.execution_allowed?"پیش‌نیازها فراهم است":"مسدود است")+
      "\nارزیابی AI: "+(value.ai_task_assessment?value.ai_task_assessment.suitability:"ثبت نشده")+
      "\nنقش مجاز AI: "+(value.ai_task_assessment?.permitted_ai_role||"—")+
      "\n\nهشدارها:\n"+(value.risk_flags.map(riskFlagFa).join("\n")||"بدون هشدار")+
      "\n\nهیچ اقدامی در پلتفرم انجام نشد.");
  }catch(err){toast(err.message)}
};
$("reward-form").onsubmit=async e=>{e.preventDefault();const data=Object.fromEntries(new FormData(e.target));data.opportunity_id=data.opportunity_id?Number(data.opportunity_id):null;data.amount=Number(data.amount);try{await api("/api/earnings",{method:"POST",body:JSON.stringify(data)});e.target.closest("dialog").close();e.target.reset();toast("درآمد در دفتر درآمد ذخیره شد");refresh()}catch(err){toast(err.message)}};
$("prioritize-discovery").onclick=loadPrioritizedDiscovery;$("rank-opportunities").onclick=loadRankedOpportunities;$("source-filter").onchange=renderSources;$("search").oninput=renderOpportunities;$("filter").onchange=renderOpportunities;$("verification-filter").onchange=renderOpportunities;
refresh().catch(e=>toast(e.message));
setInterval(()=>refresh().catch(()=>{}),60000);