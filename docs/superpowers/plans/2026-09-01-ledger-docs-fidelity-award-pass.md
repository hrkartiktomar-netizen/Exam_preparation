# The Ledger — Docs-Fidelity & Award-Grade Fix Pass · Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make The Ledger frontend docs-compliant (Lenis/GSAP/Three.js manuals in `frontend/docs/`), bug-free (audit B1–B11, C1–C7), and awwwards-grade by delivering the original rebuild plan's missing spectacle (G1–G12) plus the approved M1–M16 motion maximum on the Today page.

**Architecture:** Vanilla HTML/CSS/JS SPA served by FastAPI (no bundler). `js/smooth.js` becomes the single motion authority (`LedgerMotion`): quality resolution (localStorage → prefers-reduced-motion → hardware heuristic), one `gsap.matchMedia` whose revert/re-register cycle reacts to quality changes, and a `register(fn)` registry so every animation lives inside a condition-scoped context (auto-teardown, SplitText revert). Route/quality/health/readiness state flows via `CustomEvent`s on `document`. Three.js lazy-loads only when the seal initializes in a WebGL tier.

**Tech Stack:** GSAP 3 (+ScrollTrigger/SplitText/Flip/Observer) vendored, Lenis 1.3.26 vendored, Three.js vendored (lazy), plain CSS with custom-property tokens, FastAPI static serving of `/css`, `/js`, `/app`.

**Spec:** `docs/superpowers/specs/2026-09-01-ledger-docs-fidelity-award-pass-design.md` (2026-09-01, approved).

---

## Global rules (read before any task)

**Verification environment** (there is no JS unit-test harness; verification is runtime):
1. Start the server (background): `venv/Scripts/python -m uvicorn main:app --port 8000` with working directory `backend/`. Kill any previous instance on port 8000 first.
2. Browser checks use the `browser-use` MCP tools (`navigate_page`, `take_screenshot`, `list_console_messages`, `evaluate_script`) against `http://127.0.0.1:8000`.
3. A task is done only when its stated checks pass with evidence (console output, screenshot, or DOM inspection). Never claim completion without running the check.

**Git hazard protocol (repo is serviced by concurrent automations, currently mid-rebase):**
- NEVER `git pull`, `git rebase`, `git stash`, or switch branches.
- Before committing: `ls .git/index.lock` — if it exists, wait 10 s and re-check up to 5 times.
- Commit only the exact files your task changed: `git add <explicit paths>` then commit with inline identity:
  ```bash
  git -c user.name="hrkartiktomar-netizen" -c user.email="hrkartiktomar-netizen@users.noreply.github.com" commit -m "<msg>"
  ```
- Never run `git config`. Never `git add -A` / `git add .`.

**Scope discipline (karpathy):**
- Every changed line must trace to the spec. No adjacent "improvements", no refactors of code a task doesn't touch.
- Protected contracts: every element `id`, all `/api` paths, exam state machine/timers/keyboard/strict-lock/zen-mode, five-state palette semantics, timer ring, localStorage answer keys, confirm()/alert() flows. Zero backend edits.
- Render-nothing rule: if an API field is absent, render nothing — never fake data.

**Tier contract (applies to every animation you write):**
- `full` — everything.
- `lite` — halved staggers, no pointer-driven or ambient items.
- `reduced` — authored end states, zero tweens, zero rAF.
- No new persistent rAF loops anywhere. Every animation is ScrollTrigger-gated, IntersectionObserver-gated, event-driven, or a CSS animation.

## File structure

| File | Responsibility after this plan |
|---|---|
| `frontend/index.html` | Boot shell: no-js swap, no hardcoded quality, no eager three.min.js, N-cell split-flap slot, veil numeral, cold-open sub line, thread/progress/ghost markup, `data-lenis-prevent` islands |
| `frontend/js/smooth.js` | **LedgerMotion** — quality authority, Lenis↔ticker bridge, plugin registration, matchMedia registry, event dispatch (S1, S2, C1, C2, C5, C6) |
| `frontend/js/nav.js` | Tabs, IST clock, quality toggle (delegates to LedgerMotion), health dot via event, Observer-driven nav reveal (C7, B8, B9, S4.8) |
| `frontend/js/app.js` | Boot, toasts, single health poller + `ledger:health`, `announce()` (aria-live hub), veil numeral beat (B5, B8, G12, M1) |
| `frontend/js/router.js` | Hash router: delegated `[data-view]`, replay-on-register, `ledger:routechange`, Flip transitions, exam wipe (B1, B4, B5, S4.1, S4.2) |
| `frontend/js/today.js` | Activation-driven Today: N-cell flap counter (B3, M2), plan thresholds (G11), data-true particles (B10, G6), cold-open completeness (G10, M3/M4), M5/M8/M9/M10/M11/M12/M13/M14 |
| `frontend/js/exam.js` | Submit-only start with re-entry guard (B6), timer warnings to aria-live (G12) |
| `frontend/js/seal.js` | Lazy three.js loader, arc rebuild ≥0.5 pt, IO+route-gated loop, context-loss handling, DPR tiers, destroy, quality re-init (C3, G7, G8, G9) |
| `frontend/js/journey.js` | **New.** Cinematic layer: seal handoff scrub, scene crossfades, Observer nav, scroll-progress rule, finale stamp slam + SEALED ghost, footer life (S4.3, S4.4, S4.8, M7, M15, M16) |
| `frontend/js/views.js` | Untouched (B1 fixed by router replay) |
| `frontend/js/api.js` | Untouched |
| `frontend/css/motion.css` | no-js/reduced fallbacks, wipe consumer, M-item keyframes; dead code removed (B7, B11) |
| `frontend/css/today.css` | Component styles for new M-item markup (thread, markers, ghost, verb pill, ambient field) |
| `frontend/css/nav.css` | Observer nav hidden state |
| `frontend/css/tokens.css` | Grain 0.035→0.02 + proportional scene steps (S5) |

---

## Phase P1 — Motion authority + docs compliance

### Task 1: index.html boot hardening

**Files:**
- Modify: `frontend/index.html:2, 26, 32-34, 62-66, 208, 344`

- [ ] **Step 1: no-js class + inline swap (B7)**

In `frontend/index.html`, change line 2 and add the swap immediately after the `<meta charset>` line:

```html
<html lang="en" class="no-js">
```

```html
  <meta charset="utf-8" />
  <script>document.documentElement.classList.remove("no-js");</script>
```

- [ ] **Step 2: Remove hard-coded quality (C6)**

Change line 26 from `<body data-quality="full" data-scene="ledger-noir">` to:

```html
<body data-scene="ledger-noir">
```

Quality is now set by `smooth.js` before first motion init.

- [ ] **Step 3: Veil numeral markup (M1)**

Replace the veil block (lines 32-34) with:

```html
  <!-- Loading veil · readiness numeral beat (M1) -->
  <div class="veil" id="veil" role="status" aria-live="polite">
    <div class="veil__numeral">0</div>
    <div class="veil__text">MEASURED NIGHTLY</div>
  </div>
```

- [ ] **Step 4: N-cell split-flap slot (B3)**

Replace the split-flap block (lines 62-66) with:

```html
          <div class="splitflap" aria-label="Readiness percentage">
            <div class="splitflap__digits"></div>
            <span class="splitflap__unit">%</span>
          </div>
```

`today.js` (Task 6) renders one `.splitflap__digit` per target digit.

- [ ] **Step 5: Lenis scroll island + remove eager three.js (S2, G7)**

Add `data-lenis-prevent` to the exam options container (line 208):

```html
            <div class="exam-options" data-lenis-prevent></div>
```

Delete line 344 entirely:

```html
  <script src="/vendor/three.min.js" defer></script>
```

(three.min.js is injected on demand by `seal.js`, Task 9.)

- [ ] **Step 6: Verify markup parses**

Run (from repo root):

```bash
venv/Scripts/python -c "from html.parser import HTMLParser; p=HTMLParser(); p.feed(open('frontend/index.html',encoding='utf-8').read()); print('parse ok')"
```

Expected: `parse ok`.

- [ ] **Step 7: Commit**

```bash
git add frontend/index.html
git -c user.name="hrkartiktomar-netizen" -c user.email="hrkartiktomar-netizen@users.noreply.github.com" commit -m "feat(frontend): boot hardening — no-js swap, dynamic quality, N-cell flap slot, lazy three"
```

---

### Task 2: smooth.js — LedgerMotion authority (S1, S2)

**Files:**
- Rewrite: `frontend/js/smooth.js` (231 lines → full replacement below)

This fixes C1 (unparseable cubic-bezier ease), C2 (Lenis `duration` without `easing`), C5 (stale `LedgerMedia` snapshot), C6 (quality now detected), and establishes the reactive `mm.revert()` quality cycle and event bus.

- [ ] **Step 1: Replace `frontend/js/smooth.js` entirely with:**

```js
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
      const cleanup = entry(conditionsFor(context.conditions));
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
```

- [ ] **Step 2: Verify no references to the removed API**

```bash
grep -rn "LedgerMedia.quality\b" frontend/js --include="*.js" | grep -v smooth.js || echo "no stale snapshot reads of quality"
```

Expected: `no stale snapshot reads of quality` (seal.js/today.js reads are replaced in Tasks 6/9; if matches remain in files not yet rewritten, note them and continue — they become live getters now anyway, which is the fix).

- [ ] **Step 3: Runtime smoke check**

Start the server (see Global rules) and in browser-use navigate to `http://127.0.0.1:8000`. Then `list_console_messages`. Expected: contains `[motion] initialized · quality=full · lenis=true`, zero red errors. Then `evaluate_script`:

```js
document.body.dataset.quality + " | " + (window.LedgerSmooth.lenis ? "lenis" : "no-lenis") + " | " + window.LedgerMotion.quality
```

Expected: `"full | lenis | full"`.

- [ ] **Step 4: Commit**

```bash
git add frontend/js/smooth.js
git -c user.name="hrkartiktomar-netizen" -c user.email="hrkartiktomar-netizen@users.noreply.github.com" commit -m "feat(frontend): LedgerMotion authority — reactive quality, docs-canonical Lenis/GSAP"
```

---

## Phase P2 — Functional bug fixes

### Task 3: nav.js — quality toggle delegates, health via event, dead code out (C7, B8, B9)

**Files:**
- Modify: `frontend/js/nav.js:52-69, 37-49, 144-148, 157-189, 192-197`

- [ ] **Step 1: Replace `cycleQuality` (lines 52-69) with:**

```js
  /* ---------- quality toggle (delegates to LedgerMotion — C7) ---------- */
  function cycleQuality() {
    const tiers = ["full", "lite", "reduced"];
    const current = window.LedgerMotion ? window.LedgerMotion.quality : (document.body.dataset.quality || "full");
    const next = tiers[(tiers.indexOf(current) + 1) % tiers.length];
    if (window.LedgerMotion) window.LedgerMotion.setQuality(next);
    else document.body.dataset.quality = next;
  }
```

- [ ] **Step 2: Replace `pollHealth` (lines 37-49) with an event subscriber:**

