(function(){
  const htmlEl = document.documentElement;
  const langToggle = document.getElementById("langToggle");
  const reportTypePlaceholder = document.getElementById("reportTypePlaceholder");

  function setLang(lang){
    htmlEl.setAttribute("data-lang", lang);
    if(lang === "ar"){
      htmlEl.lang = "ar";
      htmlEl.dir = "rtl";
      langToggle.textContent = "EN";
      if(reportTypePlaceholder) reportTypePlaceholder.textContent = "اختر…";
    } else {
      htmlEl.lang = "en";
      htmlEl.dir = "ltr";
      langToggle.textContent = "AR";
      if(reportTypePlaceholder) reportTypePlaceholder.textContent = "Select…";
    }
    localStorage.setItem("wpo_lang", lang);
    // re-render reports to match the chosen language
    renderReports(window.__WPO_REPORTS__ || []);
  }

  // Default language: saved -> browser -> EN
  const saved = localStorage.getItem("wpo_lang");
  if(saved){
    setLang(saved);
  } else {
    const browserIsAr = (navigator.language || "").toLowerCase().startsWith("ar");
    setLang(browserIsAr ? "ar" : "en");
  }

  if(langToggle){
    langToggle.addEventListener("click", () => {
      const current = htmlEl.getAttribute("data-lang") || "en";
      setLang(current === "en" ? "ar" : "en");
    });
  }

  function buildReportText(){
    const reportType = (document.getElementById("reportType")?.value || "").trim();
    const network = (document.getElementById("network")?.value || "").trim();
    const entity = (document.getElementById("entity")?.value || "").trim();
    const address = (document.getElementById("address")?.value || "").trim();
    const links = (document.getElementById("links")?.value || "").trim();
    const contact = (document.getElementById("contactField")?.value || "").trim();
    const details = (document.getElementById("details")?.value || "").trim();
    const lang = htmlEl.getAttribute("data-lang") || "en";

    if(lang === "ar"){
      return [
        "Whale Protocol Official – بلاغ جديد",
        "--------------------------------",
        "نوع البلاغ: " + (reportType || "غير محدد"),
        "الشبكة: " + (network || "غير محدد"),
        "الاسم/الرمز: " + (entity || "غير محدد"),
        "العنوان/العقد: " + (address || "غير محدد"),
        "روابط الأدلة: " + (links || "غير متوفر"),
        "وسيلة تواصل: " + (contact || "غير متوفر"),
        "",
        "تفاصيل البلاغ:",
        details || "(لا توجد تفاصيل)"
      ].join("\n");
    }

    return [
      "Whale Protocol Official – New Report",
      "-----------------------------------",
      "Report Type: " + (reportType || "Not specified"),
      "Network/Chain: " + (network || "Not specified"),
      "Project/Token/Wallet: " + (entity || "Not specified"),
      "Suspicious Address/Contract: " + (address || "Not specified"),
      "Evidence Links: " + (links || "Not provided"),
      "Reporter Contact: " + (contact || "Not provided"),
      "",
      "Report Details:",
      details || "(No details provided)"
    ].join("\n");
  }

  // Form handlers
  const form = document.getElementById("reportForm");
  const copyBtn = document.getElementById("copyBtn");

  const okBox = document.getElementById("okBox");
  const okBoxAr = document.getElementById("okBoxAr");
  const warnBox = document.getElementById("warnBox");
  const warnBoxAr = document.getElementById("warnBoxAr");
  const badBox = document.getElementById("badBox");
  const badBoxAr = document.getElementById("badBoxAr");
  const cooldownBox = document.getElementById("cooldownBox");
  const cooldownBoxAr = document.getElementById("cooldownBoxAr");

  function hideStatus(){
    [okBox, okBoxAr, warnBox, warnBoxAr, badBox, badBoxAr, cooldownBox, cooldownBoxAr].forEach(el => {
      if(el) el.style.display = "none";
    });
  }

  function showBox(enEl, arEl){
    const lang = htmlEl.getAttribute("data-lang") || "en";
    (lang === "ar" ? arEl : enEl).style.display = "block";
  }

  const COOLDOWN_MS = 30000; // 30 seconds
  const cooldownKey = "wpo_last_report_ts";

  if(copyBtn){
    copyBtn.addEventListener("click", async () => {
      hideStatus();
      const text = buildReportText();
      try{
        await navigator.clipboard.writeText(text);
        showBox(okBox, okBoxAr);
        setTimeout(hideStatus, 2200);
      }catch(e){
        alert("Copy failed. Please copy manually.");
      }
    });
  }

  if(form){
    form.addEventListener("submit", (e) => {
      e.preventDefault();
      hideStatus();

      // Honeypot: if filled -> bot
      const hp = (document.getElementById("company")?.value || "").trim();
      if(hp) return;

      const now = Date.now();
      const last = Number(localStorage.getItem(cooldownKey) || "0");
      if(now - last < COOLDOWN_MS){
        showBox(cooldownBox, cooldownBoxAr);
        return;
      }

      const reportType = (document.getElementById("reportType")?.value || "").trim();
      const details = (document.getElementById("details")?.value || "").trim();
      const address = (document.getElementById("address")?.value || "").trim();
      const links = (document.getElementById("links")?.value || "").trim();

      if(!reportType || !details){
        showBox(warnBox, warnBoxAr);
        return;
      }

      if(!address && !links){
        showBox(badBox, badBoxAr);
        return;
      }

      localStorage.setItem(cooldownKey, String(now));

      const lang = htmlEl.getAttribute("data-lang") || "en";
      const body = encodeURIComponent(buildReportText());
      const subject = encodeURIComponent(lang === "ar"
        ? "Whale Protocol Official – بلاغ جديد"
        : "Whale Protocol Official – New Report"
      );

      window.location.href = `mailto:whalebreaker2025@gmail.com?subject=${subject}&body=${body}`;
    });
  }

  // Reports loader
  async function loadReports(){
    try{
      const res = await fetch("reports.json", { cache: "no-store" });
      if(!res.ok) throw new Error("Failed to load reports.json");
      const data = await res.json();
      const reports = Array.isArray(data?.reports) ? data.reports : [];
      window.__WPO_REPORTS__ = reports;
      renderReports(reports);
    }catch(err){
      window.__WPO_REPORTS__ = [];
      renderReports([]);
    }
  }

  function esc(s){
    return String(s || "").replace(/[&<>\"']/g, (c) => ({
      "&":"&amp;",
      "<":"&lt;",
      ">":"&gt;",
      '"':"&quot;",
      "'":"&#39;"
    }[c]));
  }

  function badgeClass(risk){
    const v = String(risk || "").toLowerCase();
    if(v === "high") return "high";
    if(v === "medium") return "medium";
    return "info";
  }

  function badgeLabel(risk, lang){
    const v = String(risk || "info").toLowerCase();
    const map = {
      en: { high: "High Risk", medium: "Medium Risk", info: "Info" },
      ar: { high: "خطر مرتفع", medium: "خطر متوسط", info: "معلومات" }
    };
    return (map[lang] && map[lang][v]) || (lang === "ar" ? "معلومات" : "Info");
  }

  function renderReports(reports){
    const grid = document.getElementById("reportsGrid");
    if(!grid) return;

    const lang = htmlEl.getAttribute("data-lang") || "en";

    if(!reports.length){
      grid.innerHTML = `
        <div class="card report">
          <div class="report-top">
            <h4>${lang === "ar" ? "لا توجد تقارير بعد" : "No reports yet"}</h4>
            <span class="badge info">${lang === "ar" ? "قريبًا" : "Soon"}</span>
          </div>
          <div class="meta">${lang === "ar" ? "حرّر ملف reports.json لنشر تقاريرك الموثقة." : "Edit reports.json to publish verified alerts."}</div>
          <div class="meta"><a href="https://x.com/Protocol_WPO" target="_blank" rel="noopener">View on X</a></div>
        </div>
      `;
      return;
    }

    const cards = reports.map((r) => {
      const title = lang === "ar" ? (r.title_ar || r.title_en) : (r.title_en || r.title_ar);
      const status = lang === "ar" ? (r.status_ar || r.status_en) : (r.status_en || r.status_ar);
      const evidence = lang === "ar" ? (r.evidence_ar || r.evidence_en) : (r.evidence_en || r.evidence_ar);
      const link = r.link || "https://x.com/Protocol_WPO";
      const risk = r.risk || "info";
      const date = r.date ? `• ${esc(r.date)}` : "";

      return `
        <div class="card report">
          <div class="report-top">
            <h4>${esc(title)}</h4>
            <span class="badge ${badgeClass(risk)}">${esc(badgeLabel(risk, lang))}</span>
          </div>
          <div class="meta">${esc(status || "")} ${date}</div>
          <div class="meta">${esc(evidence || "")}</div>
          <div class="meta"><a href="${esc(link)}" target="_blank" rel="noopener">${lang === "ar" ? "عرض" : "View"}</a></div>
        </div>
      `;
    }).join("\n");

    grid.innerHTML = cards;
  }

  loadReports();
})();
