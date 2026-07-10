// Extra AgroVet features: dark mode, history, weather/spraying, crop calendar,
// daily tip, disease library, text-to-speech, downloadable report.
(function () {
  const T = () => window.AgrovetI18n;
  const $ = (id) => document.getElementById(id);
  const API = (window.AGROVET_CONFIG && window.AGROVET_CONFIG.API_BASE) || "";

  function bind(id, fn) {
    const el = $(id);
    if (el) el.addEventListener("click", fn);
  }

  /* ---------------- Dark mode ---------------- */
  const THEME_KEY = "agrovet_theme";
  function applyTheme(theme) {
    document.documentElement.setAttribute("data-theme", theme);
    const b = $("darkToggle");
    if (b) b.textContent = theme === "dark" ? "\u2600" : "\u263D";
  }
  function initDark() {
    applyTheme(localStorage.getItem(THEME_KEY) || "light");
    bind("darkToggle", () => {
      const next = document.documentElement.getAttribute("data-theme") === "dark" ? "light" : "dark";
      localStorage.setItem(THEME_KEY, next);
      applyTheme(next);
    });
  }

  /* ---------------- Diagnosis history ---------------- */
  const HKEY = "agrovet_history";
  const getHistory = () => JSON.parse(localStorage.getItem(HKEY) || "[]");
  function saveHistory(entry) {
    const h = getHistory();
    h.unshift(entry);
    localStorage.setItem(HKEY, JSON.stringify(h.slice(0, 8)));
    renderHistory();
  }
  function renderHistory() {
    const box = $("historyList");
    if (!box) return;
    const h = getHistory();
    if (!h.length) { box.innerHTML = `<p class="muted small">${T().t("history_empty")}</p>`; return; }
    box.innerHTML = h.map((e) => `
      <div class="hist-item">
        <img src="${e.thumb || ""}" alt="" />
        <div>
          <div class="hi-title">${e.plant} - ${e.condition}</div>
          <div class="muted small">${(e.confidence * 100).toFixed(0)}% - ${new Date(e.time).toLocaleString()}</div>
        </div>
      </div>`).join("");
  }

  /* ---------------- Weather + spraying advisory ---------------- */
  const WMAP = { en: {}, bn: {} };
  function sprayAdvice(temp, wind, rainProb, precip) {
    const en = [], bn = [];
    let ok = true;
    if (precip > 0 || rainProb >= 60) { ok = false; en.push("Rain likely - spraying may wash off."); bn.push("\u09AC\u09C3\u09B7\u09CD\u099F\u09BF\u09B0 \u09B8\u09AE\u09CD\u09AD\u09BE\u09AC\u09A8\u09BE - \u09B8\u09CD\u09AA\u09CD\u09B0\u09C7 \u09A7\u09C1\u09AF\u09BC\u09C7 \u09AF\u09C7\u09A4\u09C7 \u09AA\u09BE\u09B0\u09C7\u0964"); }
    if (wind >= 15) { ok = false; en.push("Windy - risk of spray drift."); bn.push("\u09AC\u09BE\u09A4\u09BE\u09B8 \u09AC\u09C7\u09B6\u09BF - \u09B8\u09CD\u09AA\u09CD\u09B0\u09C7 \u09B8\u09B0\u09C7 \u09AF\u09C7\u09A4\u09C7 \u09AA\u09BE\u09B0\u09C7\u0964"); }
    if (temp >= 34) { en.push("Very hot - spray early morning/evening."); bn.push("\u0996\u09C1\u09AC \u0997\u09B0\u09AE - \u09B8\u0995\u09BE\u09B2\u09C7/\u09B8\u09A8\u09CD\u09A7\u09CD\u09AF\u09BE\u09AF\u09BC \u09B8\u09CD\u09AA\u09CD\u09B0\u09C7 \u0995\u09B0\u09C1\u09A8\u0964"); }
    if (ok && !en.length) { en.push("Good conditions for spraying."); bn.push("\u09B8\u09CD\u09AA\u09CD\u09B0\u09C7\u09B0 \u099C\u09A8\u09CD\u09AF \u0989\u09AA\u09AF\u09C1\u0995\u09CD\u09A4 \u0986\u09AC\u09B9\u09BE\u0993\u09AF\u09BC\u09BE\u0964"); }
    return { ok, msg: (T().lang === "bn" ? bn : en).join(" ") };
  }
  function loadWeather() {
    const box = $("weatherBody");
    box.innerHTML = `<p class="muted small">${T().t("weather_loading")}</p>`;
    if (!navigator.geolocation) { box.innerHTML = `<p class="muted small">${T().t("weather_geo_unsupported")}</p>`; return; }
    navigator.geolocation.getCurrentPosition(async (pos) => {
      const { latitude: la, longitude: lo } = pos.coords;
      try {
        const u = `https://api.open-meteo.com/v1/forecast?latitude=${la}&longitude=${lo}&current=temperature_2m,relative_humidity_2m,precipitation,wind_speed_10m&daily=precipitation_probability_max&timezone=auto`;
        const d = await (await fetch(u)).json();
        const c = d.current, rp = (d.daily.precipitation_probability_max || [0])[0];
        const adv = sprayAdvice(c.temperature_2m, c.wind_speed_10m, rp, c.precipitation);
        box.innerHTML = `
          <div class="wx-grid">
            <div><b>${c.temperature_2m}\u00B0C</b><span>${T().t("wx_temp")}</span></div>
            <div><b>${c.relative_humidity_2m}%</b><span>${T().t("wx_humidity")}</span></div>
            <div><b>${c.wind_speed_10m}</b><span>${T().t("wx_wind")}</span></div>
            <div><b>${rp}%</b><span>${T().t("wx_rain")}</span></div>
          </div>
          <div class="spray ${adv.ok ? "ok" : "no"}">${adv.ok ? "\u2705" : "\u26A0\uFE0F"} ${adv.msg}</div>`;
      } catch { box.innerHTML = `<p class="muted small">${T().t("weather_unavailable")}</p>`; }
    }, () => {
      box.innerHTML = `<button id="wxEnable" class="btn btn-ghost btn-sm">${T().t("weather_enable")}</button>`;
      box.querySelector("#wxEnable").addEventListener("click", loadWeather);
    });
  }

  /* ---------------- Crop season calendar (Bangladesh) ---------------- */
  const SEASONS = [
    { months: [10, 11, 0, 1], en: "Rabi (winter)", bn: "\u09B0\u09AC\u09BF (\u09B6\u09C0\u09A4)", cropsEn: "Wheat, potato, mustard, lentil, boro paddy", cropsBn: "\u0997\u09AE, \u0986\u09B2\u09C1, \u09B8\u09B0\u09BF\u09B7\u09BE, \u09AE\u09B8\u09C1\u09B0, \u09AC\u09CB\u09B0\u09CB \u09A7\u09BE\u09A8" },
    { months: [2, 3, 4, 5], en: "Kharif-1 (pre-monsoon)", bn: "\u0996\u09B0\u09BF\u09AB-\u09E7 (\u09AA\u09CD\u09B0\u09BE\u0995-\u09AC\u09B0\u09CD\u09B7\u09BE)", cropsEn: "Aus paddy, jute, summer vegetables", cropsBn: "\u0986\u0989\u09B6 \u09A7\u09BE\u09A8, \u09AA\u09BE\u099F, \u0997\u09CD\u09B0\u09C0\u09B7\u09CD\u09AE\u0995\u09BE\u09B2\u09C0\u09A8 \u09B8\u09AC\u099C\u09BF" },
    { months: [6, 7, 8, 9], en: "Kharif-2 (monsoon)", bn: "\u0996\u09B0\u09BF\u09AB-\u09E8 (\u09AC\u09B0\u09CD\u09B7\u09BE)", cropsEn: "Aman paddy, vegetables", cropsBn: "\u0986\u09AE\u09A8 \u09A7\u09BE\u09A8, \u09B8\u09AC\u099C\u09BF" },
  ];
  function renderCalendar() {
    const m = new Date().getMonth();
    const s = SEASONS.find((x) => x.months.includes(m)) || SEASONS[0];
    const bn = T().lang === "bn";
    $("calendarBody").innerHTML = `
      <div class="cal-season">${bn ? s.bn : s.en}</div>
      <div class="muted small">${bn ? s.cropsBn : s.cropsEn}</div>`;
  }

  /* ---------------- Daily tip ---------------- */
  const TIPS = [
    { en: "Rotate crops each season to break disease cycles.", bn: "\u09B0\u09CB\u0997\u09C7\u09B0 \u099A\u0995\u09CD\u09B0 \u09AD\u09BE\u0999\u09A4\u09C7 \u09AA\u09CD\u09B0\u09A4\u09BF \u09AE\u09CC\u09B8\u09C1\u09AE\u09C7 \u09AB\u09B8\u09B2 \u09AC\u09A6\u09B2\u09BE\u09A8\u0964" },
    { en: "Remove and destroy infected leaves to slow spread.", bn: "\u09B0\u09CB\u0997\u09BE\u0995\u09CD\u09B0\u09BE\u09A8\u09CD\u09A4 \u09AA\u09BE\u09A4\u09BE \u09B8\u09B0\u09BF\u09AF\u09BC\u09C7 \u09A7\u09CD\u09AC\u0982\u09B8 \u0995\u09B0\u09C1\u09A8\u0964" },
    { en: "Water at the base, not the leaves, to reduce fungus.", bn: "\u09AB\u09BE\u0982\u0997\u09BE\u09B8 \u0995\u09AE\u09BE\u09A4\u09C7 \u09AA\u09BE\u09A4\u09BE\u09AF\u09BC \u09A8\u09AF\u09BC, \u0997\u09CB\u09A1\u09BC\u09BE\u09AF\u09BC \u09AA\u09BE\u09A8\u09BF \u09A6\u09BF\u09A8\u0964" },
    { en: "Scout your field weekly to catch problems early.", bn: "\u09B8\u09AE\u09B8\u09CD\u09AF\u09BE \u0986\u0997\u09C7 \u09A7\u09B0\u09A4\u09C7 \u09B8\u09BE\u09AA\u09CD\u09A4\u09BE\u09B9\u09BF\u0995 \u09AE\u09BE\u09A0 \u09AA\u09B0\u09BF\u09A6\u09B0\u09CD\u09B6\u09A8 \u0995\u09B0\u09C1\u09A8\u0964" },
    { en: "Use certified disease-free seeds and seedlings.", bn: "\u09B8\u09BE\u09B0\u09CD\u099F\u09BF\u09AB\u09BE\u0987\u09A1 \u09B0\u09CB\u0997\u09AE\u09C1\u0995\u09CD\u09A4 \u09AC\u09C0\u099C \u0993 \u099A\u09BE\u09B0\u09BE \u09AC\u09CD\u09AF\u09AC\u09B9\u09BE\u09B0 \u0995\u09B0\u09C1\u09A8\u0964" },
    { en: "Avoid working in the field when plants are wet.", bn: "\u0997\u09BE\u099B \u09AD\u09C7\u099C\u09BE \u09A5\u09BE\u0995\u09B2\u09C7 \u09AE\u09BE\u09A0\u09C7 \u0995\u09BE\u099C \u098F\u09A1\u09BC\u09BF\u09AF\u09BC\u09C7 \u099A\u09B2\u09C1\u09A8\u0964" },
    { en: "Balanced fertiliser keeps plants strong against disease.", bn: "\u09B8\u09C1\u09B7\u09AE \u09B8\u09BE\u09B0 \u0997\u09BE\u099B\u0995\u09C7 \u09B0\u09CB\u0997 \u09AA\u09CD\u09B0\u09A4\u09BF\u09B0\u09CB\u09A7\u09C0 \u09B0\u09BE\u0996\u09C7\u0964" },
  ];
  function renderTip() {
    const day = Math.floor(Date.now() / 86400000) % TIPS.length;
    const tip = TIPS[day];
    $("tipBody").textContent = T().lang === "bn" ? tip.bn : tip.en;
  }

  /* ---------------- Disease library ---------------- */
  let DISEASES = {};
  async function loadLibrary() {
    const lang = T() ? T().lang : "bn";
    try { DISEASES = (await (await fetch(`${API}/api/diseases?lang=${lang}`)).json()).diseases || {}; }
    catch { DISEASES = {}; }
    renderLibrary($("libSearch") ? $("libSearch").value : "");
  }
  function renderLibrary(q) {
    const box = $("libList");
    q = (q || "").toLowerCase();
    const items = Object.values(DISEASES).filter((d) =>
      d.title.toLowerCase().includes(q) || (d.summary || "").toLowerCase().includes(q));
    const sev = (d) => d.severity_label || (T().t("sev_" + (d.severity || "none")) !== "sev_" + (d.severity || "none") ? T().t("sev_" + (d.severity || "none")) : d.severity);
    box.innerHTML = items.map((d) => `
      <details class="lib-item">
        <summary><span class="sev ${d.severity}">${sev(d)}</span> ${d.title}</summary>
        <p class="muted small">${d.summary}</p>
        <div class="small"><b>${T().t("treatment")}:</b> ${(d.treatment || []).join("; ")}</div>
      </details>`).join("") || `<p class="muted small">${T().t("library_empty")}</p>`;
  }

  /* ---------------- Text-to-speech ---------------- */
  let speaking = false;
  function speakAdvice() {
    const r = window.lastResult;
    const b = r && r.stage2_disease && r.stage2_disease.best_answer;
    if (!b || !window.speechSynthesis) return;
    if (speaking) { window.speechSynthesis.cancel(); speaking = false; setListenLabel(); return; }
    const a = b.advice || {};
    const text = `${b.plant}, ${b.condition}. ${a.summary || ""}. ${T().t("treatment")}: ${(a.treatment || []).join(". ")}`;
    const u = new SpeechSynthesisUtterance(text);
    u.lang = T().lang === "bn" ? "bn-BD" : "en-US";
    u.onend = () => { speaking = false; setListenLabel(); };
    speaking = true; setListenLabel();
    window.speechSynthesis.speak(u);
  }
  function setListenLabel() {
    const b = $("listenBtn");
    if (b && T()) b.textContent = (speaking ? "\u23F9 " : "\u{1F50A} ") + T().t(speaking ? "stop" : "listen");
  }

  /* ---------------- Download / share report ---------------- */
  function buildReport() {
    const r = window.lastResult;
    if (!r) return "";
    const g = r.stage1_leaf_gate || {};
    let s = "AgroVet - Diagnosis report\n" + new Date().toLocaleString() + "\n\n";
    s += `Leaf check: ${g.is_leaf ? "Leaf" : "Not a leaf"} (${((g.leaf_probability || 0) * 100).toFixed(1)}%)\n\n`;
    const d = r.stage2_disease;
    if (d) {
      const b = d.best_answer;
      s += `Best answer: ${b.plant} - ${b.condition} (${(b.confidence * 100).toFixed(1)}%)\n`;
      s += `${b.agreement}\n\n`;
      s += "Per-model:\n" + d.models.map((m) => ` - ${m.model}: ${m.plant} ${m.condition} (${(m.confidence * 100).toFixed(1)}%)`).join("\n") + "\n\n";
      if (b.advice) {
        s += `Treatment: ${(b.advice.treatment || []).join("; ")}\n`;
        s += `Prevention: ${(b.advice.prevention || []).join("; ")}\n`;
      }
    }
    return s;
  }
  function downloadReport() {
    const text = buildReport();
    if (!text) return;
    const blob = new Blob([text], { type: "text/plain" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = "agrovet-diagnosis.txt";
    a.click();
  }
  async function shareReport() {
    const text = buildReport();
    if (!text) return;
    if (navigator.share) { try { await navigator.share({ title: T().t("share_title"), text }); } catch {} }
    else { navigator.clipboard.writeText(text); alert(T().t("share_copied")); }
  }

  /* ---------------- Public hook called after a prediction ---------------- */
  function onResult(data, thumb) {
    window.lastResult = data;
    const d = data.stage2_disease;
    if (d && d.best_answer) {
      const b = d.best_answer;
      saveHistory({ plant: b.plant, condition: b.condition, confidence: b.confidence, time: Date.now(), thumb });
      $("resultActions").classList.remove("hidden");
      setListenLabel();
    }
  }

  /* ---------------- init ---------------- */
  function init() {
    try {
      initDark();
      renderHistory();
      renderCalendar();
      renderTip();
      loadLibrary();
      const libSearch = $("libSearch");
      if (libSearch) libSearch.addEventListener("input", (e) => renderLibrary(e.target.value));
      bind("clearHistory", () => { localStorage.removeItem(HKEY); renderHistory(); });
      bind("loadWeather", loadWeather);
      bind("listenBtn", speakAdvice);
      bind("downloadBtn", downloadReport);
      bind("shareBtn", shareReport);
      setListenLabel();
      document.addEventListener("langchange", () => {
        renderHistory(); renderCalendar(); renderTip();
        loadLibrary();
        setListenLabel();
        const wb = $("weatherBody");
        if (wb && wb.querySelector(".wx-grid")) loadWeather();
      });
    } catch (err) {
      console.error("AgrovetFeatures init error:", err);
    }
  }

  window.AgrovetFeatures = { onResult, init };
  if (document.readyState !== "loading") init();
  else document.addEventListener("DOMContentLoaded", init);
})();