```js
  /* ---------- health dot (single poller lives in app.js; we subscribe) ---------- */
  function subscribeHealth() {
    document.addEventListener("ledger:health", function (e) {
      if (!healthEl) return;
      healthEl.dataset.status = e.detail && e.detail.ok ? "ok" : "error";
    });
  }
```

- [ ] **Step 3: In `buildNav`, replace the health poll lines (147-148) and keep clock cleanup:**

Replace:

```js
    // Start health polling
    pollHealth();
    setInterval(pollHealth, 30000);
```

with:

```js
    // Health updates arrive via ledger:health (polled once in app.js)
    subscribeHealth();

    // Clear clock interval on page exit
    window.addEventListener("pagehide", function () {
      if (clockInterval) clearInterval(clockInterval);
    });
```

- [ ] **Step 4: Delete `setupScrollBehavior` entirely (lines 157-189) and remove its call from `init` (line 196).**

The seal-mini reveal and nav compress return in Task 12 (ScrollTrigger + Observer).

- [ ] **Step 5: Sync the toggle label on quality change — in `init`, before `buildNav();` add:**

```js
    document.addEventListener("ledger:qualitychange", function (e) {
      const btn = document.querySelector(".nav__quality");
      if (btn) btn.textContent = e.detail.quality;
    });
```

- [ ] **Step 6: Verify**

Server running, reload `http://127.0.0.1:8000`. Click the `full` toggle in the nav twice via browser-use. `list_console_messages` expected: `[motion] quality full -> lite` then `lite -> reduced`. `evaluate_script`:

```js
document.body.dataset.quality + " | " + (window.LedgerSmooth.lenis === null ? "lenis-torn-down" : "lenis-live")
```

Expected after two clicks: `"reduced | lenis-torn-down"`. Click once more → `full | lenis-live`.

- [ ] **Step 7: Commit**

```bash
git add frontend/js/nav.js
git -c user.name="hrkartiktomar-netizen" -c user.email="hrkartiktomar-netizen@users.noreply.github.com" commit -m "fix(frontend): quality toggle gates motion, health via event, remove dead scroll handler"
```

---

### Task 4: app.js — single health poller, announce(), delegated footer, veil numeral beat (B5, B8, G12, M1)

**Files:**
- Modify: `frontend/js/app.js:37-52, 95-108` (replace whole file below — 122 lines)

- [ ] **Step 1: Replace `frontend/js/app.js` entirely with:**

```js
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
```

Notes: footer-row click/keydown bindings are gone (router owns them via delegation, Task 5); `#health-dot` is driven by nav.js subscribing to `ledger:health`; veil waits up to 1600 ms for `ledger:readiness` (dispatched by today.js, Task 6).

- [ ] **Step 2: Add veil numeral styling to `frontend/css/base.css` (append at end):**

```css
/* ── Veil numeral beat (M1) ── */
.veil {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: var(--sp-3);
}
.veil__numeral {
  font-family: var(--f-mono);
  font-size: var(--fs-800);
  font-weight: 300;
  color: var(--ink-1);
  letter-spacing: var(--track-display);
  line-height: 1;
}
.veil__text {
  font-family: var(--f-mono);
  font-size: var(--fs-050);
  letter-spacing: var(--track-caps);
  color: var(--ink-3);
}
```

(If `.veil` already sets display/centering in base.css, only append the two child rules.)

- [ ] **Step 3: Verify**

Reload the app. Expected: veil shows a large numeral counting from 0 to readiness %, then dissolves; footer status reads `ENGINE RUNNING`; console clean. `evaluate_script`: `document.querySelector("#sr-live") ? "sr-live present" : "missing"` → `sr-live present`.

- [ ] **Step 4: Commit**

```bash
git add frontend/js/app.js frontend/css/base.css
git -c user.name="hrkartiktomar-netizen" -c user.email="hrkartiktomar-netizen@users.noreply.github.com" commit -m "fix(frontend): single health poller, announce hub, veil numeral beat, drop footer bindings"
```

---

### Task 5: router.js — delegated navigation, replay-on-register, routechange event (B1, B4, B5)

**Files:**
- Modify: `frontend/js/router.js:55-58, 76-89, 97-102`

- [ ] **Step 1: Dispatch events from `showView` — replace lines 55-58:**

```js
    // Fire event + callbacks
    var prev = currentRoute;
    currentRoute = routeId;
    document.dispatchEvent(new CustomEvent("ledger:routechange", { detail: { route: routeId, prev: prev } }));
    onRouteChange.forEach(function (fn) { fn(routeId, prev); });
    if (window.LedgerApp && window.LedgerApp.announce) {
      window.LedgerApp.announce(routeId === "today" ? "Today" : routeId.charAt(0).toUpperCase() + routeId.slice(1) + " view");
    }
```

- [ ] **Step 2: Replace `init` (lines 76-89) with delegated activation:**

```js
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
```

- [ ] **Step 3: Replay-on-register (B1) — replace the exposed object (lines 97-102):**

```js
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
```

- [ ] **Step 4: Verify deep links (B1)**

In browser-use navigate to `http://127.0.0.1:8000/#pyq` (cold load). Expected: PYQ view active, papers grid rendered (or the authored empty state) — previously blank. Repeat for `#tracker` and `#results`. Console clean.

- [ ] **Step 5: Verify footer + CTA delegation**

On `#today`, click a footer index row → route changes. `evaluate_script`:

```js
document.querySelectorAll(".footer__row").length + " rows, click handlers delegated"
```

Also confirm the next-action CTA (rendered later by today.js) navigates — covered fully in Task 6 verification.

- [ ] **Step 6: Commit**

```bash
git add frontend/js/router.js
git -c user.name="hrkartiktomar-netizen" -c user.email="hrkartiktomar-netizen@users.noreply.github.com" commit -m "fix(frontend): delegated [data-view] activation, route replay, routechange event"
```

---

### Task 6: today.js — activation-driven init, N-cell flap roll, plan thresholds, readiness event (B2, B3+M2, B4, G11)

**Files:**
- Modify: `frontend/js/today.js:23-49, 80-106, 466-526, 528-580`

B10 (burst double loop) is resolved by construction in Task 13's data-true rewrite — do not patch it here.

- [ ] **Step 1: Replace `animateCounter` (lines 23-49) with the N-cell split-flap roll (B3 + M2):**

```js
  /* ────── A01: Split-Flap Counter · N cells + railway roll (B3, M2) ────── */
  function animateCounter(container, targetValue) {
    var digitsWrap = container.querySelector(".splitflap__digits");
    if (!digitsWrap) return;

    var pct = Math.max(0, Math.min(100, Math.round(targetValue)));
    var target = String(pct);

    digitsWrap.innerHTML = target.split("").map(function () {
      return '<div class="splitflap__digit"><span class="splitflap__char">0</span></div>';
    }).join("");

    var digits = Array.prototype.slice.call(digitsWrap.querySelectorAll(".splitflap__char"));

    if (typeof gsap === "undefined" || (window.LedgerMotion && window.LedgerMotion.isReduced)) {
      digits.forEach(function (d, i) { d.textContent = target[i]; });
      return;
    }

    // Each flap cycles intermediate digits before settling (railway board)
    digits.forEach(function (d, i) {
      var finalVal = parseInt(target[i], 10);
      var rolls = 8 + i * 4 + finalVal;
      var obj = { step: 0 };
      gsap.to(obj, {
        step: rolls,
        duration: 1.1 + i * 0.18,
        delay: 0.25 + i * 0.08,
        ease: "power2.out",
        onUpdate: function () { d.textContent = Math.floor(obj.step) % 10; },
        onComplete: function () { d.textContent = finalVal; },
      });
    });
  }
```

- [ ] **Step 2: Fix priority thresholds in `renderNextAction` (G11) — replace lines 84-87:**

```js
    var priority = "low";                                  // ≤5 · emerald
    if (data.priority_score >= 10) priority = "critical";  // 10 · red
    else if (data.priority_score >= 8) priority = "high";  // 8-9 · amber
    else if (data.priority_score >= 6) priority = "medium"; // 6-7 · brass
```

- [ ] **Step 3: Dispatch readiness event in `loadData` — after the counter block (lines 493-494), add:**

```js
      document.dispatchEvent(new CustomEvent("ledger:readiness", { detail: { percent: readinessPercent } }));
```

- [ ] **Step 4: Replace the meta-line update (lines 496-501) to preserve the verb-pill markup added in Task 14:**

```js
      var confEl = qs("#confidence-val");
      if (confEl && readinessData) {
        confEl.textContent = (readinessData.confidence || "—").toUpperCase();
      }
```

- [ ] **Step 5: Activation-driven init (B2) — replace lines 567-579 with:**

```js
  function remeasureBurst() {
    var canvas = qs(".burst__canvas canvas");
    if (!canvas || !canvas.parentElement) return;
    var rect = canvas.parentElement.getBoundingClientRect();
    if (rect.width > 0 && canvas.dataset.sized !== "true") {
      // Was sized 0×0 against a display:none view — force re-render next data pass
      canvas.dataset.sized = "";
    }
  }

  // Route-aware init: replay guarantees first-paint coverage (B1/B2)
  if (window.LedgerRouter) {
    window.LedgerRouter.onRoute(function (route) {
      if (route !== "today") return;
      if (!initialized) init();
      else remeasureBurst();
    });
  }
```

And in `renderBurst` (line 407 area), after the canvas context check, mark sizing:

```js
    canvas.dataset.sized = "true";
```

- [ ] **Step 6: Add `.splitflap__digits` flex rule to `frontend/css/today.css` (append):**

```css
.splitflap__digits { display: flex; }
```

- [ ] **Step 7: Verify**

Cold-load `http://127.0.0.1:8000`. Expected: split-flap shows up to 3 cells and rolls digits before settling on readiness %; console clean. Cold-load `#exam` then click back via nav → Today re-renders (burst canvas not 0×0 — `evaluate_script`: `document.querySelector(".burst__canvas canvas").width > 0`). Next-action CTA click navigates to its target view.

- [ ] **Step 8: Commit**

```bash
git add frontend/js/today.js frontend/css/today.css
git -c user.name="hrkartiktomar-netizen" -c user.email="hrkartiktomar-netizen@users.noreply.github.com" commit -m "fix(frontend): activation-driven Today, N-cell flap roll, plan priority thresholds"
```

---

### Task 7: exam.js — submit-only start, re-entry guard, timer announcements (B6, G12)

**Files:**
- Modify: `frontend/js/exam.js:22-38, 109-136`

- [ ] **Step 1: Replace `initSetup` (lines 22-38) with submit-only binding:**

```js
  /* ────── Setup ────── */
  function initSetup() {
    var form = qs(".exam-setup__form");
    if (!form) return;

    // Submit only — the start button is type="submit" inside the form.
    // (Click + submit was double-bound; a double start orphaned the timer — B6.)
    form.addEventListener("submit", function (e) {
      e.preventDefault();
      startExam();
    });
  }
```

- [ ] **Step 2: Add re-entry guard at the top of `startExam` (line 40-41):**

```js
  async function startExam() {
    if (!API) return;
    if (examState) return; // re-entry guard (B6)
```

- [ ] **Step 3: Timer warnings to aria-live (G12) — inside `startTimer`, replace the `if (timerEl) {` block (lines 121-128) with:**

