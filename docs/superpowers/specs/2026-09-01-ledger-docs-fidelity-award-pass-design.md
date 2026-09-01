# The Ledger — Docs-Fidelity & Award-Grade Fix Pass

| Field | Value |
|---|---|
| Date | 2026-09-01 |
| Status | Approved (design); implementation gated on writing-plans |
| Scope | `frontend/**` only — zero backend edits |
| Sources of truth | ① `frontend/docs/{LIBRARIES_REFERENCE,DEEP_DIVE_RESEARCH,ULTRA_DEEP_DIVE}.md` (Context7 manuals, 2026-09-01) · ② Original rebuild plan (M0–M15, "The Ledger — Cinematic Frontend Rebuild") · ③ `design_research/analysis/*` (52-site corpus) · ④ Code audit + milestone gap-check (2026-09-01) |

## 1. Goals

1. **Docs compliance** — Lenis/GSAP/Three.js used exactly as the fetched manuals prescribe.
2. **Zero known functional bugs** — every audit finding resolved.
3. **Plan fidelity** — deliver the awwwards-grade moments the original plan promised but the rebuild skipped (Flip transitions, paper wipe, seal journey, scene crossfades, ST pin, data-true particles, cold-open completeness).
4. **Research polish** — apply the highest-leverage `design_research` rules without redesigning approved visuals.

## 2. Non-goals

- No backend changes; no new API endpoints (existing endpoints only; if a needed field is absent from a response, render nothing rather than faking data).
- No token/palette redesign; no changes to exam-shell behavior, layout, or the five-state palette semantics.
- No new views, no copy rewrites beyond §S5 margin personality.
- No bundler/build tooling — vanilla stack constraint stands.

## 3. Evidence base (condensed audit, file:line)

### Correct today (do not regress)
- Lenis driven by `gsap.ticker` with `time*1000`, `lagSmoothing(0)`, `lenis.on("scroll", ScrollTrigger.update)` — `js/smooth.js:97-109`. Docs' canonical integration.
- Constellation bound to `/api/topics/stats` (`js/today.js:507-509`), grain texture (`css/base.css:33-43`), results pass/fail gate (`js/views.js:355-363`), burst IntersectionObserver pause (`js/today.js:454-462`).

### Docs violations / correctness findings
- C1 `gsap.defaults({ ease: "cubic-bezier(0.16, 1, 0.3, 1)" })` — unparseable without CustomEase (`js/smooth.js:84-87`, token `css/tokens.css:130`).
- C2 Lenis `duration` passed but inert without `easing` in vendored 1.3.26 (`js/smooth.js:51-52`) — docs: `lerp` vs `duration+easing` are mutually exclusive.
- C3 Seal: progress torus geometry disposed + recreated **every frame** (`js/seal.js:150-151`); rAF loop never paused (runs while Today hidden); no `webglcontextlost/restored`; `destroy()` never called; `mousemove` listener leaks (`js/seal.js:132-136,138-193`).
- C4 SplitText never reverted (`js/today.js:58`); `gsap.context` unused anywhere.
- C5 `window.LedgerMedia` rewritten by matchMedia callback but consumers snapshot it at init (seal DPR `js/seal.js:38`, burst count `js/today.js:420`) — stale across breakpoints.
- C6 Reduced motion effectively dead: `index.html:26` hard-codes `data-quality="full"`, bypassing detect heuristics (`js/smooth.js:15-31`); only the split-flap counter checks `isReduced`.
- C7 Quality toggle writes the attribute but gates nothing (`js/nav.js:52-69`).

