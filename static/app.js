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
const statusFa = (v) => ({game_rewards:"پاداش بازی",survey_rewards:"پاداش نظرسنجی",microtasks:"کارهای کوچک",freelance_jobs:"کارهای آزاد",digital_products:"محصولات دیجیتال",discovered:"کشف‌شده",reviewing:"در حال بررسی",eligible:"مجاز",ineligible:"غیرمجاز",archived:"بایگانی‌شده",pending:"در انتظار",approved:"تأییدشده",rejected:"ردشده",verified:"تأییدشده",pending_approval:"در انتظار تأیید",confirmed:"تأییدشده",paid:"پرداخت‌شده",manual:"دستی",assist:"با کمک دستیار",official_api:"رابط رسمی برنامه‌نویسی",games_competitions:"بازی و مسابقه",surveys_microtasks:"نظرسنجی و کارهای کوچک",freelancing_services:"فریلنسری و خدمات",ai_content_products:"محتوای هوش مصنوعی و محصولات دیجیتال",other:"سایر","unknown":"نامشخص"})[v]||"نامشخص";
const currencyFa = (c) => ({EUR:"یورو",USD:"دلار آمریکا",GBP:"پوند",TRY:"لیر",IRR:"ریال",CAD:"دلار کانادا",AUD:"دلار استرالیا"})[String(c||"").toUpperCase()] || "واحد پول";
const money = (n,c="EUR") => new Intl.NumberFormat("fa-IR",{maximumFractionDigits:2}).format(Number(n||0))+" "+currencyFa(c);
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
  "time estimate is missing or invalid":"برآورد زمان ثبت نشده یا معتبر نیست",
  "advertised reward is unknown":"مبلغ پاداش اعلام‌شده مشخص نیست",
  "risk assessment is missing":"ارزیابی ریسک انجام نشده است",
  "automatic execution is unavailable for this execution mode":"اجرای خودکار در روش انتخاب‌شده مجاز نیست"
})[v]||"هشدار دیگری ثبت شده است";
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
  $("stat-pending").textContent="در انتظار: "+money(dash.pending_total);
  renderOpportunities();renderSources();renderTasks(tasks);renderRewards(rewards);fillRewardOptions();
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
        پاداش خالص: ${e.net_reward_estimate==null?"نامشخص":esc(e.net_reward_estimate)+" "+(e.currency?currencyFa(e.currency):"")}<br>
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
function renderTasks(tasks){$("task-list").innerHTML=tasks.length?tasks.map(t=>`<div class="item"><div><h3>${esc(t.description)}</h3><p>${esc(t.opportunity_title)} · ${esc(t.platform)} · ${esc(statusFa(t.status))}</p></div><div class="item-actions">${t.status==="pending_approval"?'<button class="primary" data-approve="'+t.id+'">تأیید کار</button>':''}${t.status==="approved"?'<button class="secondary" data-complete="'+t.id+'">علامت‌گذاری به‌عنوان تکمیل‌شده</button>':''}</div></div>`).join(""):'<div class="empty">هنوز کاری ثبت نشده است. از یک فرصت، کار جدید بسازید.</div>';
  $("task-list").querySelectorAll("[data-approve]").forEach(b=>b.onclick=async()=>{if(!confirm("این کار را تأیید می‌کنید؟ مسئولیت رعایت قوانین پلتفرم همچنان با شماست."))return;try{await api(`/api/tasks/${b.dataset.approve}/approve`,{method:"POST"});toast("کار تأیید شد")}catch(e){toast(e.message)}refresh()});
  $("task-list").querySelectorAll("[data-complete]").forEach(b=>b.onclick=async()=>{try{await api(`/api/tasks/${b.dataset.complete}/complete`,{method:"POST"});toast("کار به‌عنوان تکمیل‌شده ثبت شد")}catch(e){toast(e.message)}refresh()});
}
function renderRewards(rows){$("reward-list").innerHTML=rows.length?rows.map(r=>`<div class="item"><div><h3>${money(r.amount,r.currency)} <span class="pill">${esc(statusFa(r.status))}</span></h3><p>${esc(r.opportunity_title||"درآمد بدون پیوند")} · ${esc(r.reference||"بدون توضیح")}</p></div></div>`).join(""):'<div class="empty">هنوز درآمدی ثبت نشده است.</div>'}
function fillRewardOptions(){$("reward-opportunity").innerHTML='<option value="">بدون پیوند به فرصت</option>'+opportunities.map(o=>'<option value="'+o.id+'">'+esc(o.title)+'</option>').join("")}
$("add-opportunity").onclick=()=>$("opportunity-dialog").showModal();
$("add-source").onclick=()=>$("source-dialog").showModal();
$("save-owner-token").onclick=()=>{const value=$("owner-token").value.trim();if(!value){sessionStorage.removeItem("autoearn_owner_token");toast("رمز مالک برای این نشست پاک شد");return}sessionStorage.setItem("autoearn_owner_token",value);toast("رمز مالک برای این نشست ذخیره شد");refresh().catch(e=>toast(e.message))};
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
  data.estimated_cost=Number(data.estimated_cost||0);
  data.evidence=String(data.evidence||"").split("\n").map(x=>x.trim()).filter(Boolean);
  try{
    const result=await api("/api/opportunities/"+data.opportunity_id+"/evaluate",{method:"POST",body:JSON.stringify(data)});
    const value=result.evaluation;
    $("evaluation-dialog").close();
    alert("وضعیت صلاحیت: "+statusFa(value.eligibility)+
      "\nمیزان اطمینان: "+value.confidence+"/100"+
      "\nامتیاز رتبه‌بندی: "+value.ranking_score+"/100"+
      "\nپاداش خالص تخمینی: "+(value.net_reward_estimate==null?"نامشخص":value.net_reward_estimate+" "+currencyFa(value.currency))+
      "\nدرآمد خالص ساعتی تخمینی: "+(value.net_hourly_estimate==null?"نامشخص":value.net_hourly_estimate+" "+currencyFa(value.currency)+" در ساعت")+
      "\nآمادگی اجرا: "+(value.execution_allowed?"پیش‌نیازها فراهم است":"مسدود است")+
      "\n\nهشدارها:\n"+(value.risk_flags.map(riskFlagFa).join("\n")||"بدون هشدار")+
      "\n\nهیچ اقدامی در پلتفرم انجام نشد.");
  }catch(err){toast(err.message)}
};
$("reward-form").onsubmit=async e=>{e.preventDefault();const data=Object.fromEntries(new FormData(e.target));data.opportunity_id=data.opportunity_id?Number(data.opportunity_id):null;data.amount=Number(data.amount);try{await api("/api/rewards",{method:"POST",body:JSON.stringify(data)});e.target.closest("dialog").close();e.target.reset();toast("درآمد ثبت شد");refresh()}catch(err){toast(err.message)}};
$("source-filter").onchange=renderSources;$("search").oninput=renderOpportunities;$("filter").onchange=renderOpportunities;$("verification-filter").onchange=renderOpportunities;
refresh().catch(e=>toast(e.message));