```js
        if (timerEl) {
          timerEl.textContent = display;
          if (remaining <= 300) {
            timerEl.dataset.warning = "";
          } else {
            delete timerEl.dataset.warning;
          }
        }

        if (remaining === 600 || remaining === 300 || remaining === 60) {
          if (window.LedgerApp && window.LedgerApp.announce) {
            window.LedgerApp.announce(Math.round(remaining / 60) + " minute" + (remaining === 60 ? "" : "s") + " remaining");
          }
        }
```

- [ ] **Step 4: Verify**

Start an exam from the UI (setup → BEGIN EXAMINATION once). Expected: exactly one timer interval (`evaluate_script` — start exam, then `document.querySelectorAll(".exam-live.is-active").length` → `1`), no duplicate toast; submit via palette works as before. Timer announcements fire at 10/5/1 min (verify by reading code paths if waiting is impractical — acceptable evidence: breakpoints not hit by other paths).

- [ ] **Step 5: Commit**

```bash
git add frontend/js/exam.js
git -c user.name="hrkartiktomar-netizen" -c user.email="hrkartiktomar-netizen@users.noreply.github.com" commit -m "fix(frontend): exam submit-only start with re-entry guard, timer aria-live"
```

---

### Task 8: motion.css — no-js fallback, dead code out (B7, B11)

**Files:**
- Modify: `frontend/css/motion.css:19-37, 49-53, 56-72`

`.wipe-enter` stays (consumed by Task 11).

- [ ] **Step 1: Delete the `.reveal-stagger` block (lines 19-37) and the `@keyframes seal-ambient` block (lines 49-53).**

- [ ] **Step 2: Replace the reduced-motion block (lines 56-72) with the complete authored-still set:**

```css
/* ── No-JS fallback — content visible without scripts (B7) ── */
html.no-js .reveal,
html.no-js .reveal-stagger > * {
  opacity: 1 !important;
  transform: none !important;
}

/* ── Reduced motion — authored end states ── */
@media (prefers-reduced-motion: reduce) {
  .reveal,
  .reveal-stagger > * {
    opacity: 1 !important;
    transform: none !important;
    transition: none !important;
  }

  .wipe-enter { clip-path: none !important; transition: none !important; }

  .ticker__track { animation: none !important; }
  .cold-open__scroll-hint { animation: none !important; opacity: 0.5; }
  .loading-state__ring { animation: none !important; }
  .exam-bar__timer[data-warning] { animation: none !important; }
  .ledger-thread,
  .scroll-progress,
  .cold-open::before { animation: none !important; }

  /* All GSAP-driven animation checks LedgerMotion.isReduced */
}
```

(The `html.no-js .reveal-stagger > *` selector is harmless once the class is gone; kept so future staggered blocks inherit the fallback.)

- [ ] **Step 3: Verify**

`evaluate_script` in browser: `getComputedStyle(document.querySelector(".reveal")).opacity` while JS runs → `"0"` (JS reveals it on scroll). Then load with scripts blocked (browser-use: `evaluate_script` → set `document.documentElement.classList.add("no-js")`; reload is not required): re-check opacity → `"1"`.

- [ ] **Step 4: Commit**

```bash
git add frontend/css/motion.css
git -c user.name="hrkartiktomar-netizen" -c user.email="hrkartiktomar-netizen@users.noreply.github.com" commit -m "fix(frontend): no-js/reduced reveal fallbacks, remove dead motion CSS"
```

---

## Phase P3 — Seal rebuild + lazy Three.js

### Task 9: seal.js rewrite (C3, G7, G8, G9)

**Files:**
- Rewrite: `frontend/js/seal.js` (231 lines → full replacement below)
- Reference: `frontend/index.html` (three.min.js already removed in Task 1)

Same visuals; fixed lifecycle: arc geometry rebuilt only when displayed percent moves ≥0.5 pts, rAF gated by IntersectionObserver + route, context-loss handled, full dispose, DPR tiers, promise-guarded lazy three.js load.

- [ ] **Step 1: Replace `frontend/js/seal.js` entirely with:**

```js
/* THE LEDGER — Three.js Brass Seal · Readiness Gauge (A04)
   PBR brass material. 24-tick ring. Ring arc = readiness %.
   Docs-faithful lifecycle: lazy three.js load, arc geometry rebuilt only on
   ≥0.5 pt change (dispose-before-assign), rAF gated by IntersectionObserver
   + route, webglcontextlost/restored handled, full traverse-dispose destroy.
   Reduced quality / no WebGL → SVG poster (static beauty frame). */
(function () {
  "use strict";

  var scene, camera, renderer, sealGroup, ringMesh;
  var containerEl = null;
  var isWebGL = false;
  var readinessPercent = 0;
  var targetPercent = 0;
  var lastBuiltPercent = -1;
  var animFrame = null;
  var running = false;
  var inViewport = true;
  var routeActive = true;
  var contextLost = false;
  var mouseX = 0, mouseY = 0;
  var io = null;

  function qs(sel) { return document.querySelector(sel); }

  function hasWebGL() {
    try {
      var c = document.createElement("canvas");
      return !!(c.getContext("webgl2") || c.getContext("webgl"));
    } catch (e) { return false; }
  }

  /* ────── Lazy three.js (G7) — promise-guarded single load ────── */
  var threePromise = null;
  function loadThree() {
    if (window.THREE) return Promise.resolve(window.THREE);
    if (!threePromise) {
      threePromise = new Promise(function (resolve, reject) {
        var s = document.createElement("script");
        s.src = "/vendor/three.min.js";
        s.onload = function () { resolve(window.THREE); };
        s.onerror = function () { threePromise = null; reject(new Error("three.js failed to load")); };
        document.head.appendChild(s);
      });
    }
    return threePromise;
  }

  function quality() {
    return window.LedgerMotion ? window.LedgerMotion.quality : (document.body.dataset.quality || "full");
  }

  function isReduced() {
    return window.LedgerMotion ? window.LedgerMotion.isReduced : quality() === "reduced";
  }

  /* ────── Init ────── */
  function init(container, percent) {
    containerEl = container;
    readinessPercent = 0;
    targetPercent = percent || 0;
    lastBuiltPercent = -1;

    subscribeRoute();

    if (isReduced() || !hasWebGL()) {
      renderSVGFallback(container, targetPercent);
      return;
    }

    // SVG poster holds the frame until three.js arrives (G7 race guard)
    renderSVGFallback(container, targetPercent);

    loadThree().then(function () {
      if (!containerEl || isReduced()) return;
      buildWebGL(containerEl);
    }).catch(function () {
      // poster already showing — nothing to do
    });
  }

  function buildWebGL(container) {
    if (typeof THREE === "undefined") return;

    // Remove poster before mounting canvas
    container.innerHTML = "";

    isWebGL = true;
    var q = quality();
    var dpr = q === "full" ? Math.min(window.devicePixelRatio || 1, 2) : 1.25;

    var w = container.clientWidth || 300;
    var h = container.clientHeight || 300;

    scene = new THREE.Scene();
    camera = new THREE.PerspectiveCamera(35, w / h, 0.1, 100);
    camera.position.set(0, 0, 4.5);

    renderer = new THREE.WebGLRenderer({ alpha: true, antialias: true });
    renderer.setSize(w, h);
    renderer.setPixelRatio(dpr);
    renderer.toneMapping = THREE.ACESFilmicToneMapping;
    renderer.toneMappingExposure = 1.1;
    container.appendChild(renderer.domElement);

    // Context loss (docs: preventDefault, pause; restore → rebuild)
    renderer.domElement.addEventListener("webglcontextlost", function (e) {
      e.preventDefault();
      contextLost = true;
      stopLoop();
    });
    renderer.domElement.addEventListener("webglcontextrestored", function () {
      contextLost = false;
      lastBuiltPercent = -1; // force arc rebuild
      startLoop();
    });

    var keyLight = new THREE.DirectionalLight(0xE3C07C, 1.2);
    keyLight.position.set(2, 3, 4);
    scene.add(keyLight);

    var fillLight = new THREE.DirectionalLight(0x3A4A46, 0.4);
    fillLight.position.set(-3, -1, 2);
    scene.add(fillLight);

    var rimLight = new THREE.PointLight(0x37C092, 0.6, 10);
    rimLight.position.set(0, -2, 3);
    scene.add(rimLight);

    scene.add(new THREE.AmbientLight(0x2A2520, 0.3));

    sealGroup = new THREE.Group();

    var brassMat = new THREE.MeshStandardMaterial({ color: 0xC79E4F, metalness: 0.85, roughness: 0.25 });

    sealGroup.add(new THREE.Mesh(new THREE.TorusGeometry(1.4, 0.04, 16, 64), brassMat));

    var progressMat = new THREE.MeshStandardMaterial({
      color: 0x37C092, metalness: 0.7, roughness: 0.3,
      emissive: 0x37C092, emissiveIntensity: 0.15,
    });
    ringMesh = new THREE.Mesh(new THREE.TorusGeometry(1.2, 0.06, 16, 64, 0.001), progressMat);
    ringMesh.rotation.z = -Math.PI / 2;
    sealGroup.add(ringMesh);

    for (var i = 0; i < 24; i++) {
      var angle = (i / 24) * Math.PI * 2;
      var tick = new THREE.Mesh(new THREE.BoxGeometry(0.015, 0.08, 0.01), brassMat);
      tick.position.x = Math.cos(angle) * 1.4;
      tick.position.y = Math.sin(angle) * 1.4;
      tick.rotation.z = angle + Math.PI / 2;
      sealGroup.add(tick);
    }

    var disc = new THREE.Mesh(
      new THREE.CircleGeometry(0.5, 32),
      new THREE.MeshStandardMaterial({ color: 0xC79E4F, metalness: 0.9, roughness: 0.2, side: THREE.DoubleSide })
    );
    sealGroup.add(disc);

    scene.add(sealGroup);

    container.addEventListener("mousemove", onMouseMove, { passive: true });

    observeViewport(container);
    startLoop();
  }

  function onMouseMove(e) {
    if (!containerEl) return;
    var rect = containerEl.getBoundingClientRect();
    mouseX = ((e.clientX - rect.left) / rect.width - 0.5) * 2;
    mouseY = ((e.clientY - rect.top) / rect.height - 0.5) * 2;
  }

  /* ────── Loop gating (G8): viewport + route + context ────── */
  function shouldRun() {
    return isWebGL && running === false && inViewport && routeActive && !contextLost && !isReduced();
  }

  function startLoop() {
    if (!shouldRun() || animFrame !== null) return;
    running = true;
    animate();
  }

  function stopLoop() {
    running = false;
    if (animFrame) { cancelAnimationFrame(animFrame); animFrame = null; }
  }

  function observeViewport(container) {
    if (typeof IntersectionObserver === "undefined") return;
    if (io) io.disconnect();
    io = new IntersectionObserver(function (entries) {
      inViewport = entries[0].isIntersecting;
      if (inViewport) startLoop(); else stopLoop();
    }, { threshold: 0.05 });
    io.observe(container);
  }

  function subscribeRoute() {
    if (subscribeRoute.done) return;
    subscribeRoute.done = true;
    document.addEventListener("ledger:routechange", function (e) {
      routeActive = e.detail.route === "today";
      if (routeActive) startLoop(); else stopLoop();
    });
    document.addEventListener("ledger:qualitychange", function () {
      // Tier change → rebuild with the appropriate renderer
      if (!containerEl) return;
      var pct = targetPercent;
      destroy();
      init(containerEl, pct);
    });
  }

  /* ────── Frame ────── */
  function animate() {
    if (!running) return;
    animFrame = requestAnimationFrame(animate);

    readinessPercent += (targetPercent - readinessPercent) * 0.02;

    // Rebuild arc geometry only when displayed percent moves ≥0.5 pts (C3)
    if (ringMesh && Math.abs(readinessPercent - lastBuiltPercent) >= 0.5) {
      lastBuiltPercent = readinessPercent;
      var progress = Math.max(0.001, Math.min(1, readinessPercent / 100));
      var next = new THREE.TorusGeometry(1.2, 0.06, 16, 64, Math.PI * 2 * progress);
      ringMesh.geometry.dispose();
      ringMesh.geometry = next;
    }

    if (sealGroup) {
      sealGroup.rotation.y += (mouseX * 0.3 - sealGroup.rotation.y) * 0.05;
      sealGroup.rotation.x += (-mouseY * 0.15 - sealGroup.rotation.x) * 0.05;
    }

    if (renderer && scene && camera) renderer.render(scene, camera);
  }

  function updateReadiness(percent) {
    targetPercent = percent;
  }

  function resize(container) {
    if (!renderer || !camera) return;
    var w = container.clientWidth;
    var h = container.clientHeight;
    if (!w || !h) return;
    camera.aspect = w / h;
    camera.updateProjectionMatrix();
    renderer.setSize(w, h);
  }

  function destroy() {
    stopLoop();
    if (io) { io.disconnect(); io = null; }
    if (containerEl) containerEl.removeEventListener("mousemove", onMouseMove);
    if (scene) {
      scene.traverse(function (obj) {
        if (obj.geometry) obj.geometry.dispose();
        if (obj.material) {
          if (Array.isArray(obj.material)) obj.material.forEach(function (m) { m.dispose(); });
          else obj.material.dispose();
        }
      });
    }
    if (renderer) {
      renderer.dispose();
      if (renderer.domElement && renderer.domElement.parentNode) renderer.domElement.remove();
    }
    scene = camera = renderer = sealGroup = ringMesh = null;
    isWebGL = false;
    contextLost = false;
    lastBuiltPercent = -1;
    mouseX = 0; mouseY = 0;
  }

  /* ────── SVG poster / static beauty frame ────── */
  function renderSVGFallback(container, percent) {
    var pct = Math.round(percent || 0);
    var circumference = 283;
    var offset = circumference - (circumference * pct / 100);

    container.innerHTML =
      '<svg viewBox="0 0 100 100" width="100%" height="100%">' +
        '<circle cx="50" cy="50" r="45" fill="none" stroke="rgba(239,234,224,0.08)" stroke-width="1.5" />' +
        '<circle cx="50" cy="50" r="38" fill="none" stroke="#C79E4F" stroke-width="2" opacity="0.3" />' +
        '<circle cx="50" cy="50" r="38" fill="none" stroke="#37C092" stroke-width="2.5" ' +
          'stroke-dasharray="' + circumference + '" stroke-dashoffset="' + offset + '" ' +
          'stroke-linecap="round" transform="rotate(-90 50 50)" />' +
        Array.from({ length: 24 }, function (_, i) {
          var angle = (i / 24) * Math.PI * 2 - Math.PI / 2;
          return '<line x1="' + (50 + Math.cos(angle) * 43) + '" y1="' + (50 + Math.sin(angle) * 43) +
            '" x2="' + (50 + Math.cos(angle) * 45) + '" y2="' + (50 + Math.sin(angle) * 45) +
            '" stroke="#C79E4F" stroke-width="0.5" opacity="0.5" />';
        }).join("") +
        '<circle cx="50" cy="50" r="16" fill="#C79E4F" opacity="0.15" />' +
        '<circle cx="50" cy="50" r="16" fill="none" stroke="#C79E4F" stroke-width="0.8" />' +
        '<text x="50" y="52" text-anchor="middle" font-family="var(--f-mono)" font-size="10" fill="#EFEAE0" font-weight="300">' + pct + '</text>' +
      '</svg>';
  }

  /* ────── Public API (unchanged contract) ────── */
  window.LedgerSeal = {
    init: init,
    updateReadiness: updateReadiness,
    resize: resize,
    destroy: destroy,
    isWebGL: function () { return isWebGL; },
  };
})();
```