### Functional bugs
- B1 Deep links (`#pyq`, `#tracker`, …) never load on first paint: `router` fires `onRoute` before `views.js` registers its callback (`js/views.js:383-393`).
- B2 Today inits unconditionally (`js/today.js:575-579`); on non-today first routes the burst canvas is sized 0×0 against `display:none` and never re-sized.
- B3 Split-flap shows "10" at 100% — only two digit cells (`index.html:63-64`, `js/today.js:26,33-34`).
- B4 Next-action CTA gets `data-view` after the router's one-time binding pass → dead button (`js/today.js:103`, `js/router.js:80-85`).
- B5 Footer rows double-bound (`js/router.js:80-85` + `js/app.js:96-108`).
- B6 Exam start bound on both form submit and button click (`js/exam.js:26-37`); a double start orphans the timer interval.
- B7 `.reveal` base `opacity:0` with visibility JS-only → blank sections if JS/ScrollTrigger fails (`css/motion.css:7-10`, `js/today.js:557-562`).
- B8 Duplicate 30 s health polls; nav poll handle discarded (`js/nav.js:148`, `js/app.js:86`); clock interval never cleared (`js/nav.js:144`).
- B9 Nav dead code: ScrollTrigger gate on a raw scroll listener, unused `delta` (`js/nav.js:158-173`).
- B10 Burst IO callback can start a second rAF loop on consecutive `isIntersecting:true` (`js/today.js:455-458`).
- B11 Dead CSS: `@keyframes seal-ambient`, `.wipe-enter`, `.reveal-stagger` (`css/motion.css:20-53`) have no consumers.

### Plan gap-check (❌ missing / ⚠ deviated)
- G1 ❌ Flip route transitions (router comment claims them).
- G2 ❌ Exam entry paper wipe (orphaned `.wipe-enter`).
- G3 ❌ Seal journey: hero WebGL / nav static SVG / `#seal-finale` never rendered — three disconnected elements.
- G4 ⚠ Scene themes static CSS; the planned GSAP-animated custom-property crossfades never fire (`css/tokens.css:209-267`).
- G5 ⚠ Statute pin = CSS sticky; plan said ScrollTrigger pin.
- G6 ⚠ Burst particles random, not mapped from `question_attempts`; no scroll scrub.
- G7 ⚠ All libs `defer`, never lazy; `three.min.js` (365KB) loads on every view.
- G8 ⚠ Seal has no offscreen pause (burst does).
- G9 ⚠ DPR tiers only 2/1.25; reduced = SVG poster (plan: static beauty frame).
- G10 ⚠ Cold-open renders confidence but never `final_score_estimate/200` nor `days_to_exam`.
- G11 ⚠ Next-action border thresholds shifted vs plan (score 5 → brass, plan says emerald).
- G12 ❌ `#sr-live` aria-live region never populated.

## 4. Design

### S1 · Motion Authority (backbone)

`js/smooth.js` becomes the single motion gate exporting `LedgerMotion`:

