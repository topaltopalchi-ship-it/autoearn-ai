const $ = (id) => document.getElementById(id);
let authPromptInFlight = null;
const api = async (path, options={}, retry=true) => {
  const headers = {"Content-Type":"application/json", ...(options.headers||{})};
  const response = await fetch(path, {...options, headers});
  const body = await response.json().catch(()=>({detail:"پاسخ غیرمنتظره از سرور"}));
  if (response.status === 401 && retry && path !== "/api/auth/login") {
    if (!authPromptInFlight) {
      authPromptInFlight = (async()=>{
        const password = prompt("برای ادامه، رمز مالک AutoEarn AI را وارد کنید:");
        if (!password) throw new Error("ورود لغو شد.");
        await api("/api/auth/login", {method:"POST", body:JSON.stringify({password})}, false);
      })().finally(()=>{authPromptInFlight=null;});
    }
    await authPromptInFlight;
    return api(path, options, false);
  }
  if (!response.ok) throw new Error(body.detail || "درخواست ناموفق بود");
  return body;
};
const money = (n,c="USD") => new Intl.NumberFormat("fa-IR",{style:"currency",currency:c}).format(n);
function toast(message){const el=$("toast");el.textContent=message;el.classList.add("show");setTimeout(()=>el.classList.remove("show"),2600)}
function esc(s=""){return String(s).replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]))}
let opportunities=[];
let discoveryItems=[];
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
  const country=($("ranking-country")?.value||"").trim().toUpperCase();
  const rankingUrl="/api/opportunities/ranked"+(country?("?country="+encodeURIComponent(country)):"");
  const [dash,opps,tasks,rewards]=await Promise.all([api("/api/dashboard"),api(rankingUrl),api("/api/tasks"),api("/api/rewards")]);
  opportunities=opps;
  $("stat-opps").textContent=dash.opportunities;$("stat-tasks").textContent=dash.tasks;
  $("stat-approval").textContent=dash.awaiting_approval;$("stat-paid").textContent=money(dash.paid_total);
  $("stat-pending").textContent="در انتظار: "+money(dash.pending_total);
  renderOpportunities();renderTasks(tasks);renderRewards(rewards);fillRewardOptions();
}
function renderOpportunities(){
  const q=$("search").value.toLowerCase(),status=$("filter").value;
  const rows=opportunities.filter(o=>(!status||o.status===status)&&[o.title,o.platform,o.category].some(x=>x.toLowerCase().includes(q)));
  $("opportunity-list").innerHTML=rows.length?rows.map(o=>`<div class="item"><div><h3><span data-no-translate>${esc(o.title)}</span> <span class="pill">${esc(faStatus(o.status))}</span></h3><p><span data-no-translate>${esc(o.platform)}</span> · ${esc(faCategory(o.category))} · رتبه تناسب ${o.ranking?.ranking_score ?? "—"}/100 · پوشش داده ${o.ranking?.data_coverage ?? 0}%<br><a href="${esc(o.url)}" target="_blank" rel="noopener noreferrer">بازکردن پلتفرم ↗</a> ${o.terms_url?'· <a href="'+esc(o.terms_url)+'" target="_blank" rel="noopener noreferrer">قوانین ↗</a>':''}<br><span data-no-translate>${esc(o.reward_description||"جزئیات پاداش وارد نشده")}</span></p></div><div class="item-actions"><button class="secondary" data-task="${o.id}">ایجاد کار</button><button class="secondary" data-status="${o.id}" data-next="reviewing">بررسی</button></div></div>`).join(""):'<div class="empty">فرصتی با این مشخصات پیدا نشد.</div>';
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
$("opportunity-form").onsubmit=async e=>{e.preventDefault();const data=Object.fromEntries(new FormData(e.target));for(const key of ["estimated_reward","estimated_hours","minimum_payout","risk_score"])data[key]=data[key]===""?null:Number(data[key]);try{await api("/api/opportunities",{method:"POST",body:JSON.stringify(data)});e.target.closest("dialog").close();e.target.reset();toast("فرصت ذخیره شد");refresh()}catch(err){toast(err.message)}};
$("reward-form").onsubmit=async e=>{e.preventDefault();const data=Object.fromEntries(new FormData(e.target));data.opportunity_id=data.opportunity_id?Number(data.opportunity_id):null;data.amount=Number(data.amount);try{await api("/api/rewards",{method:"POST",body:JSON.stringify(data)});e.target.closest("dialog").close();e.target.reset();toast("پاداش ثبت شد");refresh()}catch(err){toast(err.message)}};
$("search").oninput=renderOpportunities;$("filter").onchange=renderOpportunities;
$("ranking-country").onchange=()=>refresh().catch(err=>toast(err.message));

const riskForm=$("risk-form");
if(riskForm){
  riskForm.onsubmit=async e=>{
    e.preventDefault();
    const button=riskForm.querySelector('button[type="submit"]');
    const result=$("risk-result");
    const signals=Object.fromEntries(
      [...riskForm.querySelectorAll('input[type="checkbox"]')].map(input=>[input.name,input.checked])
    );
    button.disabled=true;
    result.className="empty";
    result.textContent="در حال ارزیابی نشانه‌ها…";
    try{
      const assessment=await api("/api/risk-assessments",{
        method:"POST",
        body:JSON.stringify(signals)
      });
      const level=assessment.risk_level==="high"?"ریسک بالا":
        assessment.risk_level==="medium"?"ریسک متوسط":"ریسک پایین";
      const riskLabels={
        upfront_payment:"درخواست پرداخت هزینه اولیه",
        deposit_or_top_up:"الزام به واریز وجه یا شارژ حساب",
        guaranteed_high_returns:"وعده سود غیرواقعی یا درآمد تضمینی",
        referral_required_to_withdraw:"اجبار به دعوت افراد برای برداشت",
        unclear_or_missing_terms:"نامشخص بودن قوانین و شرایط",
        missing_payout_threshold:"نامشخص بودن حداقل مبلغ برداشت",
        crypto_only_payout:"پرداخت صرفاً از طریق رمزارز",
        requests_sensitive_data_early:"درخواست زودهنگام اطلاعات حساس",
        asks_to_move_off_platform:"هدایت پرداخت یا گفتگو به خارج از پلتفرم",
        unrealistic_time_pressure:"فشار زمانی غیرمنطقی برای تصمیم‌گیری"
      };
      const flags=assessment.flags.length
        ? assessment.flags.map(flag=>'<li>'+esc(riskLabels[flag.code]||flag.reason)+' (+'+flag.weight+')</li>').join("")
        : "<li>هیچ‌یک از نشانه‌های انتخاب‌شده شناسایی نشد.</li>";
      result.className="risk-result";
      result.innerHTML='<div class="risk-score"><strong>'+assessment.risk_score+'/100</strong><span>'+level+'</span></div>'+
        '<p>این چک‌لیست فقط راهنمای اولیه است؛ امتیاز پایین، معتبر بودن یا بی‌خطر بودن پلتفرم را ثابت نمی‌کند.</p><ul>'+flags+'</ul>'+
        '<p class="risk-warning">این نتیجه اعتبار پلتفرم را تأیید نمی‌کند. پیش از ثبت‌نام، قوانین رسمی و هویت گرداننده را مستقل بررسی کنید.</p>';
    }catch(error){
      result.className="empty";
      result.textContent=error.message;
    }finally{
      button.disabled=false;
    }
  };
}

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
      discoveryItems=found;
      renderDiscoveryResults();
      toast(found.length+" فرصت احتمالی پیدا شد");
    }catch(err){results.className="empty";results.textContent=err.message;toast(err.message)}
    finally{button.disabled=false;button.textContent="جست‌وجوی فرصت‌ها"}
  };
}

