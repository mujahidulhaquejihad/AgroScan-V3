/* AgroVet core - ES5-safe (works in older browsers, no fetch/async required) */
(function () {
  var API = "";
  if (window.AGROVET_CONFIG && window.AGROVET_CONFIG.API_BASE) {
    API = window.AGROVET_CONFIG.API_BASE;
  }

  function $(id) { return document.getElementById(id); }

  function T(key, vars) {
    return window.AgrovetI18n ? window.AgrovetI18n.t(key, vars) : key;
  }

  function setStatus(text, isBad) {
    var el = $("status");
    if (!el) return;
    el.textContent = text;
    if (isBad) el.className = "status pill bad";
    else el.className = "status pill";
  }

  function xhrGet(url, ok, fail) {
    var x = new XMLHttpRequest();
    x.open("GET", url, true);
    x.timeout = 10000;
    x.onload = function () {
      if (x.status >= 200 && x.status < 300) {
        try { ok(JSON.parse(x.responseText)); }
        catch (e) { fail("bad json"); }
      } else fail("HTTP " + x.status);
    };
    x.onerror = function () { fail("network"); };
    x.ontimeout = function () { fail("timeout"); };
    x.send();
  }

  function formatErr(detail) {
    if (!detail) return T("err_prediction");
    if (typeof detail === "string") return detail;
    if (detail.msg) return detail.msg;
    if (detail.length && detail[0] && detail[0].msg) return detail[0].msg;
    return JSON.stringify(detail);
  }

  function xhrPostFile(url, file, ok, fail, onProgress) {
    var fd = new FormData();
    fd.append("file", file, file.name || "leaf.jpg");
    var x = new XMLHttpRequest();
    x.open("POST", url, true);
    x.timeout = 300000;
    if (x.upload && onProgress) {
      x.upload.onprogress = function (ev) {
        if (ev.lengthComputable) {
          onProgress(T("uploading_pct", { pct: Math.round(ev.loaded / ev.total * 100) }));
        }
      };
    }
    x.onload = function () {
      if (!x.responseText) {
        fail("Empty response (HTTP " + x.status + ").");
        return;
      }
      try {
        var data = JSON.parse(x.responseText);
        if (x.status >= 200 && x.status < 300) ok(data);
        else fail(formatErr(data.detail) || ("HTTP " + x.status));
      } catch (e) {
        fail("Server returned invalid JSON (HTTP " + x.status + ")");
      }
    };
    x.onerror = function () { fail("Network error during upload."); };
    x.ontimeout = function () { fail("Timed out after 5 min."); };
    x.send(fd);
  }

  function compressForUpload(file, done) {
    if (!window.FileReader || !document.createElement("canvas").getContext) {
      done(file);
      return;
    }
    var reader = new FileReader();
    reader.onload = function () {
      var img = new Image();
      img.onload = function () {
        var maxSide = 1024;
        var w = img.width, h = img.height;
        if (w > maxSide || h > maxSide) {
          if (w > h) { h = Math.round(h * maxSide / w); w = maxSide; }
          else { w = Math.round(w * maxSide / h); h = maxSide; }
        }
        var canvas = document.createElement("canvas");
        canvas.width = w;
        canvas.height = h;
        var ctx = canvas.getContext("2d");
        ctx.drawImage(img, 0, 0, w, h);
        if (canvas.toBlob) {
          canvas.toBlob(function (blob) {
            if (!blob) { done(file); return; }
            var out = new File([blob], "leaf.jpg", { type: "image/jpeg" });
            done(out);
          }, "image/jpeg", 0.85);
        } else {
          done(file);
        }
      };
      img.onerror = function () { done(file); };
      img.src = reader.result;
    };
    reader.onerror = function () { done(file); };
    reader.readAsDataURL(file);
  }

  var selectedFile = null;
  var apiOnline = false;
  var statusTry = 0;
  var lastResultData = null;
  var lastStatusKey = "status_checking";
  var lastStatusVars = null;
  var lastStatusBad = false;

  function isImage(file) {
    if (!file) return false;
    if (file.type && file.type.indexOf("image/") === 0) return true;
    return /\.(jpe?g|png|webp|bmp|gif)$/i.test(file.name || "");
  }

  function updateAnalyzeBtn() {
    var btn = $("analyzeBtn");
    if (btn) btn.disabled = !(selectedFile && apiOnline);
  }

  function refreshStatusText() {
    setStatus(T(lastStatusKey, lastStatusVars), lastStatusBad);
  }

  function checkStatus() {
    lastStatusKey = "status_checking";
    lastStatusVars = null;
    lastStatusBad = false;
    refreshStatusText();
    xhrGet(API + "/api/status", function (s) {
      var models = s.disease_models_loaded || [];
      if (models.length) {
        apiOnline = true;
        lastStatusKey = "status_models";
        lastStatusVars = { n: models.length, device: s.device || "cpu" };
        lastStatusBad = false;
        refreshStatusText();
        var banner = $("offlineBanner");
        if (banner) banner.className = "offline-banner hidden";
      } else {
        apiOnline = false;
        lastStatusKey = "status_not_trained";
        lastStatusBad = true;
        refreshStatusText();
      }
      updateAnalyzeBtn();
    }, function () {
      statusTry++;
      if (statusTry < 20) {
        lastStatusKey = statusTry < 3 ? "status_loading" : "status_connecting";
        lastStatusVars = statusTry < 3 ? null : { n: statusTry };
        lastStatusBad = false;
        refreshStatusText();
        setTimeout(checkStatus, 2000);
      } else {
        apiOnline = false;
        lastStatusKey = "status_api_offline";
        lastStatusVars = null;
        lastStatusBad = true;
        refreshStatusText();
        var banner = $("offlineBanner");
        if (banner) banner.className = "offline-banner";
        updateAnalyzeBtn();
      }
    });
  }

  window.agrovetPickFile = function (input) {
    var file = input.files && input.files[0];
    var err = $("errorBox");
    if (err) err.className = "error hidden";
    if (!file) return;
    if (!isImage(file)) {
      if (err) { err.textContent = T("err_bad_image"); err.className = "error"; }
      return;
    }
    selectedFile = file;
    var preview = $("preview");
    var placeholder = $("placeholder");
    var fname = $("fileName");
    if (preview) {
      preview.src = URL.createObjectURL(file);
      preview.style.display = "block";
    }
    if (placeholder) placeholder.style.display = "none";
    if (fname) {
      var kb = Math.round(file.size / 1024);
      fname.textContent = T("file_ready", { name: file.name, kb: kb, action: T("file_action") });
      fname.className = "file-name muted small";
    }
    updateAnalyzeBtn();
  };

  function pct(x) { return (x * 100).toFixed(1) + "%"; }

  function renderResult(data) {
    lastResultData = data;
    var results = $("results");
    if (results) results.className = "results";

    var g = data.stage1_leaf_gate || {};
    var s1 = $("stage1Body");
    if (s1) {
      if (g.available === false) {
        s1.innerHTML = "<p class='muted'>" + (g.note || T("leaf_skipped")) + "</p>";
      } else if (!g.is_leaf) {
        s1.innerHTML = "<p>" + T("image_is") + " <span class='leaf-no'>" + T("not_leaf") + "</span></p>";
        if (data.message) {
          s1.innerHTML += "<p class='muted' style='margin-top:10px'>" + data.message + "</p>";
        }
      } else {
        var leafLow = g.leaf_probability < 0.8;
        s1.innerHTML = "<p>" + T("image_is") + " <span class='leaf-yes'>" + T("is_leaf") + "</span></p>" +
          "<div class='conf'>" + T("leaf_prob") + " <strong>" + pct(g.leaf_probability) + "</strong></div>" +
          "<div class='bar'><i style='width:" + (g.leaf_probability * 100) + "%'></i></div>" +
          (leafLow ? "<p class='muted small' style='margin-top:8px'>" + T("photo_tip") + "</p>" : "");
      }
    }

    var d = data.stage2_disease;
    var bestCard = $("bestCard"), modelsCard = $("modelsCard"), adviceCard = $("adviceCard");
    if (!d) {
      if (bestCard) bestCard.className = "card stage best hidden";
      if (modelsCard) modelsCard.className = "card stage hidden";
      if (adviceCard) adviceCard.className = "card stage hidden";
      if ($("lowConfAlert")) $("lowConfAlert").className = "low-conf-alert hidden";
      if ($("resultActions")) $("resultActions").className = "result-actions hidden";
      return;
    }

    var b = d.best_answer;
    var alertBox = $("lowConfAlert");
    var lowConf = b.low_confidence || b.confidence < 0.8;

    if (alertBox) {
      if (lowConf) {
        var msg = b.recommendation || T("low_conf_msg");
        alertBox.innerHTML = "<strong>\u26A0 " + T("low_conf_title", { pct: pct(b.confidence) }) + "</strong>" +
          msg + "<br><br>" +
          T("call_label") + " " +
          "<a href='tel:16123'>Krishi 16123</a> \u00B7 <a href='tel:16358'>Vet 16358</a>";
        alertBox.className = "low-conf-alert";
      } else {
        alertBox.className = "low-conf-alert hidden";
      }
    }

    if (bestCard) bestCard.className = "card stage best";
    if ($("bestBody")) {
      $("bestBody").innerHTML = "<div class='verdict'><span class='plant'>" + b.plant +
        "</span><span class='cond " + (b.is_healthy ? "healthy" : "disease") + "'>" + b.condition +
        "</span>" + (lowConf ? "<span class='badge warn'>" + T("badge_low") + "</span>" : "<span class='badge ok'>" + T("badge_ok") + "</span>") +
        "</div><div class='conf'>" + T("confidence") + " <strong>" + pct(b.confidence) + "</strong></div>" +
        "<div class='bar'><i style='width:" + (b.confidence * 100) + "%'></i></div>" +
        (b.method ? "<div class='meta-row'><span>" + b.method + "</span>" +
          (b.agreement ? "<span>" + b.agreement + "</span>" : "") + "</div>" : "");
    }

    if (b.advice && adviceCard) {
      adviceCard.className = "card stage";
      var a = b.advice;
      var html = "<p class='muted'>" + a.summary + "</p><div class='advice-grid'>" +
        "<div><h4>" + T("treatment") + "</h4><ul>";
      var i;
      for (i = 0; a.treatment && i < a.treatment.length; i++) html += "<li>" + a.treatment[i] + "</li>";
      html += "</ul></div><div><h4>" + T("prevention") + "</h4><ul>";
      for (i = 0; a.prevention && i < a.prevention.length; i++) html += "<li>" + a.prevention[i] + "</li>";
      html += "</ul></div></div>";
      if ($("adviceBody")) $("adviceBody").innerHTML = html;
    }

    if (modelsCard) modelsCard.className = "card stage hidden";

    if (window.AgrovetFeatures && window.AgrovetFeatures.onResult) {
      window.AgrovetFeatures.onResult(data, $("preview") ? $("preview").src : "");
    }
    if (results) results.scrollIntoView({ behavior: "smooth" });
  }

  function setLoaderText(text) {
    var loader = $("loader");
    if (!loader) return;
    var p = loader.getElementsByTagName("p")[0];
    if (p) p.textContent = text;
  }

  function runAnalyze() {
    if (!selectedFile || !apiOnline) {
      var err0 = $("errorBox");
      if (err0) {
        err0.textContent = !apiOnline ? T("err_no_server") : T("err_no_image");
        err0.className = "error";
      }
      return;
    }
    var loader = $("loader"), err = $("errorBox"), results = $("results");
    if (results) results.className = "results hidden";
    if (err) err.className = "error hidden";
    if (loader) loader.className = "loader";
    setLoaderText(T("compressing"));
    lastStatusKey = "status_analyzing";
    lastStatusBad = false;
    refreshStatusText();
    var btn = $("analyzeBtn");
    if (btn) btn.disabled = true;

    compressForUpload(selectedFile, function (uploadFile) {
      setLoaderText(T("uploading"));
      xhrPostFile(API + "/api/predict", uploadFile, function (data) {
        if (loader) loader.className = "loader hidden";
        renderResult(data);
        checkStatus();
        updateAnalyzeBtn();
      }, function (msg) {
        if (loader) loader.className = "loader hidden";
        checkStatus();
        if (err) {
          err.textContent = typeof msg === "string" ? msg : T("err_prediction");
          err.className = "error";
        }
        updateAnalyzeBtn();
      }, function (progressText) {
        setLoaderText(progressText);
      });
    });
  }

  function init() {
    var year = $("year");
    if (year) year.textContent = new Date().getFullYear();

    var fileInput = $("fileInput");
    if (fileInput) fileInput.onchange = function () { window.agrovetPickFile(fileInput); };

    var analyzeBtn = $("analyzeBtn");
    if (analyzeBtn) analyzeBtn.onclick = function (e) {
      if (e && e.preventDefault) e.preventDefault();
      runAnalyze();
    };

    document.addEventListener("langchange", function () {
      refreshStatusText();
      if (selectedFile) {
        var fname = $("fileName");
        if (fname && fname.textContent) {
          var kb = Math.round(selectedFile.size / 1024);
          fname.textContent = T("file_ready", { name: selectedFile.name, kb: kb, action: T("file_action") });
        }
      }
      if (lastResultData) renderResult(lastResultData);
    });

    checkStatus();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
