/* THE LEDGER — App Bootstrap
   Loads in order: smooth → nav → router → seal → API → views → today.
   Manages toasts, veil, health polling, and foot-year. */
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

  /* ────── Veil ────── */
  function hideVeil() {
    var veil = qs("#veil");
    if (!veil) return;
    veil.style.opacity = "0";
    veil.style.transition = "opacity 0.6s ease";
    setTimeout(function () { veil.remove(); }, 600);
  }

  /* ────── Health & Status ────── */
  async function checkHealth() {
    var dot = qs("#health-dot");
    var footDot = qs("#foot-status-dot");
    var footText = qs("#foot-status");

    try {
      var h = await window.LedgerAPI.health();
      if (dot) dot.dataset.status = "ok";
      if (footDot) footDot.dataset.status = "";
      if (footText) footText.textContent = "ENGINE RUNNING";
    } catch (e) {
      if (dot) dot.dataset.status = "error";
      if (footText) footText.textContent = "ENGINE OFFLINE";
    }
  }

  /* ────── Init Seal ────── */
  function initSeal() {
    var container = qs(".cold-open__seal");
    if (!container || !window.LedgerSeal) return;

    // Get readiness from dashboard
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

    // Resize handler
    window.addEventListener("resize", function () {
      window.LedgerSeal.resize(container);
    });
  }

  /* ────── Boot ────── */
  function boot() {
    // Set foot year
    var yearEl = qs("#foot-year");
    if (yearEl) yearEl.textContent = new Date().getFullYear();

    // Health check
    if (window.LedgerAPI) {
      checkHealth();
      setInterval(checkHealth, 30000);
    }

    // Init seal
    initSeal();

    // Hide veil after short delay
    setTimeout(hideVeil, 800);

    // Footer row click routing
    document.querySelectorAll(".footer__row[data-view]").forEach(function (row) {
      row.addEventListener("click", function () {
        if (window.LedgerRouter) {
          window.LedgerRouter.navigate(row.dataset.view);
        }
      });
      row.addEventListener("keydown", function (e) {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          if (window.LedgerRouter) window.LedgerRouter.navigate(row.dataset.view);
        }
      });
    });
  }

  /* ────── Expose globals ────── */
  window.LedgerApp = {
    toast: toast,
    hideVeil: hideVeil,
  };

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot);
  } else {
    boot();
  }
})();