- [ ] **Step 2: Verify WebGL path**

Server running, cold-load `http://127.0.0.1:8000`. In browser-use: `list_network_requests` — expect `/vendor/three.min.js` requested ONCE, and only after first paint. Console clean. Seal renders with brass ring.

- [ ] **Step 3: Verify gating**

`evaluate_script`:

```js
(function(){ var c = document.querySelector(".cold-open__seal canvas"); return c ? "canvas live" : "no canvas"; })()
```

Expected: `canvas live`. Toggle quality to `reduced` via nav toggle → same script expected: `no canvas` (SVG poster), console shows `[motion] quality full -> reduced`. Toggle back → canvas returns. Navigate to `#pyq` and back to `#today` — seal still alive, no console errors.

- [ ] **Step 4: Verify no geometry churn (C3)**

While on Today with WebGL, run `evaluate_script`:

```js
window.__geoProbe = 0; var orig = THREE.TorusGeometry; THREE.TorusGeometry = function(){ window.__geoProbe++; return new orig(...arguments); }; "probe armed"
```

Wait ~3 s (static readiness), then:

```js
var n = window.__geoProbe; window.__geoProbe = 0; THREE.TorusGeometry && (n <= 2 ? "churn fixed (" + n + ")" : "CHURN: " + n)
```

Expected: `churn fixed (0|1|2)` — previously dozens per second.

- [ ] **Step 5: Commit**

```bash
git add frontend/js/seal.js
git -c user.name="hrkartiktomar-netizen" -c user.email="hrkartiktomar-netizen@users.noreply.github.com" commit -m "feat(frontend): seal rebuild — lazy three, gated loop, arc-on-change, context-loss, dispose"
```

---

## Phase P4 — Plan-fidelity spectacle + Today motion maximum

### Task 10: Flip route transitions (S4.1, G1)

**Files:**
- Modify: `frontend/js/router.js:16-61`

- [ ] **Step 1: Replace `showView` with the Flip-aware version:**

```js
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
      if (routeId === "exam") window.LedgerSmooth.stop();
      else window.LedgerSmooth.start();
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
```

- [ ] **Step 2: Verify**

Navigate today → pyq → results at quality `full`: panels crossfade (screenshot mid-transition optional). Toggle to `reduced`: transitions are instant. Start an exam (live console active) and navigate via palette submit flow — no Flip errors in console.

- [ ] **Step 3: Commit**

```bash
git add frontend/js/router.js
git -c user.name="hrkartiktomar-netizen" -c user.email="hrkartiktomar-netizen@users.noreply.github.com" commit -m "feat(frontend): GSAP Flip route transitions with reduced/exam guards"
```

---

### Task 11: Paper wipe into the hall (S4.2, G2)

**Files:**
- Modify: `frontend/js/router.js` (subscribe after `init`)
- Consumer: `frontend/css/motion.css` `.wipe-enter` (already present)

- [ ] **Step 1: Add the wipe subscriber at the bottom of router.js, after the `LedgerRouter` exposure:**

```js
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
```

- [ ] **Step 2: Verify**

At `full`: navigate to `#exam` — the hall wipes down into view (screenshot two frames if possible). At `lite`/`reduced`: instant swap. Console clean in all tiers.

- [ ] **Step 3: Commit**

```bash
git add frontend/js/router.js
git -c user.name="hrkartiktomar-netizen" -c user.email="hrkartiktomar-netizen@users.noreply.github.com" commit -m "feat(frontend): paper wipe threshold into the exam hall"
```

---

### Task 12: Journey layer — seal handoff, scene crossfades, instrument nav, stamp slam (S4.1–S4.4, M7, M15, M16)

**Files:**
- Create: `frontend/js/journey.js`
- Modify: `frontend/index.html` (progress rule div, finale ghost, script tag)
- Modify: `frontend/css/tokens.css` (register six scene custom properties for GSAP color interpolation)
- Modify: `frontend/css/motion.css` (progress rule + finale ghost styles)
- Modify: `frontend/css/nav.css` (hide-on-scroll transform)
- Modify: `frontend/js/today.js` (lawData hoist, stamp handler → API.lawComplete, quiet-beat field fixes)

- [ ] **Step 1: Register the six scene custom properties in `frontend/css/tokens.css` — append immediately after the existing `@property --counter-val` line (line 14):**

```css
@property --canvas { syntax: "<color>"; inherits: true; initial-value: #0C0E10; }
@property --ink-1  { syntax: "<color>"; inherits: true; initial-value: #EFEAE0; }
@property --ink-2  { syntax: "<color>"; inherits: true; initial-value: #B4ACA0; }
@property --ink-3  { syntax: "<color>"; inherits: true; initial-value: #857E72; }
@property --signal { syntax: "<color>"; inherits: true; initial-value: #37C092; }
@property --metal  { syntax: "<color>"; inherits: true; initial-value: #C79E4F; }
```

GSAP can only interpolate custom properties that are registered with a concrete syntax; without this the crossfades snap instead of blending. `inherits: true` is required so every child re-resolves during the blend.

- [ ] **Step 2: Add the journey markup to `frontend/index.html`:**

After the `</header>` that closes `#topnav` (line 52), before `<main id="main">`:

```html
  <!-- M7 · scroll progress hairline (driven by journey.js) -->
  <div class="scroll-progress" aria-hidden="true"></div>
```

Inside the finale section, directly after `<div class="finale__seal-return" id="seal-finale" aria-hidden="true"></div>` (line 165):

```html
        <div class="finale__ghost" aria-hidden="true">SEALED</div>
```

In the script block, directly after `<script src="/js/today.js" defer></script>` (line 354):

```html
  <script src="/js/journey.js" defer></script>
```

- [ ] **Step 3: Add journey styles to `frontend/css/motion.css` (append):**

```css
/* ── M7 · Scroll progress hairline — journey.js drives scaleY ── */
.scroll-progress {
  position: fixed;
  top: 0;
  right: 0;
  width: 1px;
  height: 100vh;
  background: var(--metal);
  transform: scaleY(0);
  transform-origin: top;
  z-index: var(--z-sticky);
  pointer-events: none;
}

/* ── M15 · Finale stamp ghost wordmark ── */
.finale { position: relative; overflow: hidden; }
.finale__ghost {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  font-family: var(--f-display);
  font-weight: 300;
  font-size: var(--fs-900);
  letter-spacing: var(--track-caps);
  color: var(--metal);
  opacity: 0;
  white-space: nowrap;
  pointer-events: none;
  z-index: 0;
}
.finale__seal-return, .finale__text, .finale__stamp-btn { position: relative; z-index: 1; }
```

