/* =========================
   WPO — i18n + mailto report + reports.json loader
   ========================= */

const TO_EMAIL = "whalebreaker2025@gmail.com";

// Supported languages
const SUPPORTED = ["en", "ar", "ur", "zh"];
const DIR = { en: "ltr", ar: "rtl", ur: "rtl", zh: "ltr" };
const LANG_NAMES = { en: "English", ar: "العربية", ur: "اردو", zh: "中文" };

// Translations (keep keys stable)
const I18N = {
  en: {
    tagline: "Market Integrity • Fraud Reporting • Investor Protection",
    nav_home: "Home",
    nav_categories: "Categories",
    nav_submit: "Submit Report",
    nav_reports: "Published Reports",
    nav_contact: "Contact",
    official_x: "Official X",
    contact_us: "Contact Us",

    hero_title: "Market Integrity Initiative",
    hero_desc:
      "Whale Protocol Official is an independent community initiative focused on exposing fraud, reporting suspicious activity, and restoring trust in digital asset markets through transparency and accountability.",
    chip_verified: "Verified Alerts",
    chip_evidence: "Evidence-Based",
    chip_community: "Community Reporting",

    k_official_x: "Official X",
    k_email: "Email",
    k_policy: "Policy",
    policy_value: "No accusations without evidence",

    cat_title: "Community Reporting Categories",
    cat1_h: "Report a Fake Project",
    cat1_p: "Misleading claims, false promises, lack of transparency.",
    cat2_h: "Report a Suspicious Wallet",
    cat2_p: "Manipulation patterns, abnormal movements, coordinated dumping.",
    cat3_h: "Report a Fraudulent Token",
    cat3_p: "Rug-pull signals, deceptive promotion, anonymous teams.",
    cat4_h: "Report a Malicious Address",
    cat4_p: "Addresses linked to scams, exploits, or investor targeting.",
    cat_note:
      "We do not publish accusations without evidence. Reports are reviewed and verified before any public alert is issued.",

    form_title: "Submit a Report",
    form_hint:
      "Your report will be prepared as an email draft to our official inbox. Provide clear evidence and explorer links when possible.",
    f_type: "Report Type",
    f_select: "Select…",
    opt_fake: "Fake Project",
    opt_wallet: "Suspicious Wallet",
    opt_token: "Fraudulent Token",
    opt_address: "Malicious Address",
    opt_other: "Other",
    f_chain: "Network / Chain",
    ph_chain: "e.g., Ethereum, BSC, Solana, GateChain",
    f_name: "Project / Token / Wallet Name (optional)",
    ph_name: "Name or ticker",
    f_addr: "Suspicious Address / Contract",
    ph_addr: "0x… / Solana / etc.",
    f_links: "Evidence Links (Explorer, TX, Screenshots)",
    ph_links: "Paste URLs (separate with commas)",
    f_contact: "Your Contact (optional)",
    ph_contact: "Email / X handle (optional)",
    f_details: "Report Details",
    ph_details: "Explain what happened, timeline, and why it is suspicious…",
    btn_send: "Prepare Email & Send",
    btn_copy: "Copy Report Text",
    tip: "Tip: TX links speed up verification.",
    ok_copy: "Copied. You can paste it anywhere.",
    warn_need: "Please choose a Report Type and add Details.",
    bad_need: "Please provide an Address or Evidence Links (at least one).",
    cooldown: "Please wait a bit before sending another report.",

    pub_title: "Published Reports",
    pub_hint: "These cards load from reports.json. Edit that file to publish real verified alerts.",
    pub_note:
      "Disclaimer: Whale Protocol Official does not provide financial advice or price predictions. We publish safety-focused reports to reduce risk and support responsible investing.",

    contact_title: "Official Communication",
    follow_x: "Follow verified alerts on X:",
    contact_line: "Contact us:",

    footer_tag: "Community Market Integrity Initiative",
    footer_contact: "Contact",
    footer_submit: "Submit Report",
    footer_reports: "Reports",

    // Email template labels
    email_subject_prefix: "[WPO REPORT]",
    email_hello: "Hello WPO Team,",
    email_new: "A new report has been submitted:",
    email_type: "Type",
    email_chain: "Network/Chain",
    email_name: "Name",
    email_addr: "Address/Contract",
    email_links: "Evidence Links",
    email_contact: "Reporter Contact",
    email_details: "Details",
    email_meta: "Meta",
  },

  ar: {
    tagline: "نزاهة السوق • بلاغات الاحتيال • حماية المستثمر",
    nav_home: "الرئيسية",
    nav_categories: "الفئات",
    nav_submit: "إرسال بلاغ",
    nav_reports: "التقارير",
    nav_contact: "تواصل",
    official_x: "X الرسمي",
    contact_us: "تواصل معنا",

    hero_title: "مبادرة نزاهة السوق",
    hero_desc:
      "Whale Protocol Official مبادرة مجتمعية مستقلة تهدف إلى كشف الاحتيال، رصد الأنشطة المشبوهة، وإعادة الثقة لسوق الأصول الرقمية عبر الشفافية والمساءلة.",
    chip_verified: "تنبيهات موثقة",
    chip_evidence: "مبني على الأدلة",
    chip_community: "بلاغات المجتمع",

    k_official_x: "حساب X الرسمي",
    k_email: "البريد",
    k_policy: "السياسة",
    policy_value: "لا اتهامات بدون أدلة",

    cat_title: "فئات البلاغات",
    cat1_h: "الإبلاغ عن مشروع وهمي",
    cat1_p: "ادعاءات مضللة، وعود كاذبة، غياب الشفافية.",
    cat2_h: "الإبلاغ عن محفظة مشبوهة",
    cat2_p: "أنماط تلاعب، تحركات غير طبيعية، تصريف منسق.",
    cat3_h: "الإبلاغ عن عملة احتيالية",
    cat3_p: "مؤشرات سحب سيولة، ترويج مخادع، فرق مجهولة.",
    cat4_h: "الإبلاغ عن عنوان مسمّم",
    cat4_p: "عناوين مرتبطة بالنصب أو الاستغلال أو استهداف المستثمرين.",
    cat_note: "لا ننشر اتهامات دون أدلة. تتم مراجعة البلاغات والتحقق منها قبل إصدار أي تنبيه علني.",

    form_title: "إرسال بلاغ",
    form_hint: "سيتم تجهيز البلاغ كمسودة بريد لإرساله إلى بريدنا الرسمي. يُفضل إرفاق أدلة وروابط المستكشف إن وجدت.",
    f_type: "نوع البلاغ",
    f_select: "اختر…",
    opt_fake: "مشروع وهمي",
    opt_wallet: "محفظة مشبوهة",
    opt_token: "عملة احتيالية",
    opt_address: "عنوان مسمّم",
    opt_other: "أخرى",
    f_chain: "الشبكة",
    ph_chain: "مثال: Ethereum, BSC, Solana, GateChain",
    f_name: "اسم المشروع/العملة/المحفظة (اختياري)",
    ph_name: "اسم أو رمز",
    f_addr: "العنوان/العقد المشبوه",
    ph_addr: "0x… / Solana / إلخ",
    f_links: "روابط الأدلة (مستكشف/معاملات/صور)",
    ph_links: "ضع الروابط (افصل بينها بفواصل)",
    f_contact: "وسيلة تواصل (اختياري)",
    ph_contact: "بريد / حساب X (اختياري)",
    f_details: "تفاصيل البلاغ",
    ph_details: "اشرح ما حدث، التسلسل الزمني، ولماذا تعتبره مشبوهًا…",
    btn_send: "تجهيز البريد وإرساله",
    btn_copy: "نسخ نص البلاغ",
    tip: "نصيحة: روابط المعاملات تسرّع التحقق.",
    ok_copy: "تم النسخ. يمكنك لصقه في أي مكان.",
    warn_need: "يرجى اختيار نوع البلاغ وإضافة التفاصيل.",
    bad_need: "يرجى إدخال العنوان أو روابط الأدلة (واحد على الأقل).",
    cooldown: "يرجى الانتظار قليلًا قبل إرسال بلاغ جديد.",

    pub_title: "التقارير المنشورة",
    pub_hint: "هذه البطاقات تُقرأ من reports.json. عدّل الملف لنشر التنبيهات الموثقة.",
    pub_note: "تنبيه: لا نقدم نصائح استثمارية أو توقعات سعرية. ننشر تقارير توعوية لحماية المستثمر وتقليل المخاطر.",

    contact_title: "التواصل الرسمي",
    follow_x: "تابع التنبيهات الموثقة على X:",
    contact_line: "راسلنا:",

    footer_tag: "مبادرة مجتمعية لنزاهة السوق",
    footer_contact: "تواصل",
    footer_submit: "إرسال بلاغ",
    footer_reports: "التقارير",

    email_subject_prefix: "[بلاغ WPO]",
    email_hello: "مرحبًا فريق WPO،",
    email_new: "تم إرسال بلاغ جديد:",
    email_type: "نوع البلاغ",
    email_chain: "الشبكة",
    email_name: "الاسم",
    email_addr: "العنوان/العقد",
    email_links: "روابط الأدلة",
    email_contact: "تواصل المُبلّغ",
    email_details: "التفاصيل",
    email_meta: "معلومات إضافية",
  },

  ur: {
    tagline: "مارکیٹ انٹیگریٹی • فراڈ رپورٹنگ • سرمایہ کار تحفظ",
    nav_home: "ہوم",
    nav_categories: "اقسام",
    nav_submit: "رپورٹ بھیجیں",
    nav_reports: "رپورٹس",
    nav_contact: "رابطہ",
    official_x: "آفیشل X",
    contact_us: "ہم سے رابطہ",

    hero_title: "مارکیٹ انٹیگریٹی اقدام",
    hero_desc:
      "Whale Protocol Official ایک آزاد کمیونٹی اقدام ہے جو فراڈ کو بے نقاب کرنے، مشتبہ سرگرمی رپورٹ کرنے، اور شفافیت و احتساب کے ذریعے ڈیجیٹل مارکیٹس میں اعتماد بحال کرنے پر مرکوز ہے۔",
    chip_verified: "تصدیق شدہ الرٹس",
    chip_evidence: "ثبوت پر مبنی",
    chip_community: "کمیونٹی رپورٹنگ",

    k_official_x: "آفیشل X",
    k_email: "ای میل",
    k_policy: "پالیسی",
    policy_value: "ثبوت کے بغیر الزام نہیں",

    cat_title: "کمیونٹی رپورٹنگ کی اقسام",
    cat1_h: "جعلی پروجیکٹ کی رپورٹ",
    cat1_p: "گمراہ کن دعوے، جھوٹے وعدے، شفافیت کی کمی۔",
    cat2_h: "مشتبہ والیٹ کی رپورٹ",
    cat2_p: "ہیرا پھیری کے پیٹرن، غیر معمولی حرکات، منظم ڈمپنگ۔",
    cat3_h: "جعلی/فراڈی ٹوکن کی رپورٹ",
    cat3_p: "رگ پل کے آثار، دھوکہ دہی پر مبنی پروموشن، گمنام ٹیمیں۔",
    cat4_h: "خطرناک ایڈریس کی رپورٹ",
    cat4_p: "اسکیمز/ایکسپلائٹس یا سرمایہ کاروں کو ہدف بنانے سے منسلک پتے۔",
    cat_note: "ہم ثبوت کے بغیر الزامات شائع نہیں کرتے۔ رپورٹ کی جانچ کے بعد ہی عوامی الرٹ جاری ہوتا ہے۔",

    form_title: "رپورٹ بھیجیں",
    form_hint: "آپ کی رپورٹ ہمارے آفیشل ان باکس کے لیے ای میل ڈرافٹ کے طور پر تیار ہوگی۔ جہاں ممکن ہو ایکسپلورر/TX لنکس دیں۔",
    f_type: "رپورٹ کی قسم",
    f_select: "منتخب کریں…",
    opt_fake: "جعلی پروجیکٹ",
    opt_wallet: "مشتبہ والیٹ",
    opt_token: "فراڈی ٹوکن",
    opt_address: "خطرناک ایڈریس",
    opt_other: "دیگر",
    f_chain: "نیٹ ورک / چین",
    ph_chain: "مثال: Ethereum, BSC, Solana, GateChain",
    f_name: "نام (اختیاری)",
    ph_name: "نام یا ٹکر",
    f_addr: "مشتبہ ایڈریس / کنٹریکٹ",
    ph_addr: "0x… / Solana / وغیرہ",
    f_links: "ثبوت کے لنکس (Explorer, TX, Screenshots)",
    ph_links: "URLs پیسٹ کریں (کاما سے الگ کریں)",
    f_contact: "آپ کا رابطہ (اختیاری)",
    ph_contact: "ای میل / X ہینڈل (اختیاری)",
    f_details: "تفصیلات",
    ph_details: "کیا ہوا، ٹائم لائن، اور کیوں مشتبہ ہے…",
    btn_send: "ای میل تیار کریں اور بھیجیں",
    btn_copy: "رپورٹ کا متن کاپی کریں",
    tip: "ٹپ: TX لنکس سے تصدیق تیز ہوتی ہے۔",
    ok_copy: "کاپی ہوگیا۔ کہیں بھی پیسٹ کرسکتے ہیں۔",
    warn_need: "براہ کرم رپورٹ کی قسم منتخب کریں اور تفصیلات لکھیں۔",
    bad_need: "براہ کرم ایڈریس یا ثبوت لنکس میں سے کم از کم ایک دیں۔",
    cooldown: "براہ کرم نئی رپورٹ بھیجنے سے پہلے تھوڑا انتظار کریں۔",

    pub_title: "شائع شدہ رپورٹس",
    pub_hint: "یہ کارڈز reports.json سے لوڈ ہوتے ہیں۔ حقیقی تصدیق شدہ الرٹس کے لیے فائل ایڈٹ کریں۔",
    pub_note: "ڈسکلیمر: ہم مالی مشورہ یا قیمت کی پیش گوئی نہیں دیتے۔ ہم خطرات کم کرنے کے لیے سیفٹی رپورٹس شائع کرتے ہیں۔",

    contact_title: "آفیشل رابطہ",
    follow_x: "X پر تصدیق شدہ الرٹس دیکھیں:",
    contact_line: "ہم سے رابطہ:",

    footer_tag: "کمیونٹی مارکیٹ انٹیگریٹی اقدام",
    footer_contact: "رابطہ",
    footer_submit: "رپورٹ",
    footer_reports: "رپورٹس",

    email_subject_prefix: "[WPO رپورٹ]",
    email_hello: "WPO ٹیم کو سلام،",
    email_new: "ایک نئی رپورٹ جمع ہوئی ہے:",
    email_type: "قسم",
    email_chain: "چین",
    email_name: "نام",
    email_addr: "ایڈریس/کنٹریکٹ",
    email_links: "ثبوت لنکس",
    email_contact: "رپورٹر رابطہ",
    email_details: "تفصیلات",
    email_meta: "میٹا",
  },

  zh: {
    tagline: "市场诚信 • 诈骗举报 • 投资者保护",
    nav_home: "主页",
    nav_categories: "类别",
    nav_submit: "提交举报",
    nav_reports: "已发布报告",
    nav_contact: "联系",
    official_x: "官方 X",
    contact_us: "联系我们",

    hero_title: "市场诚信倡议",
    hero_desc:
      "Whale Protocol Official 是一个独立的社区倡议，专注于揭露诈骗、举报可疑活动，并通过透明与问责恢复数字资产市场信任。",
    chip_verified: "已核验警报",
    chip_evidence: "基于证据",
    chip_community: "社区举报",

    k_official_x: "官方 X",
    k_email: "邮箱",
    k_policy: "政策",
    policy_value: "无证据不指控",

    cat_title: "社区举报类别",
    cat1_h: "举报虚假项目",
    cat1_p: "误导性宣传、虚假承诺、缺乏透明度。",
    cat2_h: "举报可疑钱包",
    cat2_p: "操纵模式、异常转账、协同砸盘。",
    cat3_h: "举报欺诈代币",
    cat3_p: "Rug Pull 信号、欺骗性推广、匿名团队。",
    cat4_h: "举报恶意地址",
    cat4_p: "与骗局、漏洞利用或针对投资者相关的地址。",
    cat_note: "我们不会在没有证据的情况下发布指控。所有举报将被审查与核验后再公开。",

    form_title: "提交举报",
    form_hint: "你的举报将作为邮件草稿准备发送至官方邮箱。请尽量提供证据与区块浏览器链接。",
    f_type: "举报类型",
    f_select: "请选择…",
    opt_fake: "虚假项目",
    opt_wallet: "可疑钱包",
    opt_token: "欺诈代币",
    opt_address: "恶意地址",
    opt_other: "其他",
    f_chain: "网络 / 链",
    ph_chain: "例如：Ethereum, BSC, Solana, GateChain",
    f_name: "名称（可选）",
    ph_name: "名称或代号",
    f_addr: "可疑地址 / 合约",
    ph_addr: "0x… / Solana / 等",
    f_links: "证据链接（浏览器、TX、截图）",
    ph_links: "粘贴链接（用逗号分隔）",
    f_contact: "你的联系方式（可选）",
    ph_contact: "邮箱 / X 账号（可选）",
    f_details: "举报详情",
    ph_details: "说明发生了什么、时间线，以及为何可疑…",
    btn_send: "生成邮件并发送",
    btn_copy: "复制举报文本",
    tip: "提示：TX 链接可加快核验。",
    ok_copy: "已复制，可粘贴到任意位置。",
    warn_need: "请选择举报类型并填写详情。",
    bad_need: "请至少提供“地址”或“证据链接”之一。",
    cooldown: "请稍等片刻再提交新的举报。",

    pub_title: "已发布报告",
    pub_hint: "这些卡片从 reports.json 加载。编辑该文件以发布核验后的警报。",
    pub_note: "免责声明：我们不提供投资建议或价格预测。我们发布安全报告以降低风险。",

    contact_title: "官方沟通",
    follow_x: "在 X 查看核验警报：",
    contact_line: "联系邮箱：",

    footer_tag: "社区市场诚信倡议",
    footer_contact: "联系",
    footer_submit: "提交举报",
    footer_reports: "报告",

    email_subject_prefix: "[WPO 举报]",
    email_hello: "WPO 团队您好，",
    email_new: "收到一条新的举报：",
    email_type: "类型",
    email_chain: "链",
    email_name: "名称",
    email_addr: "地址/合约",
    email_links: "证据链接",
    email_contact: "举报者联系方式",
    email_details: "详情",
    email_meta: "附加信息",
  }
};