- **Quality resolution:** manual override persisted (`localStorage ledger-quality`) → else `prefers-reduced-motion` → `reduced` → else hardware heuristic (`hardwareConcurrency ≤ 2 || deviceMemory ≤ 2` → `lite`) → else `full`. Removes the hard-coded `data-quality="full"` from `index.html`; JS sets the attribute before first motion init.
- **Reactive quality:** one `gsap.matchMedia` instance owned by `LedgerMotion`. `LedgerMotion.setQuality(q)` sets `body[data-quality]`, calls `mm.revert()` (automatic teardown of all condition-scoped animations — the docs' pattern, no manual kill lists), then re-runs a single `registerConditions(mm)` function that re-adds `isFull/isLite/isReduced` conditions based on the current quality. All consumers register their animations inside conditions via this function or by listening to `ledger:qualitychange`.
- **Event bus:** `document` CustomEvents `ledger:qualitychange {quality, prev}` and `ledger:routechange {route}`. Seal, burst, ticker, nav subscribe.
- **Expose** `LedgerMotion.quality`, `.isReduced`, `.isLite`, `.mm` so consumers read live state instead of snapshotting `window.LedgerMedia` (fixes C5).

### S2 · Docs-compliance fixes

- **Lenis:** remove `duration` (C2); keep `lerp: 0.1`, ticker drive, `lagSmoothing(0)`, scroll→`ScrollTrigger.update`. Add `data-lenis-prevent` on exam option list scroll area and any future modal scroll islands. Reduced quality → Lenis not instantiated (existing behavior, now reachable via C6 fix).
- **GSAP defaults:** map `--e-out` intent to native `power3.out` in `gsap.defaults`; keep per-tween overrides (C1).
- **Today animations inside matchMedia:** premise SplitText reveal, constellation draws, statute scrub, quiet-beat ghost words, `.reveal` triggers all created inside `mm.add` conditions: `full/lite` → animated; `reduced` → authored end states (elements shown, ring filled, words lit) with no tweens. SplitText instances `revert()`-ed on condition exit (C4).
- **Three.js seal (seal.js rewrite, same visuals):**
  - Progress arc: keep `TorusGeometry` rebuilds but only when displayed percent changes ≥0.5 pts (or on quality/resize); dispose old geometry before assigning new (kills C3 churn).
  - Loop: `IntersectionObserver` on container + `ledger:routechange` gate → pause when offscreen or Today hidden (G8). Reduced: render one static frame, no loop (G9, plan M12 "static beauty frame").
  - `webglcontextlost` → `preventDefault` + pause; `webglcontextrestored` → re-init scene; creation error → SVG poster fallback.
  - `destroy()`: traverse-dispose geometry/material/textures, `renderer.dispose()`, remove listeners, null refs; called on quality transitions away from WebGL tiers and on context-loss terminal failure (C3).
  - DPR: full `min(devicePixelRatio,2)` / lite `1.25` / reduced single-frame at `1` (G9).
- **Lazy Three.js (G7):** remove `<script src="/vendor/three.min.js" defer>` from `index.html`; inject dynamically when seal init runs (quality ≠ reduced AND WebGL available). Promise-guarded single load. GSAP stack stays `defer` (needed by first-paint motion).

### S3 · Functional bug fixes

- **B1:** router replays the current hash after all modules register (router exposes `LedgerRouter.replay()` called by `app.js` at end of DOMContentLoaded), or `views.js` registers synchronously at parse (script is deferred, order-safe). Replay approach chosen — no load-order coupling.
- **B2:** Today becomes activation-driven: `ledger:routechange(today)` → `Today.init()` once (sized against a visible view); on re-activation re-measure burst canvas. Unconditional `setTimeout(init,50)` removed.
- **B3:** split-flap renders N digit cells from the target string length (3 cells at 100), animation per cell.
- **B4/B5:** one delegated `[data-view]` click handler on `document` (router-owned); remove app.js footer binding and router's one-time pass. Fixes dead CTA + double navigate together.
- **B6:** exam start on `submit` only; button keeps `type="submit"`, click handler deleted; `startExam` guards re-entry (`if (state.active) return`).
- **B7:** `html` gets `no-js` class swapped by first inline script snippet; `.reveal` visible under `no-js` and `prefers-reduced-motion` CSS (already partially present — complete it).
- **B8:** single 30 s health poll in `app.js` (nav subscribes to its result event); clock interval cleared on pagehide.
- **B9:** delete dead scroll-gate code; replaced by Observer (§S4.8).
- **B10:** `animating` flag checked before starting a new loop (single loop invariant).
- **B11:** `.wipe-enter` repurposed by G2 fix; `seal-ambient` and `reveal-stagger` deleted unless consumed by S4/S5 work.

### S4 · Plan-fidelity spectacle

1. **Flip route transitions (G1):** on route change, `Flip.getState` of outgoing view shell → swap `is-active` → `Flip.from(state, {duration: var(--t-med), ease: power2.inOut, absolute: true, onEnter/onLeave fades})`. Skipped entirely under `reduced` (instant swap) and suppressed while an exam is active (hall discipline). `flipId` attributes on view panels.
2. **Paper wipe into the hall (G2):** entering exam view triggers clip-path wipe (dark→cream inset expansion via `.wipe-enter`, GSAP-driven), per plan M9 "ceremonial threshold"; lite/reduced → simple fade.
3. **Seal journey (G3):** one motif, three anchors. Scroll-scrubbed handoff via a ScrollTrigger scrub tween over the cold-open exit range (ScrollTrigger is already driven by Lenis): hero WebGL seal scales/settles toward the nav corner while the nav SVG mini (same artwork) fades in. Finale: `#seal-finale` renders the SVG twin at full size; "Stamp the day" runs the stamp slam (drop → rotate → press, `power4.in` + micro-rebound) and calls the existing daily-complete action. No WebGL element is DOM-transplanted.
4. **Scene crossfades (G4):** one ScrollTrigger per scene boundary animates body-level theme variables (`--canvas`, `--ink-1/2/3`, `--signal`, `--metal`) via `gsap.to(document.body, {"--canvas": ...})` as sections cross mid-viewport; `immediateRender:false`, revert on condition exit; reduced → instant attribute swap. Sections keep `data-scene` as the declarative source; a small resolver maps scene → variable targets.
5. **Statute path pin (G5):** desktop + full/lite → `ScrollTrigger.create({pin: true, pinSpacing: true, anticipatePin: 1, ...existing scrub config})`; mobile or reduced → keep CSS sticky fallback (matchMedia branch). `ScrollTrigger.refresh()` on route activation and fonts.ready (already present).
6. **Data-true particles (G6):** burst reads the same `recent_attempts` payload the proof scatter uses; particle x = time_spent (normalized), y = correctness band + jitter, color = topic token, count = attempts length, capped at 220 on `full` and 60 on `lite`. Scroll-scrubbed drift replaces perpetual rAF (scrub progress → positional interpolation); reduced → static composed frame. Counter overlay keeps `total_attempts`.
7. **Cold-open completeness (G10):** render `final_score_estimate / 200` and `days_to_exam` from the readiness response below the counter (guard: render nothing if fields absent). Priority thresholds restored to plan mapping (G11): 10→red, ≥8→amber, ≥6→brass, ≥5→emerald.
8. **Observer earns its place:** `Observer.create({type:"wheel,touch,scroll", onUp/onDown, tolerance})` drives direction-aware nav (compress on down, restore on up) replacing the dead handler (B9). Killed under reduced.
9. **aria-live (G12):** `#sr-live` polite announcements: readiness value on load, route changes, exam timer warnings (10/5/1 min), submit/score reveal, quality changes.

### S4+ · Today motion maximum (approved expansion, M1–M16)

User-approved addition: push the Today page to maximum motion density, tiered — `full` gets everything, `lite` gets reduced density (fewer particles/instances, no parallax/ambient), `reduced` gets authored stills. Every pattern is frame-evidenced in the corpus. Governance: **no new persistent rAF loops** — each item is ScrollTrigger-gated to its viewport, IO-gated, or a CSS animation; the particle scrub stays scroll-driven; `lite` halves stagger counts and drops pointer-driven items.

**Cold open**
- M1 Numeral preloader beat: veil shows readiness % counting up as a lone numeral, then dissolves (trevornoah "70" pattern).
- M2 Split-flap roll: digits physically cycle intermediate values before settling on readiness (railway flap).
- M3 Verb-pill rotator in cold-open meta: `MEASURED / SEALED / STAMPED` cycle (notion pill).
- M4 Ambient emerald light field drifting behind the seal — accent-as-light, `full` only (raycast).

**Chapter grammar**
- M5 Ghost→solid word reveals on premise lines + every chapter title (SplitText word stagger + blur-out, condition-scoped; pitch).
- M6 Line-flow brass hairline threading cold-open → premise → proof → finale (SVG dash-offset drift; mintlify).
- M7 Scroll-progress hairline rule (1px brass, Lenis-scroll-position driven, right edge).
- M8 § hairline section markers draw themselves in on entry (upgrades the static S5 marker).

**Per-section life**
- M9 Next-action card pointer-parallax tilt + magnetic CTA hover (desktop + `full` only; trevor/figma drift).
- M10 Constellation: edge draw-in stagger, readiness-linked node pulses, emerald hover glow (only within its viewport).
- M11 Statute ring numeral tick on state change + panel word stagger (railway spine).
- M12 Proof charts: sparkline stroke-draw, scatter pop stagger, count-up labels (coursera draw band).
- M13 Ticker: pause-on-hover + value tick-flash on update (warp/mercury).
- M14 Quiet beat: line-mask serif reveal + drop-cap settle (editorial-soft 400–700ms).
- M15 Finale: ghost `SEALED` wordmark rises behind the stamp slam.
- M16 Footer: index rows stagger-rise + watermark drift on scroll-in.

### S5 · Research polish (high-leverage only)

- **Hairline section markers:** "§ NN · NAME" mono eyebrow centered on a drawn 1px rule at Today chapter boundaries (synthesis PASS-7 #2).
- **Whisper audit:** display weights 300–400 on dark fields; luminance (ink ladder) carries emphasis — no bold-shout introduced; enforce ≤4 type sizes per viewport.
- **Accent discipline check:** brass ≤5% screen area; emerald as data/status/light only, brass never glows (existing token intent — verify in screenshots).
- **Grain:** tune `--grain-opacity` 0.035 → 0.02 default (plan value), keep per-scene steps proportionally.
- **Margins personality:** keep footer status poetry; sharpen exit line; no new gimmicks.

## 5. Protected contracts (absolute)

Every element `id`; all `/api` paths; exam state machine, timers, keyboard shortcuts, strict-mode submit lock, zen-mode; five-state palette semantics; timer ring untouched by GSAP; `EXAM_TEMPLATES` semantics; localStorage answer keys; confirm()/alert() flows; no backend edits.

## 6. Phasing

| Phase | Content | Depends on |
|---|---|---|
| P1 | S1 motion authority + S2 docs compliance (smooth.js, tokens.css, index.html, seal-less boot) | — |
| P2 | S3 functional bugs (router, views, today, exam, nav, app, motion.css) | P1 |
| P3 | Seal rebuild + lazy three.min.js (seal.js, index.html) | P1 |
| P4 | S4 spectacle items 1–9 + S4+ Today motion maximum M1–M16 (router Flip, wipe, seal journey, crossfades, pin, particles, cold-open, Observer, aria-live, M inventory) | P1–P3 |
| P5 | S5 polish | P4 |
| P6 | Verification matrix (§7) | P5 |

## 7. Verification

Server: `venv/Scripts/python -m uvicorn main:app --port 8000` from `backend/` (serves frontend). Browser-use matrix:

1. Desktop 1440×900 + 1280×800: full scroll of Today (cold-open → finale), verify seal journey, crossfades, pin, particles, ticker pause, and every M1–M16 item alive at `full` (veil numeral beat, flap roll, verb pill, word reveals, brass thread, progress rule, section markers, parallax card, constellation life, ring tick, chart draws, ticker flash, quiet-beat masks, SEALED ghost, footer stagger).
2. Quality toggle cycle full→lite→reduced→full: observe Lenis teardown, seal DPR/static frame, particle count, animation revert; persist across reload.
3. `prefers-reduced-motion: reduce` emulation: authored stills everywhere, no racing animations, Flip/wipe skipped.
4. Deep links `#pyq`, `#exam`, `#results` on cold load render their views.
5. Exam flow end-to-end: setup → wipe → live console (Lenis stopped, no ambient motion) → submit → results.
6. WebGL disabled / context-loss simulation → SVG poster fallback, no console errors.
7. Mobile 390×844 + 375×667: sticky fallback, no pin, thumb targets.
8. Console clean (no errors/warnings) across all of the above.
9. SR: `#sr-live` receives announcements (DOM inspection).

## 8. Risks & mitigations

| Risk | Mitigation |
|---|---|
| ST pin in display:none views mis-measures | pin branch only active when Today active; refresh on route activation |
| Flip needs measurable elements (display:none swap) | sequence: state → make incoming measurable (visibility hidden + block) → Flip.from; absolute:true |
| Crossfade of many CSS vars costs paint | animate only 5 core vars, single trigger per boundary, `scrub` not tween storms |
| Readiness API may lack `final_score_estimate`/`days_to_exam` | render-nothing guard; verify payload in P4 before wiring |
| Lazy three.min.js race with seal init | promise-guarded loader; SVG poster until loaded |
| Motion-max density causes jank at `full` | no new persistent rAF; every M item ST/IO-gated to its viewport; `lite` halves staggers and drops pointer/ambient items; verify smoothness in §7 item 1 |
| Git hazard (concurrent automations) | never pull/rebase; check `.git/index.lock`; commit only explicit paths |
