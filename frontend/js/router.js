/* THE LEDGER — Hash Router with GSAP Flip transitions.
   Routes: today, exam, pyq, descriptive, tracker, updates, review, results.
   Each route swap uses GSAP Flip for layout persistence. */
(function () {
  "use strict";

  var ROUTES = ["today", "exam", "pyq", "descriptive", "tracker", "updates", "review", "results"];
  var currentRoute = null;
  var onRouteChange = [];

  function getRoute() {
    var hash = window.location.hash.replace("#", "").split("?")[0] || "today";
    return ROUTES.indexOf(hash) >= 0 ? hash : "today";
  }

  function showView(routeId) {
    var panels = document.querySelectorAll("[data-view-panel]");
    var entering = null;
    var outgoing = null;

    panels.forEach(function (panel) {
      if (panel.dataset.viewPanel === routeId) entering = panel;
      else if (panel.classList.contains("is-active")) outgoing = panel;
    });

    var hallActive = !!document.querySelector(".exam-live.is-active");
    var canFlip = !hallActive &&
      typeof Flip !== "undefined" && typeof gsap !== "undefined" &&
      window.LedgerMotion && !window.LedgerMotion.isReduced && outgoing && entering;

    if (canFlip) {
      var state = Flip.getState(panels);
      panels.forEach(function (panel) {
        panel.classList.toggle("is-active", panel === entering);
      });
      Flip.from(state, {
        duration: 0.4,
        ease: "power2.inOut",
        absolute: false,
        fade: true,
        nested: true,
      });
    } else {
      panels.forEach(function (panel) {
        panel.classList.toggle("is-active", panel === entering);
      });
    }

    // Update nav
    if (window.LedgerNav) window.LedgerNav.selectTab(routeId);

    // Scroll to top
    if (window.LedgerSmooth && window.LedgerSmooth.lenis) {
      window.LedgerSmooth.scrollTo(0, { immediate: true });
    } else {
      window.scrollTo(0, 0);
    }

    // Refresh ScrollTrigger for new content
    if (typeof ScrollTrigger !== "undefined") {
      setTimeout(function () { ScrollTrigger.refresh(); }, 100);
    }

    // Disable smooth scroll during exam
    if (window.LedgerSmooth) {
      if (routeId === "exam") {
        window.LedgerSmooth.stop();
      } else {
        window.LedgerSmooth.start();
      }
    }

    // Fire event + callbacks
    var prev = currentRoute;
    currentRoute = routeId;
    document.dispatchEvent(new CustomEvent("ledger:routechange", { detail: { route: routeId, prev: prev } }));
    onRouteChange.forEach(function (fn) { fn(routeId, prev); });
    if (window.LedgerApp && window.LedgerApp.announce) {
      window.LedgerApp.announce(routeId === "today" ? "Today" : routeId.charAt(0).toUpperCase() + routeId.slice(1) + " view");
    }

    return entering;
  }

  function navigate(routeId) {
    if (ROUTES.indexOf(routeId) < 0) routeId = "today";
    if (routeId === currentRoute) return;
    window.location.hash = "#" + routeId;
  }

  function handleHash() {
    var route = getRoute();
    if (route !== currentRoute) {
      showView(route);
    }
  }

  function init() {
    window.addEventListener("hashchange", handleHash);

    // One delegated activator for every [data-view] element, present or future (B4/B5)
    document.addEventListener("click", function (e) {
      var el = e.target && e.target.closest ? e.target.closest("[data-view]") : null;
      if (!el) return;
      e.preventDefault();
      navigate(el.dataset.view);
    });

    document.addEventListener("keydown", function (e) {
      if (e.key !== "Enter" && e.key !== " ") return;
      var el = e.target && e.target.closest ? e.target.closest("[data-view]") : null;
      // Native buttons/links activate via click — skip to avoid double fire
      if (!el || el.tagName === "BUTTON" || el.tagName === "A") return;
      e.preventDefault();
      navigate(el.dataset.view);
    });

    // Initial route
    handleHash();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }

  window.LedgerRouter = {
    navigate: navigate,
    getRoute: getRoute,
    onRoute: function (fn) {
      onRouteChange.push(fn);
      // Replay: modules that register after first paint still get the current route (B1)
      if (currentRoute) fn(currentRoute, null);
    },
    replay: function () {
      onRouteChange.forEach(function (fn) { fn(currentRoute, null); });
    },
    routes: ROUTES,
  };

  /* Ceremonial threshold: clip-path wipe when entering the hall (G2).
     lite/reduced fall through to the instant swap above. */
  document.addEventListener("ledger:routechange", function (e) {
    if (e.detail.route !== "exam") return;
    if (typeof gsap === "undefined") return;
    if (!window.LedgerMotion || window.LedgerMotion.isReduced || window.LedgerMotion.isLite) return;
    var panel = document.querySelector('[data-view-panel="exam"]');
    if (!panel) return;
    gsap.fromTo(panel,
      { clipPath: "inset(0 0 100% 0)" },
      {
        clipPath: "inset(0 0 0% 0)",
        duration: 1.1,
        ease: "power2.inOut",
        clearProps: "clipPath",
      }
    );
  });
})();