- [ ] **Step 4: Add the hide-on-scroll rule to `frontend/css/nav.css` (append):**

```css
/* Journey layer hides the instrument bar on scroll-down (animated tiers only) */
.ledger-nav { transition: transform var(--t-med) var(--e-out); }
.ledger-nav[data-hidden] { transform: translateY(-100%); }
```

If `.ledger-nav` already declares a `transition`, merge `transform var(--t-med) var(--e-out)` into that existing declaration instead of adding a second one.

- [ ] **Step 5: Create `frontend/js/journey.js`:**

```js
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
```

- [ ] **Step 6: Wire the stamp to the backend in `frontend/js/today.js`.**

Hoist the law payload — replace the module variable block (lines 8-11):

```js
  var API = null;
  var dashData = null;
  var readinessData = null;
  var lawData = null;
  var initialized = false;
```

In `loadData`, change line 484 from `var lawData = ...` to:

```js
      lawData = results[4].status === "fulfilled" ? results[4].value : null;
```

Fix the quiet-beat field names to match `LawRevisionModel` (backend/models.py:478 — the payload has `daily_text` / `line_start` / `line_end`, not `text` / `lines_count`). In `renderQuietBeat` replace:

```js
    var text = lawData.text || lawData.content || "Today's law revision content will appear here when available.";
```

with:

```js
    var text = lawData.daily_text || lawData.text || lawData.content || "Today's law revision content will appear here when available.";
```

and replace the eyebrow assignment with:

```js
      var dayLines = (lawData.line_end != null && lawData.line_start != null)
        ? (lawData.line_end - lawData.line_start + 1)
        : (lawData.lines_count || 0);
      eyebrow.textContent = "§ DAILY ACT REVISION · DAY " + (lawData.day_index || 1) + " · " + dayLines + " LINES";
```

Replace the stamp handler (lines 537-552) — drop the gsap pulse (journey.js owns the slam), seal the day server-side:

```js
    // Stamp CTA — seals today's Act slice server-side; slam visuals live in journey.js
    var stampBtn = qs(".finale__stamp-btn");
    if (stampBtn) {
      stampBtn.addEventListener("click", async function () {
        if (window.LedgerApp && window.LedgerApp.toast) {
          window.LedgerApp.toast("Day stamped. The ledger records.", "success");
        }
        if (window.LedgerApp && window.LedgerApp.announce) {
          window.LedgerApp.announce("Day sealed");
        }
        if (!API || !lawData) return;
        var dayLines = (lawData.line_end != null && lawData.line_start != null)
          ? Math.max(30, Math.min(180, lawData.line_end - lawData.line_start + 1))
          : 80;
        try {
          await API.lawComplete(lawData.day_index || 1, dayLines);
        } catch (err) {
          if (window.LedgerApp && window.LedgerApp.toast) {
            window.LedgerApp.toast("Seal failed: " + err.message, "error");
          }
        }
      });
    }
```

Backend contract (backend/main.py:966): `lines_per_day` is validated `ge=30, le=180`, default 80 — hence the clamp.

- [ ] **Step 7: Verify**

Server up, quality `full`, Today view:
- Scroll slowly: the hero seal shrinks and tracks toward the nav seal; the nav seal fades in over the same range; scrolling back up reverses it.
- Wheel down hides the nav; wheel up reveals it. Start an exam (`#exam`, begin) and wheel down — the nav must NOT hide.
- Scrolling into `.quiet-beat` (hall-paper), `.proof` (signal-ledger), `.finale` (brass-close) shows a 0.6s color blend, not a snap.
- The right-edge hairline grows with page scroll.
- Click STAMP THE DAY: "SEALED" slams down behind the text, toast appears, `evaluate_script`: `document.getElementById("sr-live").textContent` returns `"Day sealed"`, and Network shows `POST /api/law/daily-revision/complete-day`.
- Quiet-beat eyebrow shows a nonzero line count and the Act text (not the placeholder sentence).
- Toggle quality to `reduced`: none of the six journey effects attach (nav always visible, no hairline growth), but stamping still POSTs.
- Console clean throughout.

- [ ] **Step 8: Commit**

```bash
git add frontend/js/journey.js frontend/index.html frontend/css/tokens.css frontend/css/motion.css frontend/css/nav.css frontend/js/today.js
git -c user.name="hrkartiktomar-netizen" -c user.email="hrkartiktomar-netizen@users.noreply.github.com" commit -m "feat(frontend): journey layer — seal handoff, scene crossfades, instrument nav, stamp slam"
```

---

### Task 13: Burst — data-true particle field, no persistent loop (S4.6, B10, G6, M12)

**Files:**
- Modify: `frontend/js/today.js` (`renderBurst` lines 400-463 and the `remeasureBurst` stub from Task 6)

The current burst spawns random particles inside a self-rescheduling `requestAnimationFrame(draw)` that can be started multiple times by the IntersectionObserver (B10) and renders nothing from real data (G6). Replace it with a deterministic field built from `recent_attempts`, drawn only when ScrollTrigger reports scroll change — no persistent rAF.

- [ ] **Step 1: Replace `renderBurst` (lines 400-463) and its helpers entirely with:**

```js
  /* ────── A15: Burst — Data-true particle field ────── */
  var burstParticles = null;
  var burstSize = { w: 0, h: 0 };
  var burstCounted = false;

  function sizeBurstCanvas(canvas) {
    var dpr = Math.min(window.devicePixelRatio || 1, 2);
    var rect = canvas.parentElement.getBoundingClientRect();
    canvas.width = Math.max(1, Math.round(rect.width * dpr));
    canvas.height = Math.max(1, Math.round(rect.height * dpr));
    canvas.style.width = rect.width + "px";
    canvas.style.height = rect.height + "px";
    var ctx = canvas.getContext("2d");
    if (ctx) ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    burstSize = { w: rect.width, h: rect.height };
    return ctx;
  }

  function buildBurstParticles(data, w, h) {
    var attempts = (data && data.recent_attempts) || [];
    var cap = (window.LedgerMotion && window.LedgerMotion.isFull) ? 220 : 60;
    var maxTime = 1;
    attempts.forEach(function (a) {
      if ((a.time_spent || 0) > maxTime) maxTime = a.time_spent;
    });
    return attempts.slice(0, cap).map(function (a, i) {
      var jitter = ((i * 37) % 40) - 20;
      return {
        x: ((a.time_spent || 30) / maxTime) * w,
        y: (a.is_correct ? 0.3 : 0.7) * h + jitter,
        r: 1.5 + ((i * 13) % 10) / 4,
        alpha: 0.35 + ((i * 29) % 45) / 100,
        color: a.is_correct ? "#37C092" : "#FF4D5E",
        phase: ((i * 53) % 360) * Math.PI / 180,
      };
    });
  }

  function drawBurst(ctx, particles, drift) {
    if (!ctx || !particles) return;
    ctx.clearRect(0, 0, burstSize.w, burstSize.h);
    particles.forEach(function (p) {
      var dx = Math.cos(drift + p.phase) * 6;
      var dy = Math.sin(drift + p.phase) * 4;
      ctx.beginPath();
      ctx.arc(p.x + dx, p.y + dy, p.r, 0, Math.PI * 2);
      ctx.fillStyle = p.color;
      ctx.globalAlpha = p.alpha;
      ctx.fill();
    });
    ctx.globalAlpha = 1;
  }

  function remeasureBurst() {
    var canvas = qs(".burst__canvas canvas");
    if (!canvas || !canvas.parentElement) return;
    var rect = canvas.parentElement.getBoundingClientRect();
    if (rect.width <= 0) return; // still display:none — wait for next activation
    var ctx = sizeBurstCanvas(canvas);
    burstParticles = buildBurstParticles(dashData, burstSize.w, burstSize.h);
    canvas.dataset.sized = "true";
    drawBurst(ctx, burstParticles, 0);
  }

  function renderBurst(data) {
    var canvas = qs(".burst__canvas canvas");
    var countEl = qs(".burst__count");
    var totalAttempts = data.total_attempts || 0;
    if (!canvas || !canvas.parentElement) return;

    var ctx = sizeBurstCanvas(canvas);
    if (!ctx) return;

    burstParticles = buildBurstParticles(data, burstSize.w, burstSize.h);
    canvas.dataset.sized = "true";
    drawBurst(ctx, burstParticles, 0);

    var reduced = window.LedgerMotion && window.LedgerMotion.isReduced;
    if (reduced || typeof gsap === "undefined" || typeof ScrollTrigger === "undefined") {
      if (countEl) countEl.textContent = totalAttempts;
      return;
    }

    // Drift is scroll-scrub driven: one draw per scroll update, no rAF loop
    ScrollTrigger.create({
      trigger: ".burst",
      start: "top bottom",
      end: "bottom top",
      onUpdate: function (self) {
        drawBurst(ctx, burstParticles, self.progress * Math.PI * 2);
      },
    });

    // M12: count the ledger entries once when the band enters
    ScrollTrigger.create({
      trigger: ".burst",
      start: "top 80%",
      onEnter: function () {
        if (burstCounted || !countEl) return;
        burstCounted = true;
        var obj = { val: 0 };
        gsap.to(obj, {
          val: totalAttempts,
          duration: 1.4,
          ease: "power2.out",
          onUpdate: function () { countEl.textContent = Math.floor(obj.val); },
          onComplete: function () { countEl.textContent = totalAttempts; },
        });
      },
    });

    var resizeTimer = null;
    window.addEventListener("resize", function () {
      clearTimeout(resizeTimer);
      resizeTimer = setTimeout(remeasureBurst, 150);
    });
  }
```

- [ ] **Step 2: Replace the Task 6 `remeasureBurst` stub** (the 9-line version added in Task 6 Step 5, inside the route-aware block) **with a delegation, since the real implementation now lives above `init`:**

```js
  // Route-aware init: replay guarantees first-paint coverage (B1/B2)
  if (window.LedgerRouter) {
    window.LedgerRouter.onRoute(function (route) {
      if (route !== "today") return;
      if (!initialized) init();
      else remeasureBurst();
    });
  }
```

(Keep only this block; delete the old stub function — the full `remeasureBurst` from Step 1 supersedes it.)

- [ ] **Step 3: Verify**

- `evaluate_script`: `document.querySelectorAll("canvas").length` unchanged, and in the Network/console: no continuous rAF churn — DevTools Performance recording over 5s idle shows zero canvas paint work while the burst is off-screen.
- Scroll to the burst: particles drift subtly with scroll only; correct answers sit in the upper band (emerald), wrong in the lower (red).
- `evaluate_script`: `performance.now(); document.querySelector(".burst__count").textContent` shows the total_attempts value counting up on first entry, then settling.
- Quality `lite`: particle count ≤ 60 (`evaluate_script`: count via a temporary console probe is not needed — instead verify visually thinner field). Quality `reduced`: static field, count shows instantly.
- Navigate Today → Exam → Today (B2 regression): burst canvas still renders (`evaluate_script`: `document.querySelector(".burst__canvas canvas").width > 0`).
- Console clean.

- [ ] **Step 4: Commit**