function renderDiscoveryResults(){
  const results=$("discovery-results");
  results.className="";
  results.innerHTML=discoveryItems.length?discoveryItems.map(item=>{
    const status=item.review_status||"pending";
    let actions="";
    if(item.promoted_opportunity_id){
      actions='<span class="pill">به فرصت‌های من افزوده شد</span>';
    }else if(status==="accepted"){
      actions='<button class="primary" data-promote="'+item.id+'">افزودن به فرصت‌های من</button>';
    }else if(status==="rejected"){
      actions='<span class="pill">ردشده</span>';
    }else{
      actions='<span class="pill">نیازمند بررسی انسانی</span><button class="secondary" data-accept="'+item.id+'">تأیید برای بررسی</button><button class="secondary" data-reject="'+item.id+'">رد فرصت</button>';
    }
    return '<div class="item"><div><h3><span data-no-translate>'+esc(item.title)+'</span> <span class="pill">'+esc(faCategory(item.category||"all"))+'</span></h3><p><span data-no-translate>'+esc(item.domain)+'</span> · شاخص کشف: '+item.confidence+'/100 · اولویت بررسی انسانی: '+(item.review_priority?.review_priority_score??"—")+'/100 · <strong>تأییدنشده</strong><br><span data-no-translate>'+esc(item.snippet||"خلاصه‌ای از منبع ارائه نشده است")+'</span><br><a href="'+esc(item.url)+'" target="_blank" rel="noopener noreferrer">مشاهده منبع ↗</a></p></div><div class="item-actions">'+actions+'</div></div>';
  }).join(""):'<div class="empty">نتیجه‌ای پیدا نشد. عبارت گسترده‌تر یا دسته دیگری را امتحان کنید.</div>';
  results.querySelectorAll("[data-accept]").forEach(button=>button.onclick=()=>updateCandidateReview(Number(button.dataset.accept),"accepted"));
  results.querySelectorAll("[data-reject]").forEach(button=>button.onclick=()=>updateCandidateReview(Number(button.dataset.reject),"rejected"));
  results.querySelectorAll("[data-promote]").forEach(button=>button.onclick=()=>promoteCandidate(Number(button.dataset.promote)));
}

