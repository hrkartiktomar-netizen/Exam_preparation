/* THE LEDGER — LedgerMotion · motion authority + Lenis↔GSAP ticker bridge.
   Quality: localStorage override → prefers-reduced-motion → hardware heuristic.
   One gsap.matchMedia instance owns all condition-scoped animation; setQuality()
   reverts it and re-registers consumers (docs pattern — no manual kill lists).
   Lenis is driven by gsap.ticker (docs canonical); lerp only — duration/easing
   are mutually exclusive with lerp and omitted. */
(function () {
  "use strict";

  const Q = { FULL: "full", LITE: "lite", REDUCED: "reduced" };
  const STORE_KEY = "ledger-quality";

  let quality = Q.FULL;
  let lenis = null;
  let tickerFn = null;
  let mm = null;
  const registry = [];

  const mqDesktop = window.matchMedia("(min-width: 1025px) and (pointer: fine)");
  const mqMobile = window.matchMedia("(max-width: 768px)");

  function announce(msg) {
    if (window.LedgerApp && window.LedgerApp.announce) window.LedgerApp.announce(msg);
  }

  /* ---------- quality resolution ---------- */
  function detectQuality() {
    let stored = null;
    try { stored = localStorage.getItem(STORE_KEY); } catch (e) { /* private mode */ }
    if (stored && Object.values(Q).includes(stored)) return stored;
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return Q.REDUCED;
    const cores = navigator.hardwareConcurrency || 4;
    const mem = navigator.deviceMemory || 4;
    if (cores <= 2 || mem <= 2) return Q.LITE;
    return Q.FULL;
  }

  /* ---------- condition registry ---------- */
  function deviceConditions() {
    return {
      isDesktop: "(min-width: 1025px) and (pointer: fine)",
      isTablet: "(min-width: 769px) and (max-width: 1024px)",
      isMobile: "(max-width: 768px)",
    };
  }

  function conditionsFor(c) {
    return {
      isDesktop: !!c.isDesktop,
      isTablet: !!c.isTablet,
      isMobile: !!c.isMobile,
      isReduced: quality === Q.REDUCED,
      isFull: quality === Q.FULL,
      isLite: quality === Q.LITE,
      animated: quality !== Q.REDUCED,
      quality: quality,
    };
  }

  function attach(entry, m) {
    m.add(deviceConditions(), function (context) {
      const cleanup = entry({ conditions: conditionsFor(context.conditions) });
      return typeof cleanup === "function" ? cleanup : undefined;
    });
  }

  function registerConditions(m) {
    registry.forEach(function (entry) { attach(entry, m); });
  }

  /* ---------- Lenis (lerp only, ticker-driven, lagSmoothing(0)) ---------- */
  function initLenis() {
    if (typeof Lenis === "undefined" || typeof gsap === "undefined") return null;
    const lerp = parseFloat(
      getComputedStyle(document.documentElement).getPropertyValue("--scroll-lerp") || "0.1"
    );
    lenis = new Lenis({
      lerp: lerp,
      smoothWheel: true,
      wheelMultiplier: 1,
      touchMultiplier: 2,
      infinite: false,
    });
    lenis.on("scroll", function () {
      if (typeof ScrollTrigger !== "undefined") ScrollTrigger.update();
    });
    tickerFn = function (time) { lenis.raf(time * 1000); };
    gsap.ticker.add(tickerFn);
    gsap.ticker.lagSmoothing(0);
    return lenis;
  }

  function destroyLenis() {
    if (tickerFn && typeof gsap !== "undefined") { gsap.ticker.remove(tickerFn); tickerFn = null; }
    if (lenis) { lenis.destroy(); lenis = null; }
  }

  /* ---------- reactive quality ---------- */
  function setQuality(next, persist) {
    if (!Object.values(Q).includes(next) || next === quality) return;
    const prev = quality;
    quality = next;
    if (persist !== false) {
      try { localStorage.setItem(STORE_KEY, next); } catch (e) { /* ignore */ }
    }
    document.body.dataset.quality = next;
    document.dispatchEvent(new CustomEvent("ledger:qualitychange", { detail: { quality: next, prev: prev } }));

    if (typeof gsap !== "undefined" && mm) {
      mm.revert();
      registerConditions(mm);
    }

    if (next === Q.REDUCED) destroyLenis();
    else if (!lenis) initLenis();

    if (typeof ScrollTrigger !== "undefined") ScrollTrigger.refresh();
    announce("Motion quality set to " + next);
    console.log("[motion] quality " + prev + " -> " + next);
  }

  /* ---------- init ---------- */
  function init() {
    quality = detectQuality();
    document.body.dataset.quality = quality;

    if (typeof gsap === "undefined") {
      console.warn("[motion] GSAP missing — static mode");
      return;
    }

    const plugins = [];
    if (typeof ScrollTrigger !== "undefined") plugins.push(ScrollTrigger);
    if (typeof SplitText !== "undefined") plugins.push(SplitText);
    if (typeof Flip !== "undefined") plugins.push(Flip);
    if (typeof Observer !== "undefined") plugins.push(Observer);
    if (plugins.length) gsap.registerPlugin(...plugins);

    // --e-out intent (cubic-bezier 0.16,1,0.3,1) maps to native power3.out;
    // raw cubic-bezier strings are unparseable by GSAP without CustomEase (C1).
    gsap.defaults({ ease: "power3.out", duration: 0.32 });

    if (typeof ScrollTrigger !== "undefined") {
      ScrollTrigger.defaults({ toggleActions: "play none none reverse" });
      if (document.fonts && document.fonts.ready) {
        document.fonts.ready.then(function () { ScrollTrigger.refresh(); });
      }
      window.addEventListener("load", function () { ScrollTrigger.refresh(); });
    }

    if (quality !== Q.REDUCED) initLenis();

    if (typeof ScrollTrigger !== "undefined") {
      mm = gsap.matchMedia();
      registerConditions(mm);
    }

    console.log("[motion] initialized · quality=" + quality + " · lenis=" + !!lenis);
  }

  /* ---------- globals (exposed at parse time; populated at init) ---------- */
  window.LedgerMedia = {
    get isDesktop() { return mqDesktop.matches; },
    get isTablet() { return !mqDesktop.matches && !mqMobile.matches; },
    get isMobile() { return mqMobile.matches; },
    get isReduced() { return quality === Q.REDUCED; },
    get quality() { return quality; },
  };

  window.LedgerMotion = {
    get quality() { return quality; },
    get isReduced() { return quality === Q.REDUCED; },
    get isLite() { return quality === Q.LITE; },
    get isFull() { return quality === Q.FULL; },
    get mm() { return mm; },
    setQuality: setQuality,
    register: function (fn) {
      registry.push(fn);
      if (mm) attach(fn, mm);
    },
  };

  window.LedgerSmooth = {
    get quality() { return quality; },
    get lenis() { return lenis; },
    stop: function () { if (lenis) lenis.stop(); },
    start: function () { if (lenis) lenis.start(); },
    scrollTo: function (target, opts) {
      if (lenis) lenis.scrollTo(target, opts);
      else if (typeof target === "number") window.scrollTo({ top: target, behavior: "instant" });
      else if (target instanceof Element) target.scrollIntoView({ behavior: "instant" });
    },
    setQuality: setQuality,
    destroy: function () {
      destroyLenis();
      if (mm) mm.revert();
      registry.length = 0;
      if (typeof ScrollTrigger !== "undefined") ScrollTrigger.killAll();
    },
  };

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