function t(key, lang) {
  return (I18N[lang] && I18N[lang][key]) || I18N.en[key] || "";
}

function normalizeLang(raw) {
  if (!raw) return "en";
  const low = raw.toLowerCase();
  const base = low.split("-")[0];
  return SUPPORTED.includes(base) ? base : "en";
}

function setHtmlLang(lang) {
  document.documentElement.setAttribute("lang", lang);
  document.documentElement.setAttribute("dir", DIR[lang] || "ltr");
  document.documentElement.setAttribute("data-lang", lang);
}

function applyI18n(lang) {
  setHtmlLang(lang);

  const langBtn = document.getElementById("langBtn");
  if (langBtn) langBtn.textContent = LANG_NAMES[lang] || "Language";

  document.querySelectorAll("[data-i18n]").forEach(el => {
    const key = el.getAttribute("data-i18n");
    if (!key) return;
    el.textContent = t(key, lang);
  });

  document.querySelectorAll("[data-i18n-placeholder]").forEach(el => {
    const key = el.getAttribute("data-i18n-placeholder");
    if (!key) return;
    el.setAttribute("placeholder", t(key, lang));
  });

  localStorage.setItem("lang", lang);
}

function initLang() {
  const saved = localStorage.getItem("lang");
  if (saved && SUPPORTED.includes(saved)) return saved;
  return normalizeLang(navigator.language || navigator.userLanguage);
}