async function updateCandidateReview(id,status){
  try{
    const updated=await api("/api/discoveries/"+id+"/review",{
      method:"PATCH",
      body:JSON.stringify({status,note:status==="accepted"?"انتخاب دستی کاربر برای افزودن به فهرست شخصی؛ بررسی اعتبار همچنان لازم است.":"ردشده توسط کاربر"})
    });
    const item=discoveryItems.find(candidate=>candidate.id===id);
    if(item)item.review_status=updated.review_status;
    renderDiscoveryResults();
    toast(status==="accepted"?"برای انتقال انتخاب شد؛ هنوز تأیید اعتبار نشده است.":"فرصت رد شد.");
  }catch(error){toast(error.message)}
}

async function promoteCandidate(id){
  if(!confirm("این فرصت به فهرست شخصی اضافه شود؟ مبلغ و شرایط نامشخص خالی می‌مانند و این کار اعتبار پلتفرم را تأیید نمی‌کند."))return;
  try{
    const result=await api("/api/discoveries/"+id+"/promote",{method:"POST"});
    const item=discoveryItems.find(candidate=>candidate.id===id);
    if(item)item.promoted_opportunity_id=result.opportunity.id;
    renderDiscoveryResults();
    toast(result.already_exists?"این نشانی از قبل ثبت شده بود و به آن پیوند خورد.":"فرصت به فهرست شخصی اضافه شد.");
    await refresh();
  }catch(error){toast(error.message)}
}



