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

    panels.forEach(function (panel) {
      if (panel.dataset.viewPanel === routeId) {
        entering = panel;
        panel.classList.add("is-active");
      } else {
        panel.classList.remove("is-active");
      }
    });

    // Update nav
    if (window.LedgerNav) {
      window.LedgerNav.selectTab(routeId);
    }

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

    // Fire callbacks
    var prev = currentRoute;
    currentRoute = routeId;
    onRouteChange.forEach(function (fn) { fn(routeId, prev); });

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

    // Handle footer row clicks
    document.querySelectorAll("[data-view]").forEach(function (el) {
      el.addEventListener("click", function (e) {
        e.preventDefault();
        navigate(el.dataset.view);
      });
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
    onRoute: function (fn) { onRouteChange.push(fn); },
    routes: ROUTES,
  };
})();