```bash
git add frontend/js/today.js
git -c user.name="hrkartiktomar-netizen" -c user.email="hrkartiktomar-netizen@users.noreply.github.com" commit -m "feat(frontend): data-true burst field, scrub-driven drift, one-shot count-up"
```

---

### Task 14: Cold-open completeness — projection line, verb pill, ambient field (S4.7, G10, M3, M4)

**Files:**
- Modify: `frontend/index.html` (`.cold-open__meta` → `.cold-open__sub`)
- Modify: `frontend/js/today.js` (meta block final form in `loadData`)
- Modify: `frontend/css/today.css` (verb pill, ambient field, sub-line styling)
- Modify: `frontend/css/motion.css` (reduced-motion rule for the pill)

Readiness payload fields (backend/main.py:920): `readiness_percentage`, `final_score_estimate`, `days_to_exam`, `weak_areas_count`, `confidence`. Render-nothing rule: any missing field renders nothing — never "undefined" or fabricated numbers.

- [ ] **Step 1: Replace the cold-open meta line in `frontend/index.html` (lines 62-67 block). Replace:**

```html
          <div class="cold-open__meta">PERCENT · MEASURED NIGHTLY · CONFIDENCE —</div>
```

with:

```html
          <div class="cold-open__sub">
            <span class="verb-pill" aria-hidden="true"><span>MEASURED</span><span>SEALED</span><span>STAMPED</span><span>MEASURED</span></span>
            <span class="cold-open__meta-rest">PERCENT · CONFIDENCE <span id="confidence-val">—</span><span id="cold-open-projected"></span></span>
          </div>
```

The fourth duplicated word makes the rotator loop seamless (the 100% keyframe lands on the same text as 0%).

- [ ] **Step 2: Replace the meta update block in `loadData`** (the `#confidence-val` block written in Task 6 Step 4) **with the final form:**

```js
      // Meta line — render nothing for missing fields
      var confEl = qs("#confidence-val");
      if (confEl && readinessData && readinessData.confidence != null) {
        confEl.textContent = String(readinessData.confidence).toUpperCase();
      }
      var projEl = qs("#cold-open-projected");
      if (projEl && readinessData && readinessData.final_score_estimate != null) {
        projEl.textContent = " · PROJECTED " + Math.round(readinessData.final_score_estimate) + "/130";
        if (readinessData.days_to_exam != null) {
          projEl.textContent += " · " + readinessData.days_to_exam + " DAYS TO THE HALL";
        }
      }
```

`/130` is the target score the frontend requests via `API.readiness(130, 28)` (api.js:35) — keep the two in sync if the target ever changes.

- [ ] **Step 3: Add styles to `frontend/css/today.css` (append):**

```css
/* Cold-open sub-line: verb pill + projection readout */
.cold-open__sub {
  display: flex;
  align-items: baseline;
  gap: var(--sp-2);
  font-family: var(--f-mono);
  font-size: var(--fs-100);
  letter-spacing: var(--track-caps);
  color: var(--ink-3);
}
.cold-open__meta-rest { white-space: nowrap; }

/* M3 · Verb pill rotator — pure CSS, three ledger verbs */
.verb-pill {
  display: inline-flex;
  flex-direction: column;
  height: 1em;
  overflow: hidden;
  color: var(--metal);
}
.verb-pill > span {
  display: block;
  height: 1em;
  line-height: 1;
  animation: verb-rotator 6s var(--e-inout) infinite;
}
@keyframes verb-rotator {
  0%, 28%   { transform: translateY(0); }
  33%, 61%  { transform: translateY(-1em); }
  66%, 94%  { transform: translateY(-2em); }
  100%      { transform: translateY(-3em); }
}

/* M4 · Ambient emerald field behind the cold open (full tier only) */
body[data-quality="full"] .cold-open { position: relative; }
body[data-quality="full"] .cold-open::before {
  content: "";
  position: absolute;
  inset: -20%;
  background:
    radial-gradient(600px 420px at var(--light-x) var(--light-y), rgba(55, 192, 146, 0.07), transparent 70%),
    radial-gradient(500px 380px at 70% 65%, rgba(199, 158, 79, 0.05), transparent 70%);
  animation: cold-field-drift 26s var(--e-inout) infinite alternate;
  pointer-events: none;
  z-index: 0;
}
@keyframes cold-field-drift {
  from { transform: translate3d(-2%, -1%, 0) scale(1); }
  to   { transform: translate3d(2%, 1.5%, 0) scale(1.04); }
}
body[data-quality="full"] .cold-open__content,
body[data-quality="full"] .cold-open__seal,
body[data-quality="full"] .cold-open__scroll-hint { position: relative; z-index: 1; }
```

- [ ] **Step 4: Add the reduced-motion kill for the pill inside the existing `@media (prefers-reduced-motion: reduce)` block in `frontend/css/motion.css`:**

```css
  .verb-pill > span { animation: none !important; }
```

(The M4 field is already excluded via its `body[data-quality="full"]` gate and the Task 8 `.cold-open::before` rule.)

- [ ] **Step 5: Verify**

- Cold-load Today: sub-line reads `MEASURED PERCENT · CONFIDENCE HIGH · PROJECTED 112/130 · 28 DAYS TO THE HALL` (values from the live payload; pill rotates MEASURED → SEALED → STAMPED every ~2s).
- Kill the backend, cold-load: no "undefined" anywhere — the confidence span stays `—` and the projection span stays empty.
- Quality `lite`/`reduced`: no ambient field behind the hero; pill static at MEASURED under reduced.
- Console clean.

- [ ] **Step 6: Commit**

```bash
git add frontend/index.html frontend/js/today.js frontend/css/today.css frontend/css/motion.css
git -c user.name="hrkartiktomar-netizen" -c user.email="hrkartiktomar-netizen@users.noreply.github.com" commit -m "feat(frontend): cold-open projection line, verb pill, ambient field"
```

---

### Task 15: Motion batch A — ghost→solid reveals, brass thread, chapter markers (M5, M6, M8, C4)

**Files:**
- Modify: `frontend/js/today.js` (delete `initPremise`, add registered reveal + chapter markers)
- Modify: `frontend/index.html` (brass thread element)
- Modify: `frontend/css/today.css` (thread + chapter-marker styles)

- [ ] **Step 1: Delete the old `initPremise` function (lines 51-77) and its call inside `init()` (line 534, `initPremise();`).**

It splits words without ever reverting them (C4 — SplitText leaks across quality cycles), and its reveals are not tier-aware. The registered replacement below supersedes it.

- [ ] **Step 2: Add the chapter markers and registered reveal to `frontend/js/today.js`. Insert before `/* ────── Data Loading ────── */` (line 465):**

```js
  /* ────── M8 · Chapter markers — the route is numbered ────── */
  var CHAPTERS = [
    { sel: ".premise",       num: "§01", name: "THE PREMISE" },
    { sel: ".next-action",   num: "§02", name: "NEXT ACTION" },
    { sel: ".constellation", num: "§03", name: "CONSTELLATION" },
    { sel: ".statute-path",  num: "§04", name: "THE STATUTE PATH" },
    { sel: ".proof",         num: "§05", name: "THE PROOF" },
    { sel: ".burst",         num: "§06", name: "THE BURST" },
    { sel: ".finale",        num: "§07", name: "THE SEAL" },
  ];

  function injectChapterMarkers() {
    CHAPTERS.forEach(function (ch) {
      var section = qs(ch.sel);
      if (!section || qs(".chapter-marker", section)) return;
      var marker = el("div", "chapter-marker reveal",
        '<span class="chapter-marker__rule"></span>' +
        '<span class="chapter-marker__name">' + ch.num + ' · ' + ch.name + '</span>' +
        '<span class="chapter-marker__rule"></span>'
      );
      section.insertBefore(marker, section.firstChild);
    });
  }

  /* ────── M5 · Ghost→solid word reveals (registered, revertible — C4) ────── */
  function attachWordReveals(m) {
    if (!m.conditions.animated) return;
    if (typeof gsap === "undefined" || typeof SplitText === "undefined" || typeof ScrollTrigger === "undefined") return;

    var targets = qsa(".premise__line").concat(qsa(".chapter-marker__name"));
    if (!targets.length) return;

    var splits = [];
    var tweens = [];
    var stagger = m.conditions.isLite ? 0.12 : 0.06;

    targets.forEach(function (line) {
      var split = new SplitText(line, { type: "words", wordsClass: "word" });
      splits.push(split);
      var isDim = line.classList.contains("premise__line--dim");
      tweens.push(gsap.fromTo(split.words,
        { opacity: 0, y: 18, filter: "blur(6px)" },
        {
          opacity: isDim ? 0.5 : 1,
          y: 0,
          filter: "blur(0px)",
          duration: 0.6,
          stagger: stagger,
          ease: "power3.out",
          scrollTrigger: {
            trigger: line,
            start: "top 82%",
            toggleActions: "play none none reverse",
          },
        }
      ));
    });

    return function () {
      tweens.forEach(function (t) {
        if (t.scrollTrigger) t.scrollTrigger.kill();
        t.kill();
      });
      splits.forEach(function (s) { s.revert(); }); // restores original text nodes (C4)
    };
  }
```

- [ ] **Step 3: At the very bottom of the IIFE (after the route-aware block, before the closing `})();`), add module-level activation:**

```js
  // Structural markers exist before any motion attaches
  injectChapterMarkers();

  if (window.LedgerMotion && typeof window.LedgerMotion.register === "function") {
    window.LedgerMotion.register(attachWordReveals);
  }
```

today.js is deferred, so the DOM is parsed when this runs; `LedgerMotion.register` attaches immediately because smooth.js initialized first (script order), satisfying the replay guarantee from Task 2.

- [ ] **Step 4: Add the brass thread element to `frontend/index.html` — directly after the closing `</div>` of `.cold-open` (line 74), inside `#view-today`:**

```html
      <!-- M6 · Brass thread — the ledger's spine -->
      <div class="ledger-thread" aria-hidden="true"></div>
```

- [ ] **Step 5: Add styles to `frontend/css/today.css` (append):**

```css
#view-today { position: relative; }

/* M6 · Brass thread drifting along the route (full + lite tiers) */
body[data-quality="full"] .ledger-thread,
body[data-quality="lite"] .ledger-thread {
  position: absolute;
  top: 12vh;
  bottom: 12vh;
  left: clamp(12px, 3vw, 48px);
  width: 1px;
  background: linear-gradient(to bottom, transparent, var(--metal) 18%, var(--metal) 82%, transparent);
  opacity: 0.28;
  animation: thread-drift 14s var(--e-inout) infinite alternate;
  pointer-events: none;
}
@keyframes thread-drift {
  from { transform: translateY(-1.2%) scaleY(0.98); opacity: 0.2; }
  to   { transform: translateY(1.2%) scaleY(1.02); opacity: 0.34; }
}

/* M8 · Chapter markers */
.chapter-marker {
  display: flex;
  align-items: center;
  gap: var(--sp-3);
  max-width: var(--w-container);
  margin: 0 auto;
  padding-top: var(--sp-6);
}
.chapter-marker__rule {
  flex: 1;
  height: 1px;
  background: var(--rule-strong);
  transform: scaleX(0);
  transform-origin: left;
  transition: transform var(--t-scene) var(--e-instrument);
}
.chapter-marker__rule:last-child { transform-origin: right; }
.chapter-marker__name {
  font-family: var(--f-mono);
  font-size: var(--fs-100);
  letter-spacing: var(--track-caps);
  color: var(--ink-3);
  white-space: nowrap;
}
.chapter-marker.is-visible .chapter-marker__rule { transform: scaleX(1); }
```

