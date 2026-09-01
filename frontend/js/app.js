/* THE LEDGER — App Bootstrap
   Toasts, veil numeral beat (M1), single health poller + ledger:health,
   aria-live announce hub (G12), seal init, foot year.
   Footer/CTA navigation is delegated in router.js — no bindings here (B5). */
(function () {
  "use strict";

  function qs(sel) { return document.querySelector(sel); }

  /* ────── Toast System ────── */
  function toast(message, type) {
    var container = qs("#toasts");
    if (!container) return;

    var t = document.createElement("div");
    t.className = "toast";
    t.dataset.type = type || "info";
    t.textContent = message;
    container.appendChild(t);

    setTimeout(function () {
      t.style.opacity = "0";
      t.style.transform = "translateY(8px) scale(0.95)";
      t.style.transition = "all 0.3s ease";
      setTimeout(function () { t.remove(); }, 300);
    }, 4000);
  }

  /* ────── aria-live announce hub (G12) ────── */
  function announce(msg) {
    var el = qs("#sr-live");
    if (!el) return;
    el.textContent = "";
    requestAnimationFrame(function () { el.textContent = msg; });
  }

  /* ────── Veil · numeral beat (M1) ────── */
  function bootVeil() {
    var veil = qs("#veil");
    if (!veil) return;
    var numeral = veil.querySelector(".veil__numeral");
    var pct = 0;
    var settled = false;

    function dissolve() {
      if (settled) return;
      settled = true;
      veil.style.opacity = "0";
      veil.style.transition = "opacity 0.6s ease";
      setTimeout(function () { veil.remove(); }, 620);
    }

    function finish() {
      var reduced = window.LedgerMotion && window.LedgerMotion.isReduced;
      if (reduced || typeof gsap === "undefined" || !numeral) {
        if (numeral) numeral.textContent = pct;
        dissolve();
        return;
      }
      var obj = { v: 0 };
      gsap.to(obj, {
        v: pct,
        duration: 0.8,
        ease: "power2.out",
        onUpdate: function () { numeral.textContent = Math.round(obj.v); },
        onComplete: dissolve,
      });
    }

    var timeout = setTimeout(finish, 1600);
    document.addEventListener("ledger:readiness", function (e) {
      pct = (e.detail && e.detail.percent) || 0;
      clearTimeout(timeout);
      finish();
    }, { once: true });
  }

  function hideVeil() {
    var veil = qs("#veil");
    if (!veil) return;
    veil.style.opacity = "0";
    veil.style.transition = "opacity 0.6s ease";
    setTimeout(function () { veil.remove(); }, 600);
  }

  /* ────── Single health poller → ledger:health (B8) ────── */
  async function checkHealth() {
    var ok = false;
    try {
      await window.LedgerAPI.health();
      ok = true;
    } catch (e) { ok = false; }

    var footDot = qs("#foot-status-dot");
    var footText = qs("#foot-status");
    if (footDot) footDot.dataset.status = ok ? "" : "error";
    if (footText) footText.textContent = ok ? "ENGINE RUNNING" : "ENGINE OFFLINE";

    document.dispatchEvent(new CustomEvent("ledger:health", { detail: { ok: ok } }));
  }

  /* ────── Init Seal ────── */
  function initSeal() {
    var container = qs(".cold-open__seal");
    if (!container || !window.LedgerSeal) return;

    if (window.LedgerAPI) {
      window.LedgerAPI.readiness(130, 28).then(function (data) {
        var pct = data && data.readiness_percentage != null ? data.readiness_percentage : 0;
        window.LedgerSeal.init(container, pct);
      }).catch(function () {
        window.LedgerSeal.init(container, 0);
      });
    } else {
      window.LedgerSeal.init(container, 0);
    }

    window.addEventListener("resize", function () {
      window.LedgerSeal.resize(container);
    });
  }

  /* ────── Boot ────── */
  function boot() {
    var yearEl = qs("#foot-year");
    if (yearEl) yearEl.textContent = new Date().getFullYear();

    if (window.LedgerAPI) {
      checkHealth();
      setInterval(checkHealth, 30000);
    }

    initSeal();
    bootVeil();
  }

  /* ────── Expose globals ────── */
  window.LedgerApp = {
    toast: toast,
    announce: announce,
    hideVeil: hideVeil,
  };

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot);
  } else {
    boot();
  }
})();
