(() => {
  const replacements = [
    ["Opportunity saved","فرصت ذخیره شد"],["Reward recorded","پاداش ثبت شد"],["pending_approval","در انتظار تأیید"],
    ["YOUR PLAY-AND-EARN COMMAND CENTER","مرکز مدیریت فرصت‌ها و درآمد"],
    ["Discover opportunities. Make informed decisions. Track every reward.","فرصت‌ها را پیدا کنید، آگاهانه تصمیم بگیرید و پاداش‌ها را پیگیری کنید."],
    ["AI WORKSPACE","محیط کاری هوشمند"],
    ["Human in control","کنترل در دست شماست"],
    ["Review platform rules and approve every task before participating.","پیش از هر فعالیت، قوانین پلتفرم را بررسی و کار را تأیید کنید."],
    ["Overview","نمای کلی"],["Opportunities","فرصت‌ها"],["Assisted tasks","کارهای با تأیید شما"],["Rewards","پاداش‌ها"],
    ["Local workspace","محیط محلی"],["Tracked platforms","پلتفرم‌های ثبت‌شده"],["Tasks created","کارهای ایجادشده"],
    ["Need your approval","نیازمند تأیید شما"],["Nothing runs without you","بدون تأیید شما کاری اجرا نمی‌شود"],
    ["Rewards paid","پاداش‌های پرداخت‌شده"],["Pending: ","در انتظار: "],
    ["MULTI-CATEGORY SEARCH","جست‌وجوی چنددسته‌ای"],["Discover earning opportunities","کشف فرصت‌های درآمدزایی"],
    ["What kind of opportunity are you looking for? e.g. remote work in Europe","دنبال چه نوع فرصتی هستید؟ مثلاً کار دورکاری در اروپا"],
    ["Opportunity category","دسته‌بندی فرصت"],["All opportunity types","همه دسته‌ها"],["Games and play rewards","بازی و پاداش بازی"],
    ["Surveys and market research","نظرسنجی و تحقیقات بازار"],["Website and app testing","آزمایش وب‌سایت و اپلیکیشن"],
    ["Microtasks and data labeling","کارهای خرد و برچسب‌گذاری داده"],["Freelance work","کار آزاد و پروژه‌ای"],
    ["Cashback and loyalty","کش‌بک و وفاداری مشتری"],["Affiliate programs","همکاری در فروش"],
    ["Creator monetization","درآمدزایی از تولید محتوا"],["Tutoring and teaching","تدریس و آموزش"],
    ["Digital products","محصولات دیجیتال"],["Paid research studies","مطالعات پژوهشی پولی"],["Responsible bug bounties","پاداش گزارش باگ مسئولانه"],
    ["Search opportunities","جست‌وجوی فرصت‌ها"],["Search leads are unverified. Review official terms and risk before joining.","نتایج جست‌وجو تأییدنشده‌اند؛ پیش از عضویت، شرایط رسمی و ریسک‌ها را بررسی کنید."],
    ["Choose a category and search to find possible opportunities.","برای یافتن فرصت‌های احتمالی، دسته‌ای انتخاب و جست‌وجو کنید."],
    ["DISCOVERY & DUE DILIGENCE","کشف و ارزیابی"],["+ Add opportunity","+ افزودن فرصت"],["Search platform or opportunity…","جست‌وجوی پلتفرم یا فرصت…"],
    ["All statuses","همه وضعیت‌ها"],["No opportunities yet. Add a platform you want to evaluate.","هنوز فرصتی ثبت نشده است. پلتفرمی را برای ارزیابی اضافه کنید."],
    ["ASSISTED EXECUTION","اجرای با تأیید کاربر"],["Tasks awaiting action","کارهای منتظر اقدام"],["No tasks yet. Create a task from an opportunity.","هنوز کاری ثبت نشده است. از یک فرصت، کار جدید ایجاد کنید."],
    ["TRANSPARENT LEDGER","دفتر شفاف پاداش‌ها"],["+ Record reward","+ ثبت پاداش"],["Reward tracking","پیگیری پاداش‌ها"],["No rewards recorded.","هنوز پاداشی ثبت نشده است."],
    ["Add opportunity","افزودن فرصت"],["Opportunity title","عنوان فرصت"],["Daily puzzle challenge","چالش روزانه پازل"],["Platform","پلتفرم"],
    ["Website URL","نشانی وب‌سایت"],["Category","دسته‌بندی"],["Game","بازی"],["Mobile app","اپلیکیشن موبایل"],["Skill / competition","مهارت / رقابت"],
    ["Survey / offer","نظرسنجی / پیشنهاد"],["Other","سایر"],["Advertised reward","پاداش اعلام‌شده"],
    ["Describe the advertised reward; do not assume it is guaranteed.","پاداش اعلام‌شده را شرح دهید؛ آن را قطعی فرض نکنید."],
    ["Eligibility / country restrictions","شرایط احراز / محدودیت کشور"],["Terms URL","نشانی شرایط و قوانین"],["Notes","یادداشت‌ها"],
    ["Save opportunity","ذخیره فرصت"],["Record reward","ثبت پاداش"],["Opportunity","فرصت"],["Not linked","بدون پیوند به فرصت"],
    ["Amount","مبلغ"],["Currency","واحد پول"],["Status","وضعیت"],["Reference / note","شناسه / یادداشت"],["Save reward","ذخیره پاداش"],
    ["pending","در انتظار"],["confirmed","تأییدشده"],["paid","پرداخت‌شده"],["rejected","ردشده"],
    ["discovered","کشف‌شده"],["reviewing","در حال بررسی"],["eligible","واجد شرایط"],["ineligible","فاقد شرایط"],["archived","بایگانی‌شده"],
    ["Review score","امتیاز بررسی"],["Open platform","بازکردن پلتفرم"],["Terms","قوانین"],["No reward details entered","جزئیات پاداش وارد نشده"],
    ["Create task","ایجاد کار"],["Review","بررسی"],["Describe the activity you plan to do. The assistant will not play or submit anything without your approval:","فعالیتی را که قصد انجامش را دارید شرح دهید. دستیار بدون تأیید شما بازی یا چیزی ارسال نمی‌کند:"],
    ["Task added to approval queue","کار به صف تأیید اضافه شد"],["Approve task","تأیید کار"],["Mark completed","علامت‌گذاری به‌عنوان تکمیل‌شده"],
    ["Approve this task? You remain responsible for following the platform rules.","این کار را تأیید می‌کنید؟ رعایت قوانین پلتفرم همچنان بر عهده شماست."],
    ["Task approved","کار تأیید شد"],["Task marked completed","کار تکمیل‌شده علامت‌گذاری شد"],["Unlinked reward","پاداش بدون پیوند"],
    ["Searching…","در حال جست‌وجو…"],["Searching public discovery sources…","در حال جست‌وجو در منابع عمومی…"],
    ["No matching leads returned. Try a broader query or another category.","نتیجه‌ای پیدا نشد. عبارت گسترده‌تر یا دسته دیگری را امتحان کنید."],
    ["Not verified","تأییدنشده"],["Human review required","نیازمند بررسی انسانی"],["possible leads found","فرصت احتمالی پیدا شد"],
    ["approved","تأییدشده"],["completed","تکمیل‌شده"],["cancelled","لغوشده"],
    ["No matching opportunities.","فرصتی با این مشخصات پیدا نشد."],
    ["Discovery signal: ","شاخص کشف: "],[" possible leads found"," فرصت احتمالی پیدا شد"],
    ["Unexpected server response","پاسخ غیرمنتظره از سرور"],["Request failed","درخواست ناموفق بود"],
    ["AutoEarn AI · MVP 0.1 · No earnings are guaranteed. Always follow each platform’s terms.","AutoEarn AI · نسخه اولیه ۰.۱ · هیچ درآمدی تضمین‌شده نیست. همواره قوانین هر پلتفرم را رعایت کنید."]
  ];
  const translate = value => {
    let out = value;
    for (const [en, fa] of replacements) out = out.split(en).join(fa);
    return out;
  };
  const translateNode = node => {
    if (node.nodeType === Node.TEXT_NODE && node.nodeValue.trim()) node.nodeValue = translate(node.nodeValue);
    else if (node.nodeType === Node.ELEMENT_NODE) {
      for (const attr of ["placeholder","aria-label","title"]) {
        if (node.hasAttribute(attr)) node.setAttribute(attr, translate(node.getAttribute(attr)));
      }
      node.childNodes.forEach(translateNode);
    }
  };
  const apply = () => document.body.childNodes.forEach(translateNode);
  apply();
  new MutationObserver(records => records.forEach(record => {
    record.addedNodes.forEach(translateNode);
    if (record.type === "characterData") translateNode(record.target);
  })).observe(document.body,{subtree:true,childList:true,characterData:true});
  document.documentElement.lang = "fa";
  document.documentElement.dir = "rtl";
})();