function initLangMenu() {
  const btn = document.getElementById("langBtn");
  const menu = document.getElementById("langMenu");
  if (!btn || !menu) return;

  btn.addEventListener("click", () => {
    const open = menu.classList.toggle("show");
    btn.setAttribute("aria-expanded", open ? "true" : "false");
  });

  document.addEventListener("click", (e) => {
    if (!e.target.closest(".lang-switch")) {
      menu.classList.remove("show");
      btn.setAttribute("aria-expanded", "false");
    }
  });

  menu.querySelectorAll("button[data-lang]").forEach(b => {
    b.addEventListener("click", () => {
      const lang = b.dataset.lang;
      applyI18n(lang);
      menu.classList.remove("show");
      btn.setAttribute("aria-expanded", "false");
    });
  });
}

function showBox(id) {
  ["okBox", "warnBox", "badBox", "cooldownBox"].forEach(x => {
    const el = document.getElementById(x);
    if (el) el.style.display = "none";
  });
  const el = document.getElementById(id);
  if (el) el.style.display = "block";
}

function buildReportText(lang, data) {
  const lines = [
    t("email_hello", lang),
    "",
    t("email_new", lang),
    "",
    `${t("email_type", lang)}: ${data.reportType || "-"}`,
    `${t("email_chain", lang)}: ${data.network || "-"}`,
    `${t("email_name", lang)}: ${data.entity || "-"}`,
    `${t("email_addr", lang)}: ${data.address || "-"}`,
    `${t("email_links", lang)}: ${data.links || "-"}`,
    `${t("email_contact", lang)}: ${data.contactField || "-"}`,
    "",
    `${t("email_details", lang)}:`,
    `${data.details || "-"}`,
    "",
    `${t("email_meta", lang)}:`,
    `URL: ${location.href}`,
    `Time: ${new Date().toISOString()}`
  ];
  return lines.join("\n");
}