The `reveal` class on each marker means the existing `.reveal` ScrollTrigger loop in `init()` adds `is-visible`, drawing both rules.

- [ ] **Step 6: Verify**

- Scroll Today top→bottom at `full`: premise words and every chapter-marker name resolve from blurred ghost to solid (staggered); marker rules draw outward on entry; scrolling back up reverses the word reveals.
- The brass thread is visible at the left edge, drifting slowly; absent under `reduced` (quality toggle).
- Quality cycle full→lite→full three times, then `evaluate_script`: premise line word count returns to the original (no nested `.word` spans): `document.querySelectorAll(".premise__line .word").length` is 0 or stable, never growing per cycle; DOM text of `.premise__line` equals its original sentence.
- Console clean.

- [ ] **Step 7: Commit**

```bash
git add frontend/js/today.js frontend/index.html frontend/css/today.css
git -c user.name="hrkartiktomar-netizen" -c user.email="hrkartiktomar-netizen@users.noreply.github.com" commit -m "feat(frontend): registered word reveals, brass thread, numbered chapter markers"
```

---

### Task 16: Motion batch B — pointer tilt, deterministic constellation, pinned statute path, ticker flash (M9, M10, M11, M13, S4.5)

**Files:**
- Modify: `frontend/js/today.js` (`renderConstellation`, `initStatutePath`, `renderTicker`, route-aware block, module-level register)
- Modify: `frontend/css/today.css` (constellation hover, ticker hover-pause)

- [ ] **Step 1: M10 — make the constellation deterministic in `renderConstellation` (lines 109-187).**

Replace the node layout (lines 117-129):

```js
    // Arrange topics in a force-directed-like layout
    var nodes = stats.map(function (t, i) {
      var angle = (i / stats.length) * Math.PI * 2;
      var radius = 140 + Math.random() * 60;
      return {
```

with:

```js
    // Deterministic ring layout — same data, same sky, every render
    var nodes = stats.map(function (t, i) {
      var angle = (i / stats.length) * Math.PI * 2;
      var radius = 150 + (i % 3) * 30;
      return {
```

Replace the sparse random connections (lines 131-143):

```js
    // Draw connection lines
    nodes.forEach(function (a, i) {
      nodes.forEach(function (b, j) {
        if (j <= i) return;
        if (Math.random() > 0.3) return; // Sparse connections
        var line = document.createElementNS("http://www.w3.org/2000/svg", "line");
        line.setAttribute("x1", a.x); line.setAttribute("y1", a.y);
        line.setAttribute("x2", b.x); line.setAttribute("y2", b.y);
        line.setAttribute("stroke", "var(--rule)");
        line.setAttribute("stroke-width", "0.5");
        svg.appendChild(line);
      });
    });
```

with ring edges only:

```js
    // Ring edges: each topic bound to its neighbour
    nodes.forEach(function (a, i) {
      var b = nodes[(i + 1) % nodes.length];
      var line = document.createElementNS("http://www.w3.org/2000/svg", "line");
      line.setAttribute("x1", a.x); line.setAttribute("y1", a.y);
      line.setAttribute("x2", b.x); line.setAttribute("y2", b.y);
      line.setAttribute("stroke", "var(--rule)");
      line.setAttribute("stroke-width", "0.5");
      svg.appendChild(line);
    });
```

Extend the GSAP entrance block (lines 174-186): after the existing `gsap.from(svg.querySelectorAll("line"), ...)` call, add the pulse:

```js
      // Breathing pulse while the constellation is on screen
      if (!(window.LedgerMotion && window.LedgerMotion.isReduced)) {
        gsap.to(svg.querySelectorAll("circle"), {
          opacity: 0.95,
          duration: 1.6,
          stagger: { each: 0.12, repeat: -1, yoyo: true },
          ease: "sine.inOut",
          scrollTrigger: {
            trigger: svg,
            start: "top 60%",
            toggleActions: "play pause resume pause",
          },
        });
      }
```

- [ ] **Step 2: M10 hover glow — add to `frontend/css/today.css` (append):**

```css
.constellation__svg g:hover circle {
  filter: drop-shadow(0 0 6px rgba(55, 192, 146, 0.8));
  opacity: 1 !important;
}
```

- [ ] **Step 3: M11 + S4.5 — pin and state-change choreography in `initStatutePath` (lines 241-292).**

Add a state tracker before the `ScrollTrigger.create` call (line 264):

```js
    var lastStateIdx = -1;
    var canPin = window.LedgerMotion && !window.LedgerMotion.isReduced &&
      window.matchMedia("(min-width: 641px)").matches;
```

Replace `ScrollTrigger.create({` config opening (lines 264-268) so it builds conditionally:

```js
    var cfg = {
      trigger: section,
      start: "top top",
      end: "bottom bottom",
      scrub: 0.8,
```

Inside the `onUpdate` handler, before the panel loop, insert the state-change block:

```js
        if (stateIdx !== lastStateIdx) {
          lastStateIdx = stateIdx;
          if (typeof gsap !== "undefined" && !(window.LedgerMotion && window.LedgerMotion.isReduced)) {
            if (ringNum) {
              gsap.fromTo(ringNum, { opacity: 0.2 }, { opacity: 1, duration: 0.3, ease: "power2.out", overwrite: "auto" });
            }
            var activePanel = panelEls[stateIdx];
            if (activePanel) {
              gsap.fromTo(activePanel.children,
                { opacity: 0, y: 14 },
                { opacity: 1, y: 0, duration: 0.4, stagger: 0.07, ease: "power3.out", overwrite: "auto" }
              );
            }
          }
        }
```

And close the config with the conditional pin (replacing the plain `});` that ends the create call):

```js
    };
    if (canPin) {
      cfg.pin = qs(".statute-path__pin");
      cfg.pinSpacing = false;
      cfg.anticipatePin = 1;
    }
    ScrollTrigger.create(cfg);
```

- [ ] **Step 4: M13 — ticker value flash in `renderTicker` (lines 190-225). After `track.innerHTML = html;` (line 214), insert:**

```js
    // M13 · flash the freshly printed values
    if (typeof gsap !== "undefined" && !(window.LedgerMotion && window.LedgerMotion.isReduced)) {
      gsap.fromTo(qsa(".ticker__value", track),
        { opacity: 0.3 },
        { opacity: 1, duration: 0.5, stagger: 0.04, ease: "power2.out", overwrite: "auto" }
      );
    }
```

And add the hover-pause rule to `frontend/css/today.css` (append):

```css
.ticker:hover .ticker__track,
.ticker__track[data-paused="true"] { animation-play-state: paused; }
```

- [ ] **Step 5: M9 — pointer tilt + magnetic CTA. Add this registration function next to `attachWordReveals` in `frontend/js/today.js`:**

```js
  /* ────── M9 · Pointer tilt + magnetic CTA (desktop · full tier) ────── */
  function attachPointerTilt(m) {
    if (!m.conditions.isDesktop || !m.conditions.isFull) return;
    if (typeof gsap === "undefined" || !gsap.quickTo) return;
    var card = qs(".next-action__card");
    var cta = qs(".next-action__cta");
    if (!card) return;

    gsap.set(card, { transformPerspective: 900 });
    var rx = gsap.quickTo(card, "rotationX", { duration: 0.4, ease: "power2.out" });
    var ry = gsap.quickTo(card, "rotationY", { duration: 0.4, ease: "power2.out" });
    var mx = cta ? gsap.quickTo(cta, "x", { duration: 0.3, ease: "power2.out" }) : null;
    var my = cta ? gsap.quickTo(cta, "y", { duration: 0.3, ease: "power2.out" }) : null;

    function onMove(e) {
      var rect = card.getBoundingClientRect();
      var px = (e.clientX - rect.left) / rect.width - 0.5;
      var py = (e.clientY - rect.top) / rect.height - 0.5;
      ry(px * 12);    // ±6°
      rx(-py * 12);
    }
    function onLeave() {
      rx(0); ry(0);
      if (mx) mx(0);
      if (my) my(0);
    }
    function onCtaMove(e) {
      if (!mx || !my || !cta) return;
      var rect = cta.getBoundingClientRect();
      mx((e.clientX - (rect.left + rect.width / 2)) * 0.25);
      my((e.clientY - (rect.top + rect.height / 2)) * 0.25);
    }

    card.addEventListener("mousemove", onMove);
    card.addEventListener("mouseleave", onLeave);
    if (cta) {
      cta.addEventListener("mousemove", onCtaMove);
      cta.addEventListener("mouseleave", onLeave);
    }

    return function () {
      card.removeEventListener("mousemove", onMove);
      card.removeEventListener("mouseleave", onLeave);
      if (cta) {
        cta.removeEventListener("mousemove", onCtaMove);
        cta.removeEventListener("mouseleave", onLeave);
      }
      gsap.set(card, { clearProps: "transform,transformPerspective" });
      if (cta) gsap.set(cta, { clearProps: "transform" });
    };
  }
```

Register it in the same bottom block as `attachWordReveals`:

```js
    window.LedgerMotion.register(attachPointerTilt);
```

- [ ] **Step 6: Final form of the route-aware block — replace the current version with (adds ScrollTrigger refresh so pins remeasure after view swaps):**

```js
  // Route-aware init: replay guarantees first-paint coverage (B1/B2)
  if (window.LedgerRouter) {
    window.LedgerRouter.onRoute(function (route) {
      if (route !== "today") return;
      if (!initialized) init();
      else {
        remeasureBurst();
        if (typeof ScrollTrigger !== "undefined") ScrollTrigger.refresh();
      }
    });
  }
```

- [ ] **Step 7: Verify**

- `full` + desktop: hover the next-action card — it tilts ≤6° toward the pointer and settles on leave; the CTA drifts magnetically (≤ ~12px). At `lite` or 390×844 viewport: no tilt.
- Constellation: reload twice — identical layout (screenshot diff or node coordinates via `evaluate_script`); hovering a node glows emerald; nodes breathe while on screen and freeze when scrolled away.
- Statute path: the ring+panel column pins while the five panels cycle with the scrub; ring numeral flashes on each state change; panel children stagger in.
- Ticker: values flash on load; hovering the tape pauses it (also via the PAUSE button).
- Console clean.

- [ ] **Step 8: Commit**

```bash
git add frontend/js/today.js frontend/css/today.css
git -c user.name="hrkartiktomar-netizen" -c user.email="hrkartiktomar-netizen@users.noreply.github.com" commit -m "feat(frontend): pointer tilt, deterministic constellation, pinned statute path, ticker flash"
```

---

### Task 17: Motion batch C — line-mask eyebrow reveal, quiet-beat drop cap, aria-live sweep (M14, G12)