async function loadVault(){
  const root=$("vault-list");
  try{
    const rows=await api("/api/vault/credentials");
    root.className="";
    root.innerHTML=rows.length?rows.map(row=>'<div class="item"><div><h3>'+esc(row.label)+' <span class="pill">'+esc(row.credential_type)+'</span></h3><p>'+esc(row.provider)+' · ذخیره‌شده به‌صورت رمزگذاری‌شده · '+esc(row.updated_at)+'</p></div><div class="item-actions">'+(row.provider.trim().toLowerCase()==="openai"&&row.credential_type==="api_key"?'<button class="secondary" data-vault-test="'+row.id+'">آزمایش اتصال</button>':"")+'<button class="secondary" data-vault-update="'+row.id+'">جایگزینی کلید</button><button class="secondary" data-vault-delete="'+row.id+'">حذف</button></div></div>').join(""):'<div class="empty">هنوز کلیدی ذخیره نشده است.</div>';
    root.querySelectorAll("[data-vault-test]").forEach(button=>button.onclick=async()=>{
      const passphrase=prompt("برای آزمایش اتصال، عبارت اصلی خزانه را وارد کنید:");
      if(!passphrase)return;
      button.disabled=true;
      try{
        const result=await api("/api/vault/credentials/"+button.dataset.vaultTest+"/test-connection",{
          method:"POST",body:JSON.stringify({passphrase})
        });
        const labels={
          connected:"اتصال OpenAI موفق است.",
          invalid_credential:"کلید نامعتبر است.",
          insufficient_permissions:"کلید دسترسی لازم را ندارد.",
          rate_limited:"محدودیت درخواست سرویس؛ بعداً دوباره تلاش کنید.",
          timeout:"مهلت اتصال تمام شد.",
          provider_unreachable:"سرویس فعلاً در دسترس نیست.",
          unexpected_redirect:"پاسخ تغییرمسیر غیرمنتظره دریافت شد.",
          provider_error:"سرویس خطا برگرداند."
        };
        toast(labels[result.status]||"نتیجه آزمایش اتصال مشخص نیست.");
      }catch(error){toast(error.message)}
      finally{button.disabled=false}
    });
    root.querySelectorAll("[data-vault-update]").forEach(button=>button.onclick=async()=>{
      const secret=prompt("مقدار جدید را وارد کنید. مقدار قبلی قابل بازیابی از داشبورد نیست:");
      if(!secret)return;
      const passphrase=prompt("عبارت اصلی خزانه را وارد کنید:");
      if(!passphrase)return;
      try{
        await api("/api/vault/credentials/"+button.dataset.vaultUpdate,{method:"PUT",body:JSON.stringify({secret,passphrase})});
        toast("کلید جایگزین شد.");await loadVault();
      }catch(error){toast(error.message)}
    });
    root.querySelectorAll("[data-vault-delete]").forEach(button=>button.onclick=async()=>{
      const passphrase=prompt("برای حذف، عبارت اصلی خزانه را وارد کنید:");
      if(!passphrase)return;
      if(!confirm("این اطلاعات محرمانه برای همیشه از خزانه حذف شود؟"))return;
      try{
        await api("/api/vault/credentials/"+button.dataset.vaultDelete,{method:"DELETE",body:JSON.stringify({passphrase})});
        toast("اطلاعات حذف شد");await loadVault();
      }catch(error){toast(error.message)}
    });
  }catch(error){root.className="empty";root.textContent=error.message}
}
const vaultForm=$("vault-form");
if(vaultForm){
  vaultForm.onsubmit=async event=>{
    event.preventDefault();
    const button=vaultForm.querySelector('button[type="submit"]');
    const payload=Object.fromEntries(new FormData(vaultForm));
    button.disabled=true;
    try{
      await api("/api/vault/credentials",{method:"POST",body:JSON.stringify(payload)});
      vaultForm.reset();
      toast("کلید با موفقیت رمزگذاری و ذخیره شد.");
      await loadVault();
    }catch(error){toast(error.message)}
    finally{button.disabled=false}
  };
  $("refresh-vault").onclick=loadVault;
}

refresh().catch(e=>toast(e.message));
loadVault();
