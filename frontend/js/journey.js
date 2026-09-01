/* THE LEDGER — Cinematic journey layer.
   Seal handoff · scene crossfades · instrument nav · progress rule ·
   finale slam (M15) · footer choreography (M16).
   Everything registered through LedgerMotion; zero persistent loops. */
(function () {
  "use strict";

  function qs(sel, root) { return (root || document).querySelector(sel); }
  function qsa(sel, root) { return Array.from((root || document).querySelectorAll(sel)); }

  /* Concrete Layer-2 hex per scene, mirroring tokens.css. GSAP cannot
     interpolate var() references, so crossfades write the registered
     custom properties with their concrete values. */
  var SCENE_VARS = {
    "ledger-noir":   { "--canvas": "#0C0E10", "--ink-1": "#EFEAE0", "--ink-2": "#B4ACA0", "--ink-3": "#857E72", "--signal": "#37C092", "--metal": "#C79E4F" },
    "hall-paper":    { "--canvas": "#F1EDE3", "--ink-1": "#23221C", "--ink-2": "#5C584E", "--ink-3": "#7A7568", "--signal": "#1E7A5E", "--metal": "#8F6F35" },
    "signal-ledger": { "--canvas": "#07090B", "--ink-1": "#EFEAE0", "--ink-2": "#9FB4AC", "--ink-3": "#6E837B", "--signal": "#52DCAE", "--metal": "#C79E4F" },
    "brass-close":   { "--canvas": "#07090B", "--ink-1": "#F4EFE4", "--ink-2": "#B3A38B", "--ink-3": "#847659", "--signal": "#37C092", "--metal": "#E3C07C" },
  };

  /* ── S4.1 · Seal handoff: hero seal scrubs into the nav seal ── */
  function attachSealHandoff(m) {
    if (!m.conditions.animated || typeof gsap === "undefined") return;
    var heroSeal = qs("#seal-hero");
    var navSeal = qs(".nav__seal");
    if (!heroSeal || !navSeal) return;

    gsap.set(navSeal, { autoAlpha: 0 });

    /* Measure from the UNTRANSFORMED rects (reset first) so refreshes
       never compound onto mid-flight transforms. */
    function navDelta() {
      gsap.set(heroSeal, { x: 0, y: 0, scale: 1 });
      var a = heroSeal.getBoundingClientRect();
      var b = navSeal.getBoundingClientRect();
      return {
        dx: (b.left + b.width / 2) - (a.left + a.width / 2),
        dy: (b.top + b.height / 2) - (a.top + a.height / 2),
      };
    }

    var tween = gsap.to(heroSeal, {
      scale: 0.16,
      x: function () { return navDelta().dx; },
      y: function () { return navDelta().dy; },
      ease: "none",
      scrollTrigger: {
        trigger: ".cold-open",
        start: "top top",
        end: "bottom 40%",
        scrub: 0.6,
        invalidateOnRefresh: true,
      },
    });
    var navTween = gsap.to(navSeal, {
      autoAlpha: 1,
      ease: "none",
      scrollTrigger: {
        trigger: ".cold-open",
        start: "top 20%",
        end: "bottom 40%",
        scrub: 0.6,
      },
    });

    return function () {
      if (tween.scrollTrigger) tween.scrollTrigger.kill();
      if (navTween.scrollTrigger) navTween.scrollTrigger.kill();
      tween.kill();
      navTween.kill();
      gsap.set(heroSeal, { clearProps: "transform,visibility,opacity" });
      gsap.set(navSeal, { clearProps: "visibility,opacity" });
    };
  }

  /* ── Scene crossfades: blend registered custom properties per section ── */
  var currentScene = "ledger-noir";

  function attachSceneCrossfades(m) {
    if (!m.conditions.animated || typeof gsap === "undefined" || typeof ScrollTrigger === "undefined") return;
    var sections = qsa('#view-today [data-scene]');
    if (!sections.length) return;

    var triggers = [];

    function applyScene(section) {
      var target = section.getAttribute("data-scene");
      if (!target || target === currentScene || !SCENE_VARS[target]) return;
      var from = SCENE_VARS[currentScene] || SCENE_VARS["ledger-noir"];
      var to = Object.assign({}, SCENE_VARS[target], {
        duration: 0.6,
        ease: "power2.inOut",
        immediateRender: false,
        /* Suppress the [data-scene] CSS transition while GSAP frames the blend */
        onStart: function () { section.style.transition = "none"; },
        onComplete: function () { section.style.transition = ""; },
      });
      gsap.fromTo(section, from, to);
      currentScene = target;
    }

    sections.forEach(function (section) {
      triggers.push(ScrollTrigger.create({
        trigger: section,
        start: "top 70%",
        onEnter: function () { applyScene(section); },
        onEnterBack: function () { applyScene(section); },
      }));
    });

    return function () {
      triggers.forEach(function (t) { t.kill(); });
      sections.forEach(function (s) { s.style.transition = ""; });
    };
  }

  /* ── Instrument nav: hide on scroll-down, reveal on scroll-up ── */
  function attachNavObserver(m) {
    if (!m.conditions.animated || typeof Observer === "undefined") return;
    var nav = qs("#topnav");
    if (!nav) return;

    var obs = Observer.create({
      type: "wheel,touch,scroll",
      tolerance: 12,
      onDown: function () {
        if (qs(".exam-live.is-active")) return; // never hide during a live exam
        nav.dataset.hidden = "";
      },
      onUp: function () { delete nav.dataset.hidden; },
    });

    return function () {
      obs.kill();
      delete nav.dataset.hidden;
    };
  }

  /* ── M7 · Scroll progress hairline ── */
  function attachProgressRule(m) {
    if (!m.conditions.animated || typeof ScrollTrigger === "undefined") return;
    var rule = qs(".scroll-progress");
    if (!rule) return;

    var st = ScrollTrigger.create({
      start: 0,
      end: "max",
      onUpdate: function (self) {
        rule.style.transform = "scaleY(" + self.progress + ")";
      },
    });

    return function () {
      st.kill();
      rule.style.transform = "";
    };
  }

  /* ── M15 · Finale stamp slam ── */
  function attachFinaleSlam(m) {
    if (!m.conditions.animated || typeof gsap === "undefined") return;
    var btn = qs(".finale__stamp-btn");
    var ghost = qs(".finale__ghost");
    if (!btn || !ghost) return;

    gsap.set(ghost, { autoAlpha: 0, scale: 1.6, y: -120, rotate: -8 });

    function slam() {
      gsap.timeline()
        .to(ghost, { autoAlpha: 1, y: 0, rotate: -4, scale: 1, duration: 0.45, ease: "power4.in" })
        .to(ghost, { scale: 0.96, duration: 0.08, ease: "power2.out" })
        .to(ghost, { scale: 1, duration: 0.34, ease: "elastic.out(1, 0.6)" })
        .to(btn, { scale: 0.94, duration: 0.09, yoyo: true, repeat: 1, ease: "power2.inOut" }, 0);
    }

    btn.addEventListener("click", slam);
    return function () {
      btn.removeEventListener("click", slam);
      gsap.set(ghost, { clearProps: "all" });
      gsap.set(btn, { clearProps: "transform" });
    };
  }

  /* ── M16 · Footer row stagger + watermark drift ── */
  function attachFooter(m) {
    if (!m.conditions.animated || typeof gsap === "undefined" || typeof ScrollTrigger === "undefined") return;
    var footer = qs("#ledger-footer");
    if (!footer) return;

    var rows = qsa(".footer__row", footer);
    var rowTween = rows.length ? gsap.from(rows, {
      opacity: 0,
      y: 24,
      duration: 0.6,
      stagger: m.conditions.isLite ? 0.16 : 0.08,
      ease: "power3.out",
      scrollTrigger: { trigger: footer, start: "top 85%" },
    }) : null;

    var wm = qs(".footer__watermark", footer);
    var wmTween = null;
    if (wm && m.conditions.isFull) {
      wmTween = gsap.to(wm, {
        xPercent: -6,
        ease: "none",
        scrollTrigger: { trigger: footer, start: "top bottom", end: "bottom bottom", scrub: 0.8 },
      });
    }

    return function () {
      if (rowTween) {
        if (rowTween.scrollTrigger) rowTween.scrollTrigger.kill();
        rowTween.kill();
        gsap.set(rows, { clearProps: "opacity,transform" });
      }
      if (wmTween) {
        if (wmTween.scrollTrigger) wmTween.scrollTrigger.kill();
        wmTween.kill();
        gsap.set(wm, { clearProps: "transform" });
      }
    };
  }

  function init() {
    if (!window.LedgerMotion || typeof window.LedgerMotion.register !== "function") return;
    window.LedgerMotion.register(attachSealHandoff);
    window.LedgerMotion.register(attachSceneCrossfades);
    window.LedgerMotion.register(attachNavObserver);
    window.LedgerMotion.register(attachProgressRule);
    window.LedgerMotion.register(attachFinaleSlam);
    window.LedgerMotion.register(attachFooter);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