**Files:**
- Modify: `frontend/index.html:143-145` (quiet-beat markup)
- Modify: `frontend/js/today.js` (renderQuietBeat selector; mask-reveal registration)
- Modify: `frontend/css/today.css` (mask, drop cap, settle)
- Modify: `frontend/css/motion.css` (reduced-motion guard)

- [ ] **Step 1: Mask markup in `frontend/index.html`. Replace:**

```html
      <div class="quiet-beat section" data-scene="hall-paper">
        <div class="quiet-beat__content">
          <div class="quiet-beat__eyebrow">§ DAILY ACT REVISION</div>
```

with:

```html
      <div class="quiet-beat section reveal" data-scene="hall-paper">
        <div class="quiet-beat__content">
          <div class="quiet-beat__eyebrow mask-reveal"><span class="mask-reveal__inner">§ DAILY ACT REVISION</span></div>
```

The added `reveal` class hooks the existing reveal loop in `init()` (today.js) — it adds `is-visible` when the section reaches "top 85%", which drives the settle keyframes in Step 4.

- [ ] **Step 2: Point the eyebrow write at the masked span in `frontend/js/today.js` — in `renderQuietBeat`, replace:**

```js
    var eyebrow = qs(".quiet-beat__eyebrow");
```

with:

```js
    var eyebrow = qs(".quiet-beat__eyebrow .mask-reveal__inner") || qs(".quiet-beat__eyebrow");
```

The Task 12 assignment (`eyebrow.textContent = "§ DAILY ACT REVISION · DAY …"`) is unchanged — it now writes into the inner span so the mask keeps clipping it.

- [ ] **Step 3: Add the M14 registration function to `frontend/js/today.js`, directly after `attachPointerTilt`:**

```js
  /* ────── M14 · Line-mask reveal (animated tiers) ────── */
  function attachMaskReveals(m) {
    if (!m.conditions.animated || typeof gsap === "undefined") return;
    var inners = qsa(".mask-reveal__inner");
    if (!inners.length) return;

    gsap.set(inners, { yPercent: 110 });
    var tweens = inners.map(function (inner) {
      return gsap.to(inner, {
        yPercent: 0,
        duration: 0.9,
        ease: "power3.out",
        scrollTrigger: {
          trigger: inner.parentElement,
          start: "top 85%",
          toggleActions: "play none none reverse",
        },
      });
    });

    return function () {
      tweens.forEach(function (t) {
        if (t.scrollTrigger) t.scrollTrigger.kill();
        t.kill();
      });
      gsap.set(inners, { clearProps: "transform" });
    };
  }
```

Register it in the bottom block beside `attachWordReveals` and `attachPointerTilt`:

```js
    window.LedgerMotion.register(attachMaskReveals);
```

`renderQuietBeat` only swaps `textContent` on re-render — the element and its ScrollTrigger survive every data reload.

- [ ] **Step 4: Add mask, drop-cap, and settle rules to `frontend/css/today.css` (append):**

```css
/* ── M14 · Line-mask reveal ── */
.mask-reveal { overflow: hidden; }
.mask-reveal__inner { display: inline-block; will-change: transform; }

/* ── Quiet beat · drop cap + settle ── */
.quiet-beat__text .ghost-word:first-child::first-letter {
  font-family: var(--f-display);
  font-weight: 300;
  font-size: 3.2em;
  line-height: 0.82;
  float: left;
  padding-right: 0.09em;
  color: var(--signal);
}
.quiet-beat.is-visible .quiet-beat__text { animation: quiet-settle 1.2s var(--e-out) both; }
@keyframes quiet-settle {
  from { opacity: 0.55; letter-spacing: 0.012em; }
  to   { opacity: 1;     letter-spacing: 0; }
}
```

The drop cap targets the first `.ghost-word` span because `renderQuietBeat` wraps every word; `::first-letter` on the container would not match through the span.

- [ ] **Step 5: Reduced-motion guard — add these two rules inside the existing `@media (prefers-reduced-motion: reduce)` block in `frontend/css/motion.css` (the block Task 8 created and Task 14 extended):**

```css
  .mask-reveal__inner { transform: none !important; }
  .quiet-beat.is-visible .quiet-beat__text { animation: none; }
```

- [ ] **Step 6: Verify — M14 visuals**

Server up. At `full` and `lite`: scroll into the quiet beat — the eyebrow rises out of its mask (yPercent 110→0, ~0.9s) and reverses when scrolling back above it. The first letter of the Act text renders as an emerald display-face drop cap; the text settles (opacity/letter-spacing) once when the section gains `is-visible`. At `reduced`: eyebrow fully visible with no transform, no settle animation. Console clean.

- [ ] **Step 7: Verify — G12 aria-live sweep (`#sr-live`)**

After each action below, run `evaluate_script`: `document.getElementById("sr-live").textContent`. All four must be non-empty and match:

1. Cold load → veil countdown completes → veil-dismissal announcement (Task 4).
2. Nav click to another view → route announcement (Task 5).
3. `#exam` → start a mock, let the server timer reach an announcement threshold (10/5/1 min) → timer announcement (Task 7).
4. Back on Today → STAMP THE DAY → `"Day sealed"` (Task 12).

- [ ] **Step 8: Commit**

```bash
git add frontend/index.html frontend/js/today.js frontend/css/today.css frontend/css/motion.css
git -c user.name="hrkartiktomar-netizen" -c user.email="hrkartiktomar-netizen@users.noreply.github.com" commit -m "feat(frontend): line-mask eyebrow reveal, quiet-beat drop cap, settle beat"
```

---

### Task 18: P5 polish — grain reduction, whisper-weight and accent audit (S5)

**Files:**
- Modify: `frontend/css/tokens.css:199, 231, 243, 257`

- [ ] **Step 1: Reduce film grain ~43% across all four scenes — grain should read as texture, never noise. Four edits in `frontend/css/tokens.css`:**

Root (`:root`, line 199) — replace:

```css
  --grain-opacity: 0.035;
  --light-x: 30%;
```

with:

```css
  --grain-opacity: 0.02;
  --light-x: 30%;
```

Hall-paper (line 231) — replace:

```css
  --plate: rgba(242, 238, 230, 0.92);  --scrim: rgba(230, 223, 210, 0.8);
  --grain-opacity: 0.03;
```

with:

```css
  --plate: rgba(242, 238, 230, 0.92);  --scrim: rgba(230, 223, 210, 0.8);
  --grain-opacity: 0.017;
```

Signal-ledger (line 243) — replace:

```css
  --plate: rgba(7, 9, 10, 0.88);  --grain-opacity: 0.04;
```

with:

```css
  --plate: rgba(7, 9, 10, 0.88);  --grain-opacity: 0.023;
```

Brass-close (line 257) — replace:

```css
  --plate: rgba(5, 4, 3, 0.88);  --grain-opacity: 0.05;
```

with:

```css
  --plate: rgba(5, 4, 3, 0.88);  --grain-opacity: 0.029;
```

- [ ] **Step 2: Whisper-weight and accent-discipline audit — screenshots at 1440×900, quality `full`: full Today scroll (cold open, premise, next action, ticker, statute path, proof, quiet beat, burst, finale), exam setup, exam results.**

Pass criteria (fix any violation before Step 3):

- Emerald `--signal` appears only on positive signal — correct answers, readiness/accuracy, sealed states. Never decorative fills.
- Brass `--metal` only on instrument/data chrome (rules, ticks, rings, hardware).
- Red `--danger` only on wrong answers, critical priority, cutoff failures.
- No body copy renders at weight 300; whisper weight appears only on display-size words.
- Grain at 200% zoom over flat canvas areas: perceptible texture, no speckle over text.

- [ ] **Step 3: Commit**

```bash
git add frontend/css/tokens.css
git -c user.name="hrkartiktomar-netizen" -c user.email="hrkartiktomar-netizen@users.noreply.github.com" commit -m "style(frontend): reduce film grain ~43% across scenes (S5 polish)"
```

If Step 2 forced class/token fixes, include those files in the same `git add` and mention them in the message.

---

### Task 19: P6 — final verification matrix and sign-off

**Files:** none (verification only; fixes committed per Step 3 if needed)

- [ ] **Step 1: Boot the server**

```bash
cd backend
venv/Scripts/python -m uvicorn main:app --port 8000
```

Wait for `Uvicorn running on http://127.0.0.1:8000`, then run the nine-row matrix with the browser-use MCP tools (`navigate_page`, `take_screenshot`, `list_console_messages`, `evaluate_script`).

- [ ] **Step 2: The matrix — every row must pass**

| # | Check | Pass criteria |
|---|-------|----------------|
| 1 | Desktop full scroll — `full` tier, 1440×900, cold load `http://127.0.0.1:8000` | All sixteen motion items alive in one scroll: M1 veil numeral, M2 flap roll, M3 cold-open meta, M4 ambient field, M5 ghost→solid words, M6 brass thread, M7 scene crossfades, M8 chapter markers, M9 card tilt, M10 constellation pulse, M11 statute pin, M12 burst count-up, M13 ticker flash, M14 mask reveal, M15 progress rule, M16 finale slam. Console clean. |
| 2 | Quality cycle | Toggle full→lite→reduced→full via the nav control; after each, `evaluate_script`: `localStorage.getItem("ledger-quality")` matches; reload persists it. `lite`: no tilt/ambient, staggers halved. `reduced`: authored stills, nav always visible, zero tweens. |
| 3 | Reduced emulation | `evaluate_script`: `localStorage.removeItem("ledger-quality")`; enable prefers-reduced-motion emulation; reload → `document.body.dataset.quality === "reduced"`. |
| 4 | Deep links | Cold-load `#exam`, `#pyq`, `#descriptive`, `#updates`, `#wrong` in turn — each view renders populated, no blank routes, no console errors; footer/nav return to Today works each time. |
| 5 | Exam end-to-end | Setup form → submit starts the exam (no answers reachable before start); answer 3 questions (localStorage answer keys update); palette states correct; timer ring animates; server-held announcements fire at thresholds; submit → results with per-paper cutoff gating; re-entry guard blocks a second active exam. |
| 6 | Seal fallback | `evaluate_script`: the SVG stamp fallback exists in the DOM (`!!document.querySelector("#seal-finale svg, .finale svg")` is true); with WebGL available the canvas seal renders. |
| 7 | Mobile 390×844 | Resize viewport; `evaluate_script`: `document.documentElement.scrollWidth <= window.innerWidth`; nav usable; no tilt; burst and constellation legible; all sections readable. |
| 8 | Console sweep | `list_console_messages` on every view visited and each quality tier: zero errors or warnings from app code. |
| 9 | `#sr-live` | Route changes, stamp, exam announcements, and veil dismissal all land in `#sr-live` (re-sweep of Task 17 Step 7 after the full run). |

- [ ] **Step 3: Fix loop and sign-off**

Any failed row: debug to the root cause (superpowers:systematic-debugging if non-obvious), fix, re-run that row plus any row the fix could affect, then commit exactly the touched files:

```bash
git add <exact fixed files>
git -c user.name="hrkartiktomar-netizen" -c user.email="hrkartiktomar-netizen@users.noreply.github.com" commit -m "fix(frontend): <row N finding>"
```

If all nine rows pass on the first run, no commit is needed — the Ledger docs-fidelity award pass is complete.