function mailtoSend(subject, body) {
  const enc = encodeURIComponent;
  const url = `mailto:${TO_EMAIL}?subject=${enc(subject)}&body=${enc(body)}`;
  // أحياناً أفضل من href في بعض المتصفحات
  window.open(url, "_self");
}

// Simple cooldown (prevents spam clicks)
const COOLDOWN_MS = 25000;
function canSendNow() {
  const last = Number(localStorage.getItem("lastSendTs") || "0");
  return (Date.now() - last) > COOLDOWN_MS;
}
function markSentNow() {
  localStorage.setItem("lastSendTs", String(Date.now()));
}

function initForm() {
  const form = document.getElementById("reportForm");
  if (!form) return;

  const copyBtn = document.getElementById("copyBtn");
  const gmailBtn = document.getElementById("gmailBtn");
  const outlookBtn = document.getElementById("outlookBtn");

  const companyHp = document.getElementById("company");

  function getLang() {
    return document.documentElement.getAttribute("data-lang") || "en";
  }

  function getData() {
    return Object.fromEntries(new FormData(form).entries());
  }

  function validate(data) {
    // honeypot
    if (companyHp && companyHp.value.trim() !== "") return { ok: false, box: null };

    // required: type + details
    if (!data.reportType || !data.details || String(data.details).trim().length < 3) {
      return { ok: false, box: "warnBox" };
    }

    // required: address OR links
    const hasAddr = (data.address || "").trim().length > 3;
    const hasLinks = (data.links || "").trim().length > 3;
    if (!hasAddr && !hasLinks) {
      return { ok: false, box: "badBox" };
    }

    // cooldown
    if (!canSendNow()) {
      return { ok: false, box: "cooldownBox" };
    }

    return { ok: true, box: null };
  }

  async function copyText(text) {
    try {
      await navigator.clipboard.writeText(text);
      showBox("okBox");
    } catch {
      const ta = document.createElement("textarea");
      ta.value = text;
      document.body.appendChild(ta);
      ta.select();
      document.execCommand("copy");
      ta.remove();
      showBox("okBox");
    }
  }

  copyBtn?.addEventListener("click", () => {
    const lang = getLang();
    const data = getData();
    const text = buildReportText(lang, data);
    copyText(text);
  });

  // Gmail Web
  gmailBtn?.addEventListener("click", () => {
    const lang = getLang();
    const data = getData();

    const v = validate(data);
    if (!v.ok) { if (v.box) showBox(v.box); return; }

    const subject = `${t("email_subject_prefix", lang)} ${data.reportType}`;
    const body = buildReportText(lang, data);

    markSentNow();

    const url =
      "https://mail.google.com/mail/?view=cm&fs=1" +
      "&to=" + encodeURIComponent(TO_EMAIL) +
      "&su=" + encodeURIComponent(subject) +
      "&body=" + encodeURIComponent(body);

    window.open(url, "_blank", "noopener");
  });

  // Outlook Web
  outlookBtn?.addEventListener("click", () => {
    const lang = getLang();
    const data = getData();

    const v = validate(data);
    if (!v.ok) { if (v.box) showBox(v.box); return; }

    const subject = `${t("email_subject_prefix", lang)} ${data.reportType}`;
    const body = buildReportText(lang, data);

    markSentNow();

    const url =
      "https://outlook.office.com/mail/deeplink/compose" +
      "?to=" + encodeURIComponent(TO_EMAIL) +
      "&subject=" + encodeURIComponent(subject) +
      "&body=" + encodeURIComponent(body);

    window.open(url, "_blank", "noopener");
  });

  // Default submit => mailto
  form.addEventListener("submit", (e) => {
    e.preventDefault();

    const lang = getLang();
    const data = getData();

    const v = validate(data);
    if (!v.ok) { if (v.box) showBox(v.box); return; }

    const subject = `${t("email_subject_prefix", lang)} ${data.reportType}`;
    const body = buildReportText(lang, data);

    markSentNow();
    mailtoSend(subject, body);
  });
}

