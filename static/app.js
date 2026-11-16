const $ = (id) => document.getElementById(id);
const api = async (path, options={}) => {
  const response = await fetch(path, {headers:{"Content-Type":"application/json"}, ...options});
  const body = await response.json().catch(()=>({detail:"پاسخ غیرمنتظره از سرور"}));
  if (!response.ok) throw new Error(body.detail || "درخواست ناموفق بود");
  return body;
};
const money = (n,c="USD") => new Intl.NumberFormat("fa-IR",{style:"currency",currency:c}).format(n);
function toast(message){const el=$("toast");el.textContent=message;el.classList.add("show");setTimeout(()=>el.classList.remove("show"),2600)}
function esc(s=""){return String(s).replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]))}
let opportunities=[];
const faStatus = value => ({
  pending_approval:"در انتظار تأیید",approved:"تأییدشده",completed:"تکمیل‌شده",
  discovered:"کشف‌شده",reviewing:"در حال بررسی",eligible:"واجد شرایط",
  ineligible:"فاقد شرایط",archived:"بایگانی‌شده",pending:"در انتظار",
  confirmed:"تأییدشده",paid:"پرداخت‌شده",rejected:"ردشده"
}[value] || value);
const faCategory = value => ({
  all:"همه",games:"بازی‌ها",surveys:"نظرسنجی‌ها",user_testing:"آزمایش کاربری",
  microtasks:"کارهای خرد",freelance:"آزادکاری",cashback:"بازگشت وجه",
  affiliate:"همکاری در فروش",creator:"تولید محتوا",tutoring:"تدریس",
  digital_products:"محصولات دیجیتال",research:"پژوهش",bug_bounty:"پاداش کشف آسیب‌پذیری",
  game:"بازی",mobile:"اپلیکیشن موبایل",skill:"مهارت / رقابت",
  survey:"نظرسنجی / پیشنهاد",other:"سایر"
}[value] || value);
async function refresh(){
  const [dash,opps,tasks,rewards]=await Promise.all([api("/api/dashboard"),api("/api/opportunities"),api("/api/tasks"),api("/api/rewards")]);
  opportunities=opps;
  $("stat-opps").textContent=dash.opportunities;$("stat-tasks").textContent=dash.tasks;
  $("stat-approval").textContent=dash.awaiting_approval;$("stat-paid").textContent=money(dash.paid_total);
  $("stat-pending").textContent="در انتظار: "+money(dash.pending_total);
  renderOpportunities();renderTasks(tasks);renderRewards(rewards);fillRewardOptions();
}
function renderOpportunities(){
  const q=$("search").value.toLowerCase(),status=$("filter").value;
  const rows=opportunities.filter(o=>(!status||o.status===status)&&[o.title,o.platform,o.category].some(x=>x.toLowerCase().includes(q)));
  $("opportunity-list").innerHTML=rows.length?rows.map(o=>`<div class="item"><div><h3><span data-no-translate>${esc(o.title)}</span> <span class="pill">${esc(faStatus(o.status))}</span></h3><p><span data-no-translate>${esc(o.platform)}</span> · ${esc(faCategory(o.category))} · امتیاز بررسی ${o.score}/60<br><a href="${esc(o.url)}" target="_blank" rel="noopener noreferrer">بازکردن پلتفرم ↗</a> ${o.terms_url?'· <a href="'+esc(o.terms_url)+'" target="_blank" rel="noopener noreferrer">قوانین ↗</a>':''}<br><span data-no-translate>${esc(o.reward_description||"جزئیات پاداش وارد نشده")}</span></p></div><div class="item-actions"><button class="secondary" data-task="${o.id}">ایجاد کار</button><button class="secondary" data-status="${o.id}" data-next="reviewing">بررسی</button></div></div>`).join(""):'<div class="empty">فرصتی با این مشخصات پیدا نشد.</div>';
  $("opportunity-list").querySelectorAll("[data-task]").forEach(b=>b.onclick=()=>createTask(Number(b.dataset.task)));
  $("opportunity-list").querySelectorAll("[data-status]").forEach(b=>b.onclick=()=>setStatus(Number(b.dataset.status),b.dataset.next));
}
async function createTask(id){const description=prompt("فعالیتی را که قصد انجامش را دارید شرح دهید. دستیار بدون تأیید شما بازی یا چیزی ارسال نمی‌کند:");if(!description)return;try{await api("/api/tasks",{method:"POST",body:JSON.stringify({opportunity_id:id,description})});toast("کار به صف تأیید اضافه شد");refresh()}catch(e){toast(e.message)}}
async function setStatus(id,status){try{await api(`/api/opportunities/${id}/status?status=${status}`,{method:"PATCH"});refresh()}catch(e){toast(e.message)}}
function renderTasks(tasks){$("task-list").innerHTML=tasks.length?tasks.map(t=>`<div class="item"><div><h3><span data-no-translate>${esc(t.description)}</span></h3><p><span data-no-translate>${esc(t.opportunity_title)} · ${esc(t.platform)}</span> · ${esc(faStatus(t.status))}</p></div><div class="item-actions">${t.status==="pending_approval"?'<button class="primary" data-approve="'+t.id+'">تأیید کار</button>':''}${t.status==="approved"?'<button class="secondary" data-complete="'+t.id+'">علامت‌گذاری به‌عنوان تکمیل‌شده</button>':''}</div></div>`).join(""):'<div class="empty">هنوز کاری ثبت نشده است. از یک فرصت، کار جدید ایجاد کنید.</div>';
  $("task-list").querySelectorAll("[data-approve]").forEach(b=>b.onclick=async()=>{if(!confirm("این کار را تأیید می‌کنید؟ رعایت قوانین پلتفرم همچنان بر عهده شماست."))return;try{await api(`/api/tasks/${b.dataset.approve}/approve`,{method:"POST"});toast("کار تأیید شد")}catch(e){toast(e.message)}refresh()});
  $("task-list").querySelectorAll("[data-complete]").forEach(b=>b.onclick=async()=>{try{await api(`/api/tasks/${b.dataset.complete}/complete`,{method:"POST"});toast("کار به‌عنوان تکمیل‌شده علامت خورد")}catch(e){toast(e.message)}refresh()});
}
function renderRewards(rows){$("reward-list").innerHTML=rows.length?rows.map(r=>`<div class="item"><div><h3>${money(r.amount,r.currency)} <span class="pill">${esc(faStatus(r.status))}</span></h3><p><span data-no-translate>${esc(r.opportunity_title||"پاداش بدون پیوند")} · ${esc(r.reference)}</span></p></div></div>`).join(""):'<div class="empty">هنوز پاداشی ثبت نشده است.</div>'}
function fillRewardOptions(){$("reward-opportunity").innerHTML='<option value="">بدون پیوند</option>'+opportunities.map(o=>'<option data-no-translate value="'+o.id+'">'+esc(o.title)+'</option>').join("")}
$("add-opportunity").onclick=()=>$("opportunity-dialog").showModal();
$("add-reward").onclick=()=>$("reward-dialog").showModal();
document.querySelectorAll("[data-close]").forEach(b=>b.onclick=()=>b.closest("dialog").close());
$("opportunity-form").onsubmit=async e=>{e.preventDefault();const data=Object.fromEntries(new FormData(e.target));try{await api("/api/opportunities",{method:"POST",body:JSON.stringify(data)});e.target.closest("dialog").close();e.target.reset();toast("فرصت ذخیره شد");refresh()}catch(err){toast(err.message)}};
$("reward-form").onsubmit=async e=>{e.preventDefault();const data=Object.fromEntries(new FormData(e.target));data.opportunity_id=data.opportunity_id?Number(data.opportunity_id):null;data.amount=Number(data.amount);try{await api("/api/rewards",{method:"POST",body:JSON.stringify(data)});e.target.closest("dialog").close();e.target.reset();toast("پاداش ثبت شد");refresh()}catch(err){toast(err.message)}};
$("search").oninput=renderOpportunities;$("filter").onchange=renderOpportunities;

