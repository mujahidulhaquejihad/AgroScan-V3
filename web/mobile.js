/* Mobile UX: camera, gallery, bottom nav, scroll spy */
(function () {
  function $(id) { return document.getElementById(id); }

  function isMobile() {
    return window.matchMedia("(max-width: 768px)").matches;
  }

  function setupUpload() {
    var cameraBtn = $("cameraBtn");
    var galleryBtn = $("galleryBtn");
    var cameraInput = $("cameraInput");
    var fileInput = $("fileInput");

    if (cameraBtn && cameraInput) {
      cameraBtn.onclick = function (e) {
        e.preventDefault();
        cameraInput.click();
      };
    }
    if (galleryBtn && fileInput) {
      galleryBtn.onclick = function (e) {
        e.preventDefault();
        fileInput.click();
      };
    }
  }

  function setupBottomNav() {
    var items = document.querySelectorAll(".mob-nav-item");
    if (!items.length) return;

    var sections = [];
    var i;
    for (i = 0; i < items.length; i++) {
      var sec = items[i].getAttribute("data-section");
      var el = sec ? document.getElementById(sec) : null;
      if (el) sections.push({ id: sec, el: el, link: items[i] });
    }

    function setActive(id) {
      for (i = 0; i < items.length; i++) {
        var on = items[i].getAttribute("data-section") === id;
        items[i].className = on ? "mob-nav-item active" : "mob-nav-item";
      }
    }

    for (i = 0; i < items.length; i++) {
      items[i].addEventListener("click", function () {
        var id = this.getAttribute("data-section");
        setTimeout(function () { setActive(id); }, 300);
      });
    }

    if (!("IntersectionObserver" in window) || !isMobile()) return;

    var obs = new IntersectionObserver(function (entries) {
      var best = null;
      entries.forEach(function (en) {
        if (en.isIntersecting && (!best || en.intersectionRatio > best.ratio)) {
          best = { id: en.target.id, ratio: en.intersectionRatio };
        }
      });
      if (best) setActive(best.id);
    }, { rootMargin: "-20% 0px -55% 0px", threshold: [0.1, 0.25, 0.5] });

    sections.forEach(function (s) { obs.observe(s.el); });
  }

  function init() {
    setupUpload();
    setupBottomNav();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
