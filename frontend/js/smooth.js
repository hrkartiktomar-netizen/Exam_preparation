/* THE LEDGER — smooth scroll bridge · Lenis ↔ GSAP ticker sync.
   Quality-adaptive: full (all effects), lite (no 3D, reduced particles),
   reduced (instant states). Respects prefers-reduced-motion.
   Registers ScrollTrigger, SplitText, Flip, Observer with GSAP. */
(function () {
  "use strict";

  /* ---------- quality tier detection ---------- */
  const Q = {
    FULL: "full",
    LITE: "lite",
    REDUCED: "reduced",
  };

  function detectQuality() {
    const body = document.body;
    const stored = body.dataset.quality;
    if (stored && Object.values(Q).includes(stored)) return stored;

    // Respect prefers-reduced-motion
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
      return Q.REDUCED;
    }

    // Heuristic: low-end device detection
    const cores = navigator.hardwareConcurrency || 2;
    const mem = navigator.deviceMemory || 4; // GB, Chrome only
    if (cores <= 2 || mem <= 2) return Q.LITE;

    return Q.FULL;
  }

  /* ---------- Lenis smooth scroll ---------- */
  let lenis = null;

  function initLenis(quality) {
    if (quality === Q.REDUCED) {
      // No smooth scroll in reduced-motion mode
      return null;
    }

    const root = document.documentElement;
    const lerp = parseFloat(
      getComputedStyle(root).getPropertyValue("--scroll-lerp") || "0.1"
    );
    const duration = parseFloat(
      getComputedStyle(root).getPropertyValue("--scroll-duration") || "1.2"
    );

    lenis = new Lenis({
      lerp: lerp,
      duration: duration,
      smoothWheel: true,
      wheelMultiplier: 1,
      touchMultiplier: 2,
      infinite: false,
    });

    return lenis;
  }

  /* ---------- GSAP plugin registration ---------- */
  function registerPlugins() {
    if (typeof gsap === "undefined") {
      console.warn("[smooth] GSAP not loaded — skipping plugin registration");
      return false;
    }

    // Register available plugins
    const plugins = [];
    if (typeof ScrollTrigger !== "undefined") plugins.push(ScrollTrigger);
    if (typeof SplitText !== "undefined") plugins.push(SplitText);
    if (typeof Flip !== "undefined") plugins.push(Flip);
    if (typeof Observer !== "undefined") plugins.push(Observer);

    if (plugins.length) {
      gsap.registerPlugin(...plugins);
    }

    // Configure GSAP defaults from design tokens
    const root = document.documentElement;
    const cs = getComputedStyle(root);

    gsap.defaults({
      ease: cs.getPropertyValue("--e-out").trim() || "power3.out",
      duration: parseFloat(cs.getPropertyValue("--t-med") || "320") / 1000,
    });

    return true;
  }

  /* ---------- Lenis ↔ GSAP ticker bridge ---------- */
  function bridgeTicker(lenis, quality) {
    if (!lenis || typeof gsap === "undefined") return;

    // Sync Lenis scroll with GSAP's ticker for ScrollTrigger coordination
    lenis.on("scroll", function () {
      if (typeof ScrollTrigger !== "undefined") {
        ScrollTrigger.update();
      }
    });

    // Drive Lenis from GSAP's RAF ticker for frame-perfect sync
    gsap.ticker.add(function (time) {
      lenis.raf(time * 1000);
    });

    // Disable Lenis's own RAF since GSAP drives it
    gsap.ticker.lagSmoothing(0);
  }

  /* ---------- ScrollTrigger quality-adaptive defaults ---------- */
  function configureScrollTrigger(quality) {
    if (typeof ScrollTrigger === "undefined") return;

    ScrollTrigger.defaults({
      toggleActions: "play none none reverse",
    });

    // Refresh on font/image load for accurate measurements
    if (document.fonts && document.fonts.ready) {
      document.fonts.ready.then(function () {
        ScrollTrigger.refresh();
      });
    }

    // Refresh on resize (debounced by ScrollTrigger internally)
    window.addEventListener("load", function () {
      ScrollTrigger.refresh();
    });
  }

  /* ---------- matchMedia for device-adaptive GSAP ---------- */
  function setupMatchMedia(quality) {
    if (typeof gsap === "undefined" || typeof ScrollTrigger === "undefined") return;

    const mm = gsap.matchMedia();

    mm.add(
      {
        isDesktop: "(min-width: 1025px) and (pointer: fine)",
        isTablet: "(min-width: 769px) and (max-width: 1024px)",
        isMobile: "(max-width: 768px)",
        isReduced: "(prefers-reduced-motion: reduce)",
      },
      function (context) {
        const { isDesktop, isTablet, isMobile, isReduced } = context.conditions;

        // Store conditions for other modules to read
        window.LedgerMedia = {
          isDesktop: isDesktop,
          isTablet: isTablet,
          isMobile: isMobile,
          isReduced: isReduced,
          quality: quality,
        };

        return function () {
          // Cleanup callback — called on context change
        };
      }
    );

    return mm;
  }

  /* ---------- public API ---------- */
  function init() {
    const quality = detectQuality();
    document.body.dataset.quality = quality;

    const gsapReady = registerPlugins();
    if (!gsapReady) {
      console.warn("[smooth] GSAP not available — running in static mode");
      window.LedgerMedia = { isDesktop: true, isTablet: false, isMobile: false, isReduced: true, quality: Q.REDUCED };
      window.LedgerSmooth = { quality: Q.REDUCED, lenis: null, destroy: function () {} };
      return;
    }

    const l = initLenis(quality);
    if (l) {
      bridgeTicker(l, quality);
    }
    configureScrollTrigger(quality);
    const mm = setupMatchMedia(quality);

    window.LedgerSmooth = {
      quality: quality,
      lenis: l,

      /** Temporarily stop smooth scroll (e.g., during modal/exam) */
      stop: function () {
        if (l) l.stop();
      },

      /** Resume smooth scroll */
      start: function () {
        if (l) l.start();
      },

      /** Programmatic scroll to element or position */
      scrollTo: function (target, opts) {
        if (l) {
          l.scrollTo(target, opts);
        } else if (typeof target === "number") {
          window.scrollTo({ top: target, behavior: "instant" });
        } else if (target instanceof Element) {
          target.scrollIntoView({ behavior: "instant" });
        }
      },

      /** Full teardown */
      destroy: function () {
        if (l) l.destroy();
        if (mm) mm.revert();
        if (typeof ScrollTrigger !== "undefined") ScrollTrigger.killAll();
        lenis = null;
      },
    };

    console.log(`[smooth] initialized · quality=${quality} · lenis=${!!l} · plugins=${gsapReady}`);
  }

  /* ---------- bootstrap ---------- */
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