const discoveryForm=$("discovery-form");
if(discoveryForm){
  discoveryForm.onsubmit=async e=>{
    e.preventDefault();
    const button=$("discover-button"), results=$("discovery-results");
    button.disabled=true;button.textContent="در حال جست‌وجو…";
    results.className="empty";results.textContent="در حال جست‌وجو در منابع عمومی…";
    try{
      const found=await api("/api/discover",{method:"POST",body:JSON.stringify({
        query:$("discovery-query").value,
        category:$("discovery-category").value,
        limit:20
      })});
      results.className="";
      results.innerHTML=found.length?found.map(item=>`<div class="item"><div><h3><span data-no-translate>${esc(item.title)}</span> <span class="pill">${esc(faCategory(item.category||"all"))}</span></h3><p><span data-no-translate>${esc(item.domain)}</span> · شاخص کشف: ${item.confidence}/100 · تأییدنشده<br><span data-no-translate>${esc(item.snippet||"خلاصه‌ای از منبع ارائه نشده است")}</span><br><a href="${esc(item.url)}" target="_blank" rel="noopener noreferrer">مشاهده منبع ↗</a></p></div><span class="pill">نیازمند بررسی انسانی</span></div>`).join(""):'<div class="empty">نتیجه‌ای پیدا نشد. عبارت گسترده‌تر یا دسته دیگری را امتحان کنید.</div>';
      toast(found.length+" فرصت احتمالی پیدا شد");
    }catch(err){results.className="empty";results.textContent=err.message;toast(err.message)}
    finally{button.disabled=false;button.textContent="جست‌وجوی فرصت‌ها"}
  };
}

refresh().catch(e=>toast(e.message));