// Load reports.json and render cards
async function loadReports() {
  const grid = document.getElementById("reportsGrid");
  if (!grid) return;

  try {
    const res = await fetch("reports.json", { cache: "no-store" });
    if (!res.ok) throw new Error("no reports.json");
    const items = await res.json();

    if (!Array.isArray(items) || items.length === 0) return;

    grid.innerHTML = "";
    items.forEach(r => {
      const card = document.createElement("div");
      card.className = "card report";

      const top = document.createElement("div");
      top.className = "report-top";

      const badge = document.createElement("span");
      badge.className = "badge " + (r.severity || "info");
      badge.textContent = (r.severity || "info").toUpperCase();

      const meta = document.createElement("div");
      meta.className = "meta";
      meta.textContent = `${r.date || ""} • ${r.network || ""}`.trim();

      top.appendChild(badge);
      top.appendChild(meta);

      const h4 = document.createElement("h4");
      h4.textContent = r.title || "Report";

      const p = document.createElement("p");
      p.textContent = r.summary || "";

      card.appendChild(top);
      card.appendChild(h4);
      card.appendChild(p);

      if (r.link) {
        const a = document.createElement("a");
        a.href = r.link;
        a.target = "_blank";
        a.rel = "noopener";
        a.textContent = r.linkText || "View evidence";
        card.appendChild(a);
      }

      grid.appendChild(card);
    });
  } catch {
    // silent
  }
}

// Boot
(function main() {
  const lang = initLang();
  applyI18n(lang);
  initLangMenu();
  initForm();
  loadReports();
})();
