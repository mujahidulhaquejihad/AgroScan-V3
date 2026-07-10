/* Optional extras: i18n, resources, drag-drop, chatbot */
(function () {
  var cfg = window.AGROVET_CONFIG || {};
  var API = cfg.API_BASE || "";
  function $(id) { return document.getElementById(id); }

  function init() {
    try {
      if (window.AgrovetI18n) {
        window.AgrovetI18n.applyI18n();
        var langBtn = $("langToggle");
        if (langBtn) langBtn.onclick = function () { window.AgrovetI18n.toggleLang(); };
      }
      document.addEventListener("langchange", function () {
        if (govLinks.length) paintGovGrid();
        if (emergencyContacts.length) paintEmergency();
      });
      loadResources();
      setupDragDrop();
      setupChat();
    } catch (e) { console.error("app-extra:", e); }
  }

  var govLinks = [];
  var govFilter = "all";
  var govQuery = "";

  function i18n() { return window.AgrovetI18n; }

  function catLabel(cat) {
    var key = "resources_cat_" + (cat || "ministry");
    return i18n() ? i18n().t(key) : cat;
  }

  function visitLabel() {
    return i18n() ? i18n().t("resources_visit") : "Visit portal";
  }

  function esc(s) {
    return String(s || "").replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/"/g, "&quot;");
  }

  function renderGovCard(c) {
    var cat = c.category || "ministry";
    var abbr = c.abbr || (c.name || "?").slice(0, 3).toUpperCase();
    var name = i18n() ? i18n().govField(c, "name") : c.name;
    var desc = i18n() ? i18n().govField(c, "desc") : c.desc;
    return "<a class='gov-card' href='" + esc(c.url) + "' target='_blank' rel='noopener' data-cat='" + esc(cat) + "'>" +
      "<div class='gov-card-top'><span class='gov-icon'>" + esc(abbr) + "</span>" +
      "<span class='gov-tag'>" + esc(catLabel(cat)) + "</span></div>" +
      "<h3 class='gov-title'>" + esc(name) + "</h3>" +
      "<p class='gov-desc'>" + esc(desc) + "</p>" +
      "<span class='gov-cta'>" + esc(visitLabel()) + " &#8594;</span></a>";
  }

  var emergencyContacts = [];

  function renderEmergencyCard(c) {
    var phone = c.phone;
    var name = i18n() && i18n().emField(phone, "name") ? i18n().emField(phone, "name") : c.name;
    var hours = i18n() && i18n().emField(phone, "hours") ? i18n().emField(phone, "hours") : c.hours;
    var note = i18n() && i18n().emField(phone, "note") ? i18n().emField(phone, "note") : c.note;
    var callTxt = i18n() ? i18n().t("call_btn", { phone: phone }) : ("Call " + phone);
    return "<div class='contact-card'><div class='cname'>" + esc(name) +
      "</div><div class='chours'>" + esc(hours) + "</div><div class='cnote'>" + esc(note) +
      "</div><a class='call-btn' href='tel:" + phone + "'>" + esc(callTxt) + "</a></div>";
  }

  function paintEmergency() {
    var eg = $("emergencyGrid");
    if (!eg || !emergencyContacts.length) return;
    var html = "", i;
    for (i = 0; i < emergencyContacts.length; i++) html += renderEmergencyCard(emergencyContacts[i]);
    eg.innerHTML = html;
  }

  function filterGovLinks() {
    var q = govQuery.toLowerCase().trim();
    var out = [], i, c, hay;
    for (i = 0; i < govLinks.length; i++) {
      c = govLinks[i];
      if (govFilter !== "all" && c.category !== govFilter) continue;
      hay = (c.name + " " + c.desc + " " + (c.abbr || "") + " " + (c.category || "")).toLowerCase();
      if (q && hay.indexOf(q) < 0) continue;
      out.push(c);
    }
    return out;
  }

  function paintGovGrid() {
    var gg = $("govGrid"), empty = $("govEmpty"), count = $("govCount");
    if (!gg) return;
    var list = filterGovLinks(), html = "", i;
    for (i = 0; i < list.length; i++) html += renderGovCard(list[i]);
    gg.innerHTML = html;
    if (empty) empty.className = list.length ? "gov-empty hidden" : "gov-empty";
    if (count) count.textContent = String(govLinks.length);
  }

  function setupGovHub() {
    var search = $("govSearch"), filters = $("govFilters");
    if (search) {
      search.oninput = function () { govQuery = search.value; paintGovGrid(); };
    }
    if (filters) {
      filters.onclick = function (e) {
        var btn = e.target;
        if (!btn || !btn.getAttribute || btn.getAttribute("data-filter") == null) return;
        govFilter = btn.getAttribute("data-filter");
        var chips = filters.querySelectorAll(".gov-filter"), j;
        for (j = 0; j < chips.length; j++) {
          chips[j].className = chips[j].getAttribute("data-filter") === govFilter
            ? "gov-filter active" : "gov-filter";
        }
        paintGovGrid();
      };
    }
  }

  function loadResources() {
    var x = new XMLHttpRequest();
    x.open("GET", API + "/api/resources", true);
    x.onload = function () {
      if (x.status !== 200) return;
      try {
        var d = JSON.parse(x.responseText);
        var eg = $("emergencyGrid");
        if (d.emergency_contacts) {
          emergencyContacts = d.emergency_contacts;
          paintEmergency();
        }
        if (d.gov_links) {
          govLinks = d.gov_links;
          setupGovHub();
          paintGovGrid();
        }
      } catch (e) {}
    };
    x.send();
  }

  function setupDragDrop() {
    var dropzone = $("dropzone");
    if (!dropzone) return;
    dropzone.ondragover = function (e) { e.preventDefault(); dropzone.className = "uploader dragover"; };
    dropzone.ondragleave = function () { dropzone.className = "uploader"; };
    dropzone.ondrop = function (e) {
      e.preventDefault();
      dropzone.className = "uploader";
      if (e.dataTransfer && e.dataTransfer.files[0] && window.agrovetPickFile) {
        var inp = $("fileInput");
        if (inp) { inp.files = e.dataTransfer.files; window.agrovetPickFile(inp); }
      }
    };
  }

  var lastDisease = null;

  function setupChat() {
    var toggle = $("chatToggle"), panel = $("chatPanel"), close = $("chatClose"), form = $("chatForm");
    if (toggle) toggle.onclick = function () {
      if (panel) panel.className = panel.className.indexOf("hidden") >= 0 ? "chat-panel" : "chat-panel hidden";
    };
    if (close && panel) close.onclick = function () { panel.className = "chat-panel hidden"; };
    if (form) form.onsubmit = function (e) {
      e.preventDefault();
      var txt = $("chatText");
      if (!txt || !txt.value.trim()) return;
      var msg = txt.value.trim();
      txt.value = "";
      sendChat(msg);
    };
  }

  function sendChat(message) {
    var log = $("chatLog");
    if (message && log) {
      var u = document.createElement("div");
      u.className = "msg user";
      u.textContent = message;
      log.appendChild(u);
    }
    var x = new XMLHttpRequest();
    x.open("POST", API + "/api/chat", true);
    x.setRequestHeader("Content-Type", "application/json");
    x.onload = function () {
      try {
        var d = JSON.parse(x.responseText);
        if (log) {
          var b = document.createElement("div");
          b.className = "msg bot";
          b.textContent = d.reply;
          log.appendChild(b);
          log.scrollTop = log.scrollHeight;
        }
      } catch (e) {}
    };
    var lang = i18n() ? i18n().lang : "en";
    x.send(JSON.stringify({ message: message, context_disease: lastDisease, lang: lang }));
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
  else init();
})();
