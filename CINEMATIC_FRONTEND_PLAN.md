# CINEMATIC_FRONTEND_PLAN.md — THE EXAMINATION ENGINE
> Living source of truth. Reread this file at the start of every work session and before every milestone (§37).
> Planning document only — no code has been changed by the creation of this file.

---

## 0. Document control

| Field | Value |
|---|---|
| Project | IFSCA Grade A Exam Engine — `D:\Exam_preparation` |
| Plan version | 2.0 (deepened per master-prompt Part VI schema) |
| Status | **planning** (direction approved-in-concept; implementation gated on M0→M11) |
| Approved creative territory | T-A "The Examination Engine" — instrument telemetry (§7) |
| Current milestone | M0 (this document) |
| Current focus | Deep-plan ratification; baseline evidence capture at M1 start |
| Next action | Begin M1: tokens.css + base.css with zero visual diff |
| Last updated | 2026-08-29 · Qoder agent · full-schema deepening after end-to-end frontend read |

---

## 1. Executive project truth

- **Product (VERIFIED):** A single-user exam war-room for IFSCA Grade A (and SEBI) aspirants that generates Gemini mocks grounded in the real OCR'd syllabus corpus, runs them in a TCS-iON-style shell, and returns verdicts, targeting, drills, amendment radar, and essay grading. Primary action: **Start Mock → perform → receive verdict → act on targeting**.
- **Audience (VERIFIED/INFERRED):** The owner-candidate; desktop Chrome/Edge on Windows; nightly 60–120 min sittings; exam-time pressure psychology; zero tolerance for distraction during attempts.
- **Required flows:** dashboard refresh; mock generate→instructions→attempt→submit→analysis; PYQ attempt→reveal→analytics; drills; wrong-answer replay; essay/descriptive grading; source search + citation; law revision + amendment tracking; updates feed.
- **Experience zones (§5 of master prompt):** `today` = Showcase; `resultPage` = Showcase payoff; `exam`, `pyq`, `review`, `essay`, `sources`, `lawSources`, `updates` = Task (with ceremonial thresholds); modals/overlays/system states = System.
- **Emotional aftertaste (decided):** *command-room calm before, hard focus during, verdict-grade release after.* Not fun. Not cozy. **Certified readiness.**
- **Constraints (VERIFIED):** vanilla HTML/CSS/JS, no bundler; FastAPI mounts only `/css` and `/js` (backend/main.py:2957-2959) plus `/app` — **all new assets must live under `frontend/css/**` or `frontend/js/**`; backend stays untouched**; Google Fonts OK (internet required by Gemini anyway); free-tier Gemini keys → dashboard/AI calls cost quota, so QA loads are budgeted.
- **Protected behavior (absolute):** every element `id`, every inline-`onclick` global, all `/api` paths, class hooks (`view/active`, `hidden`, `zen-mode`, `selected/current/answered/not-answered/marked/answered-marked`, `warning/critical`, `open`, `stagger-in`, `timer-ring-*`, `data-view/template/mode/cat/exam`), `EXAM_TEMPLATES` semantics, strict-mode submit lock, `injectTimerRing`, keyboard shortcuts (←/→, 1-5, A-E, M, S), `localStorage answer_q{n}`, confirm()/alert() flows, zen-mode chrome hiding, PH1_P1 palette grouping.
- **Definition of done:** §47 of the master prompt, audited against §26 of this file.

---

## 2. Cinematic creative decisions (all made autonomously per master prompt §46)

| ID | Decision | Status | Source | Impact |
|---|---|---|---|---|
| D1 | Concept = "The Examination Engine": an instrument that calibrates a candidate across the cut-off line | INFERRED | Code already computes `cutoff_pct`, "CLEARED/NOT CLEARED", aggregate gating — the cut-off is the product's real antagonist | Whole visual world |
| D2 | Signature motif = the 5-state **palette cell** + the **Threshold Line** (1px signal hairline with ticks) | INFERRED | qnum palette is the app's most domain-locked artifact (§8) | Brand mark, bullets, chips, progress, verdicts |
| D3 | Near-black base #08090A family, one emerald signal #00E5A0; violet demoted to *marked-for-review state only*; **no purple/indigo/pink aurora gradients anywhere** | INFERRED | Research verdict + §4.6 prohibition | Palette |
| D4 | Fonts: Archivo variable (wdth 62-125, wght 100-900) display; Inter body; JetBrains Mono data. Kinetic width-axis "lock" on titles | VERIFIED feasible | Google Fonts CSS API returns `font-weight:100 900; font-stretch:62% 125%` (checked 2026-08-29) | Typography + motion |
| D5 | GSAP (all plugins free, MIT-era license post-Webflow) as sole temporal layer; Three.js WebGL for the protagonist | VERIFIED | gsap.com/pricing; gsap 3.13 blog (checked 2026-08-29) | Motion stack |
| D6 | 3D protagonist = **The Readiness Core** (stacked subject plates + orbiting clock ring), Today hero band, live dashboard data | INFERRED | §27 default; product telemetry drives its state | S-3D-1 |
| D7 | Keep vanilla stack; vendored libs under `frontend/js/vendor/`; zero backend edits | VERIFIED constraint | Serving mounts | Architecture |
| D8 | Exam shell is **designed silence**: no ambient motion during attempts; timer ring stays functional-only (GSAP never touches it) | INFERRED | Timed performance is the core job | Motion hierarchy |
| D9 | Mobile = separate art direction: thumb rail tabs, bottom-sheet palette, simplified Core, one authored wow (verdict slam) | INFERRED | §29 | Mobile |
| D10 | Reduced motion = authored edit (static composed frames, instant states, 3D poster), never duration=0 hack | INFERRED | §30 | A11y |
| D11 | Code-native visuals only: SVG systems, procedural 3D, type; no stock photography, no fabricated logos/metrics; vendor libs are the only third-party assets (permissive licenses) | INFERRED | §15 asset rules | Asset manifest |
| D12 | Inline `style=` soup inside app.js renderers → classes, view-by-view during migration (IDs untouched) | INFERRED | Token governance | Migration |
| D13 | Baseline screenshot capture happens once at M1 (single page load ≈ few Gemini calls) to conserve free-tier quota; subsequent QA reuses running server prudently | INFERRED | Memory: 4,500 req/day across 9 keys; dashboard AI endpoints cost calls | QA economics |
| D14 | No scrollytelling pin inside Task views; one modest pin (≈140vh, 2 narrative states) on Today only; generation/result sequences are time-triggered, not scroll-trapped | INFERRED | §21 restraint + task-zone rule | Motion map |
| D15 | Git hazard protocol: concurrent arena automations mutate this repo — never pull/rebase; check `.git/index.lock`; commit only explicit frontend/ + plan files if asked | VERIFIED | Project memory (2026-08-28 incident) | Safety |

**UNKNOWN — USER INPUT REQUIRED:** none. No rights, credential, or architecture blockers exist.

---

## 3. Repository & current-product evidence

- **Framework:** none (static HTML/CSS/JS) served by FastAPI/uvicorn (`start.bat`, localhost:8000). No package.json, no tests, no lint for frontend.
- **Routing/layout:** single `index.html`; 8 tab-switched `<section class="view">`; sticky `app-top` + `tabs`; `zen-mode` body class hides chrome in-attempt.
- **Styling:** one 1702-line `app.css` — token-ish `:root` vars exist but ~60% of values are hard-coded in inline styles inside `app.js` renderers; glassmorphism panels; gradient-text brand; blink keyframe on critical timer (seizure review needed).
- **Fonts:** Google Fonts Archivo 700/900, Inter 400-700, JetBrains Mono 400/700/800 (preconnect present).
- **Existing motion:** `viewFadeIn`, `staggerReveal`, hover lifts, modal slide-in, data-stream overlay (scan-lines + gradient bar), timer-ring SVG injected by JS.
- **Existing data-viz (under-used gems):** readiness constellation SVG, scatter review matrix, chronology strip, score trend line, timer ring — all authored in JS, all visually weak today; these become the brand's graphic system (§8).
- **Diagnosis (evidence-anchored):** ① gradient-clipped wordmark (app.css:163-172) = generic AI-dashboard tell; ② identical `.panel` grid in all 8 views; ③ flat `#121212` backgrounds; ④ no signature per view; ⑤ readiness numeral/constellation/scatter wasted; ⑥ mobile = collapsed columns only; ⑦ reduced-motion is a blunt global kill (app.css:1429); ⑧ focus styles decent but inconsistent across chips/cells.
- **Baseline capture:** pending M1 (D13).

---

## 4. Keep / refine / recompose / replace map

| Surface / subsystem | Evidence | Decision | Reason | Risk | Milestone |
|---|---|---|---|---|---|
| View/tab architecture, IDs, API layer | app.js `switchView`, `api()` | **KEEP** | Behavior contract | Low | — |
| Exam state machine, timers, keyboard, strict lock, zen mode | exam.js | **KEEP** | Core product | — | M7 guards |
| Timer ring SVG + injection | exam.js:10-29 | **REFINE** visuals only (stroke tokens); `data-motion-ignore` | Functional + already on-brand | Injection replaces node → animations must never bind it | M7 |
| `:root` tokens | app.css:6-65 | **REPLACE** with full semantic token layer; legacy aliases kept until app.css deletion | Governance | Visual diff regressions → zero-diff gate at M1 | M1 |
| Wordmark gradient text | app.css:163-172 | **REPLACE** with engraved wordmark + palette-cell mark | Anti-slop detector #1 | None | M4 |
| `.panel` card everywhere | app.css:293-307 | **RECOMPOSE** into 4 distinct surface treatments per zone | Same-card slop detector | Renderer class hooks | M4-M6 |
| Buttons/badges/inputs | app.css:355-453 | **REFINE** anatomy (hairline draw, lock states, mono numerals) | State craft | onclick globals untouched | M4 |
| Generator deck (sliders/chips/mode) | index.html:110-181 | **RECOMPOSE** as instrument console + T4 sequence | Signature moment | Hidden driver selects must remain | M7 |
| Data-stream overlay | app.js:597-618 | **REPLACE** with GSAP console timeline | Current = generic scanlines | Same show/hide API kept | M7 |
| Exam shell + palette | app.css:550-770 | **REFINE** into "designed silence" + palette-cell polish | Task zone | Zero behavior change | M7 |
| Result page | index.html:809-854 | **RECOMPOSE** into verdict stage (T7) | Payoff is currently flat | IDs stable | M8 |
| Modals | app.css:902-995 | **REFINE** + focus trap + Esc + clip-wipe entry | A11y gap (no trap today) | — | M4 |
| Constellation/scatter/chronology/trend SVG | app.js:304-337, 681-813 | **RECOMPOSE** into branded graphic system (mono labels, signal strokes, threshold ticks) | Best domain assets | Render output strings keep classes | M5/M8 |
| Responsive blocks | app.css:1442-1487 | **REPLACE** with re-authored mobile system (§18) | Compression ≠ art direction | — | M9 |
| Reduced-motion block | app.css:1429-1436 | **REPLACE** with authored edit (matchMedia + CSS) | §30 | — | M10 |
| Legacy compat blocks (`.exam-header`, `.palette-grid`…) | app.css:1489-1702 | **VERIFY then DELETE** — grep first; likely dead | Debt | Must grep JS + HTML first | M11 |

---

## 5. North star & design principles

- **Visual thesis (one sentence):** *Swiss instrument-grid discipline organizes a near-black examination telemetry world, while kinetic Archivo type and one WebGL Readiness Core turn study data into a machine that visibly calibrates you across the cut-off line.*
- **Brand traits:** precise · instrument-grade · decisive. **Counter-traits:** playful · ornamental · cozy.
- **Controlled-spectacle cadence:** ceremony at thresholds (arrive / generate / submit / verdict), stillness in between; one lead idea per moment (§28 tiers enforced).
- **Global invariants:** one signal family (emerald); mono = any number that is measured (timers, marks, IDs, %, dates); every status has shape+label, never color alone; hairline rules + elevation by surface lift (no drop-shadow decoration); 10px/6px radii; focus = 2px signal outline + 2px offset everywhere.
- **Hard prohibition:** purple/indigo/pink/cyan aurora gradients, violet glow atmospherics. Violet `#8A93FF` exists **only** as the solid "marked for review" state fill (exam palette semantics already require a distinct fifth hue) — never as gradient, glow, or background field.
- **Originality criteria:** palette-cell mark, threshold-line grammar, section-code stamps (`PH2·FM·REGS`), cut-off verdict stamps, OMR-inspired dot registration — swap test: relocating this skin to a generic SaaS would read as nonsense. ✓

---

## 6. Reference decomposition (research corpus: `docs/DESIGN_RESEARCH.md`, 9 captured sites + 5 encoded)

| Reference | Composition | Type | Color/material | Motion/3D | Principle adapted | Not copied |
|---|---|---|---|---|---|---|
| linear.app | Elevation via lighter surfaces | Inter var w510 | #08090A near-black | Subtle | Surface-lift hierarchy, no borders-as-decoration | Marketing layout |
| raycast.com | Dense tool UI | Inter + GeistMono | Near-black + canvas hero | 22 transitions | Mono as credibility voice; canvas hero carries identity | Hero composition |
| vercel.com | Extreme restraint | GeistSans 400 | #000 | Canvas-only spectacle | Let one artifact (our Core) carry the hero | Emptiness as brand |
| brilliant.org | Product-as-hero | CoFo custom | White/warm panels | Interactive canvas | Telemetry IS the hero content | Playful palette |
| dlr-test.training | Clinical precision | DIN 2014 | Light | — | Exam-hall authority for the shell | Their lightness |
| langmobile (MILL3) | Warm editorial | Ambit 900 + DM Sans | Cream | 75 micro-transitions | Micro-transition density target | Warmth |
| trevornoah.com | Color-block fields | Die Grotesk | Deep navy panels | Canvas | Bold flat fields instead of borders | Palette |
| duolingo / supabase | Character / dev-cred | Custom / Manrope | Dark teal / green-tinted black | SVG | Status color with personality; restraint counts | Gamification |
| LiquidInk (encoded) | — | — | — | 3D symbol as protagonist | One meaningful object structures chapters | Ink material |
| Matters (encoded) | — | — | Near-black + acid signal | — | One decisive signal on near-black; intelligence over decoration | Editorial model |
| PX PUSH (encoded) | — | — | — | Scroll-as-time | State-change sequences as authored time (generate→enter→submit) | CRT kitsch |
| SurVedaa (encoded) | — | — | Controlled darkness | Patient reveals | Designed silence in the exam shell | Photo pacing |
| ShareBien (encoded) | — | — | Chrome identity | — | Material must repeat through type+interaction, not one hero effect | Chrome |

**Domain research (primary originality source):** TCS iON exam-hall grammar (candidate block, palette, instructions sheet — already emulated and kept), OMR bubbles & registration dots, syllabus subject codes, negative-marking arithmetic (−0.25×marks), gazette/amendment language, and above all **the cut-off line** — the number every Indian competitive exam is organized around. These motifs cannot belong to any other product.

---

## 7. Style synthesis & territories

**Territory A — "The Examination Engine" (SELECTED).** Backbone: Swiss/International Typographic (grid, numbered systems, one signal). Character: Terminal/Hacker telemetry world (mono command state, phosphor signal, event log) rebuilt for an exam observatory, not hacker kitsch. Accent: Layered Depth (3 planes max) + Kinetic Typography (variable-axis lock). Sentence: see §5 thesis. Quality tests (§9 of master prompt): swap ✓ fail-for-others · motif ✓ palette-cell/threshold · three-frame ✓ hero→exam silence→verdict · silhouette ✓ plate-stack readable at thumbnail · type ✓ Archivo Expanded carries identity pre-color · background ✓ every view staged (§13) · mobile ✓ §18 · restraint ✓ one lead idea/moment.

**Territory B — "Archive & Act" (Dark Academia) — REJECTED:** ink-brown/parchment beauty suits the Act text but contradicts TCS-iON simulation fidelity and telemetry features; candlelight reads leisure, not readiness; fails the *perform-under-a-clock* emotional test.
**Territory C — "Warm Pedagogy" (cream editorial) — REJECTED:** betrays established dark command-center DNA and exam psychology; friendly ≠ exam-grade; fails silhouette and swap tests against the captured research verdict (near-black + mono = technical credibility).
**Purple remix note:** Glassmorphism/Aurora/Bento seed palettes containing purple were structurally excluded; the only retained glass behavior is the pre-existing runtime chip, rebuilt as solid elevated surface (no blur haze).

---

## 8. Brand world bible

1. **Core idea:** a precision engine calibrating a candidate across the cut-off line.
2. **Voice:** terse briefings; UPPERCASE mono metadata; verdicts as stamps ("CLEARED 40% CUT-OFF"); CTAs are commands ("START MOCK", "ENTER EXAM", "GRADE SITTING"); no exclamation marks, no marketing adjectives.
3. **Signature motifs:** (a) **palette cell** — the 5-state question square, reused as brand mark, bullet, chip, step, loading tick, favicon; (b) **Threshold Line** — 1px signal hairline with tick marks: readiness meter, verdict divider, heatmap ladder, radar baseline, timer zero-mark; sections hand off by transforming it (horizontal→vertical divider→ring→sweep); (c) section-code stamps; (d) OLD→NEW diff blocks.
4. **Material:** machined dark metal + engraved hairlines + phosphor signal; elevation only by surface lift; grain at ≤3% opacity for anti-sterility.
5. **Image world:** none — data is the imagery (SVG telemetry, procedural 3D, type). No photography, no illustrations of people.
6. **3D world:** see S-3D-1. Silhouette-first, metalness-driven, emissive = mastery, fog = atmosphere; camera always protects a left-column reading zone.
7. **Graphic world:** 1.5px strokes; mono tick labels; dot-grid plotting; thresholds as ticked lines; no drop shadows; chart category colors = topic hash palette (existing `getTopicColor` retained but re-tuned to desaturated instrument hues).
8. **Motion character:** verbs **calibrate · sweep · lock**. Energy curve: quiet hum → rising telemetry → hard lock → stillness → verdict release. Eases: entrance `expo.out`; control `power3.out`; payoff signature **lock-ease** (CustomEase: fast approach, ~1px overshoot, settle). Rest behavior: only the Core idles (0.05 rad/s drift) + timer; everything else fully rests.
9. **Recurring transition:** the **lock-in** — content arrives slightly scaled/offset, snaps to grid with a hairline drawing in (DrawSVG). Used by tab changes, reveals, stamps, verdicts at different energies.
10. **Moments of silence:** the exam shell in-attempt; law-text and passage reading panes; the beat before the verdict stamp. Designed silence vs blankness: these fields keep dot-grid texture, exact margins, and one live instrument (timer).
11. **Could another brand own this?** No — palette cells, cut-off stamps, OMR dots, section codes, and negative-marking arithmetic are exam-domain-locked.

---

## 9. Narrative & content architecture

**Session story (one nightly sitting):** ARRIVE (Control Center: "how ready am I tonight?") → DIAGNOSE (weak topics, radar, SRS dues) → COMMIT (generator deck; the machine forges a paper) → ENTER (instructions ritual; doors open; silence) → PERFORM (60 min, zero spectacle) → JUDGE (verdict stage: score vs cut-off) → TARGET (weak areas → drill → next action). Every view sits on this line; no view decorates outside it.

- **CTA hierarchy:** ① START MOCK / GENERATE AND ENTER EXAM (magnetic, only magnetic targets + exam submit) ② per-view primaries (Grade, Search, Load Today) ③ utility buttons. One level-1 CTA visible at a time.
- **Proof strategy:** the product's own telemetry is the proof (real readiness %, real accuracy, real amendment diffs) — never invented numbers (§4.3).
- **Handoffs:** Today → exam via Core *launch* collapse (T3→T4); exam → result via submit-lock; result → review via "TARGET LOCKED" action; law radar → updates via sweep→feed grammar.
- **Task-flow rhythm (non-cinematic views):** orientation (page-head + mono sub) → action (consoles) → feedback (status-line console voice) → recovery (empty/error scenes §C16-C18).

---

## 10. Route signature matrix

| ID | View | Zone | User goal | Opening impression | Signature composition | Motif/asset | Background (BG id) | Motion intensity | Unique interaction | Mobile thesis | Payoff | Status |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| R1 | today | Showcase | "How ready am I?" | Instrument band: Core right, telemetry left | 3D stage + kinetic numeral + panel ladder | Readiness Core, threshold meter | BG1 | High entry → idle | Core tap/pointer parallax; numeral axis-settle | Stacked; Core reframed small | Readiness number locks | planned |
| R2 | exam | Task+ceremony | Generate & sit a mock | Generator console; then silence | Console → shell (2 states) | Sliders as dials, palette cells | BG2/BG3 | High (gen) → near-zero (attempt) | Data-stream forge sequence; magnetic CTA | Full-width dials; palette bottom sheet | Entry into exam silence | planned |
| R3 | pyq | Task/archive | Attempt real papers | Archive shelf | Dossier grid with year/phase stamps + ATTEMPT seal | Dossier cards, subject stamps | BG4 | Medium | Hover seal stamp; Flip into shell | Vertical dossiers | Paper opened | planned |
| R4 | review | Task | Target weaknesses | Instrument board | Heatmap ladder left, drill consoles right | Heat cells + cutoff ticks, chronology | BG5 | Low-medium | Row hover reveals threshold tick | Stacked consoles | Target locked | planned |
| R5 | essay | Task/studio | Write & get graded | Writer's desk | Prompt plate + editor + 4 grading dials | Word-counter ticker, dials | BG6 | Low; dial sweep payoff | Live word-count tick; dial sweep on grade | Desk stacks | Score dials settle | planned |
| R6 | sources | Task | Search & cite | Citation ledger | Command search bar + authority meters | Authority bar, ledger boxes | BG7 | Low | Meter fills on result | Same | Citation opened | planned |
| R7 | lawSources | Narrative/task | Revise Act, track amendments | Engraved ledger + radar | Mono law-text + amendment radar sweep | Radar, OLD→NEW diffs | BG8 | Medium (sweep) | Radar sweep on scan | Radar→compact dial | Scan complete | planned |
| R8 | updates | Task | Triage intel | Wire feed | Briefing cards with verification stamps + diffs | Stamps, diff blocks | BG9 | Low; stagger lock-in | Expand detail (height tween) | Same | Update reviewed/dismissed | planned |
| R9 | resultPage (overlay) | Showcase payoff | Receive verdict | Verdict stage | Giant score + threshold sweep + stamp + viz cascade | Verdict stamp, scatter, chronology, trend | BG10 | High, short | Score count-up; stamp slam (T7) | Stamp scales; cascade stacks | CLEARED/BELOW verdict + next action | planned |
| R10 | modals (instructions/citation) | System | Consent/read | Branded threshold | Clip-wipe entry; mono rules list; kbd row | Palette-cell bullets | dim field | Brief | Focus trap + Esc | Same | Confirmed | planned |
| R11 | system states (loading/empty/error/success) | System | Trust the machine | Console voice | Micro-scenes per state (§C16) | Dormant-core glyph, console lines | inherited | Brief | — | — | Recovery path | planned |

---

## 11. Section scorecards (condensed; 12 fields → columns)

| Sec | Purpose/beat · Content | Dominant visual · BG | Type behavior · Entry/hold/exit · Handoff | Desktop → Mobile · Reduced motion | Accept frame |
|---|---|---|---|---|---|
| S1 today-hero | Premise: readiness at a glance; live metrics | Core stage over dot-grid horizon (BG1) | H1 kinetic line-rise + wdth settle; numeral count + axis lock; entry T1/T3, hold=idle drift, exit=pin release → panel ladder | Split 7/5 cols → stacked; Core small, tap-rotate · RM: static composed frame + final numeral | Storyboard 0/25/50/75/100 (T3) |
| S2 today-panels | Proof: weak topics, radar, SRS, analytics, goals | Panel ladder on engraved rules (BG1b) | Lock-in stagger 40ms; mono data ticks; entry on scroll trigger, exit to footer-CTA | 2-col → 1-col · RM: immediate | All panels populated + empty variants |
| S3 generator-deck | Inciting action: forge the paper | Instrument console; dial sliders, template chips as stamped keys (BG2) | Slider value mono ticks; chips border-draw; entry lock-in; exit = T4 overlay take-over | Dials full-width · RM: static console | T4 storyboard |
| S4 instructions-ritual | Threshold: rules before entry | Modal over dimmed field; palette-cell bullets; kbd row | Clip-wipe entry; focus trap; exit = doors-open wipe to shell | Same · RM: fade | Keyboard-only pass |
| S5 exam-shell | Performance: designed silence | Flat near-black, faintest dot-grid; question column 920px; palette rail (BG3) | No entry animation mid-attempt; option selection = border-draw + cell check; question swap 80ms cut | Palette → bottom sheet; options ≥48px · RM: identical (already still) | Full attempt, keyboard-only |
| S6 exam-palette | Instrument: state of the attempt | 5-state cells; section grouping for PH1_P1 | Cell state fills pop 120ms; current = amber reticle | Bottom sheet drag handle · RM: instant | 100-question grid stress |
| S7 pyq-dossiers | Archive: choose a paper | Dossier cards, stamped year/phase, ATTEMPT seal (BG4) | Hover: lift + seal rotate 2°; entry stagger; Flip into shell | Vertical stack · RM: no lift | Filter permutations |
| S8 review-board | Target: heatmap + consoles | Signal ladder table with cutoff ticks; drill console (BG5) | Row hover: threshold tick slides in; entry lock-in | Stack · RM: instant | Heatmap with 0-attempt rows |
| S9 essay-desk | Studio: write | Prompt plate / editor / dials; ruled margin line (BG6) | Word counter mono tick; grade = 4 dial sweeps + total lock | Stack · RM: dials jump to value | Graded result render |
| S10 sources-ledger | Search & cite | Command bar + authority meters (BG7) | Meter fill 300ms expo; results lock-in | Same · RM: instant | No-results state |
| S11 law-ledger | Revise the Act | Engraved mono law-text; marginal ticks (BG8) | Text is still; AI panel lock-in | Same · RM: instant | Full-act scroll |
| S12 amendment-radar | Watch the horizon | Radar sweep SVG; blips = amendments; OLD→NEW diffs (BG8b) | Sweep DrawSVG 2.4s; blips pop on sweep pass | Compact dial · RM: static radar + blips | Scan running/complete |
| S13 updates-feed | Triage intel | Wire-feed cards; verification stamps; diff blocks (BG9) | Cards lock-in stagger; expand height tween | Same · RM: instant | All filter combos |
| S14 verdict-stage | Judgment: the cut-off moment | Vignette field; threshold line sweep; stamp (BG10) | T7 sequence; score count-up wdth settle; stamp slam −3° | Stamp scales to width · RM: all states shown, no slam | Storyboard T7; both CLEARED & BELOW paths |
| S15 viz-cascade | Evidence after verdict | Scatter matrix, chronology strip, trend line | Dots pop by topic; strip draws L→R; trend DrawSVG | Horizontal-scroll scatter · RM: static charts | Populated 50-Q result |
| S16 loading-scenes | Trust during waits | Console lines + palette-cell progress ticks | Typewriter mono lines (RM: instant) | Same | Forced slow network |
| S17 empty-scenes | First-use honesty | Dormant-core glyph + command CTA ("NO TELEMETRY — THE ENGINE STARTS WITH ONE MOCK") | Fade | Same | Fresh DB |
| S18 error-scenes | Recovery | Signal-fault panel + retry; console voice | Fade + retry pulse (RM: static) | Same | Backend stopped |

---

## 12. Semantic design tokens

### 12.1 Color (raw values live once in `tokens.css`; OKLCH primary with hex fallback)

| Token | Hex | ≈OKLCH | Job |
|---|---|---|---|
| `--canvas` | #08090A | oklch(.131 .004 255) | Base field |
| `--canvas-raised` | #0E1013 | oklch(.168 .005 255) | Hero band alt |
| `--surface-1/2/3` | #121419 / #171A20 / #1E222A | — | Elevation ladder (lift, never shadow) |
| `--ink` | #F2F4F6 | oklch(.962 .005 250) | Primary text |
| `--muted` | #9AA3AD | oklch(.72 .012 250) | Secondary text |
| `--faint` | #5C6470 | oklch(.51 .015 255) | Large labels/UI only (3.3:1) |
| `--rule` / `--rule-strong` | rgba(242,244,246,.07/.14) | — | Hairlines |
| `--signal` | #00E5A0 | oklch(.82 .17 168) | The signal |
| `--signal-dim` / `--signal-soft` | #00B37E / rgba(0,229,160,.10) | — | Hover / fields |
| `--on-signal` | #04110C | — | Ink on signal fills |
| `--danger` | #FF4D6A | oklch(.63 .21 15) | Wrong/critical |
| `--warn` | #FFB224 | oklch(.80 .16 80) | Review/due |
| `--mark-state` | #8A93FF | oklch(.69 .12 285) | **Only** marked-for-review fill |
| `--focus` | var(--signal) | — | Focus ring |
| `--selection` | rgba(0,229,160,.22) | — | Text selection |
| `--scrim` | rgba(8,9,10,.55→0) | — | Text protection over Core/media |
| `--3d-env/key/fill/rim/emissive` | fog #0A0C10 · #EAF2FF · signal-dim · #C9D4E0 · signal | — | Scene S-3D-1 |
| `--chart-1..8` | desaturated instrument hues (teal/steel/sand/olive…) | — | Topic hash (re-tuned `getTopicColor`) |

**Contrast whitelist (measured, WCAG formula, canvas #08090A unless noted):**

| Foreground | Background | Ratio | Min | Pass |
|---|---|---|---|---|
| ink | canvas | 18.2:1 | 4.5 | ✓ |
| ink | surface-1 | 16.8:1 | 4.5 | ✓ |
| muted | canvas | 7.8:1 | 4.5 | ✓ |
| muted | surface-2 | 7.2:1 | 4.5 | ✓ |
| signal | canvas | 12.1:1 | 3 | ✓ |
| on-signal | signal fill | 11.7:1 | 4.5 | ✓ |
| danger | canvas | 6.2:1 | 4.5 | ✓ |
| warn | canvas | 11.1:1 | 4.5 | ✓ |
| mark-state | canvas | 7.3:1 | 4.5 | ✓ |
| faint | canvas | 3.3:1 | 3 (UI/large only) | ✓ restricted |
| H1 over Core worst frame | scrim zone composited | ≥7:1 verified at M3 via pixel sample | 3 | gate |

Worst-frame rule: Core emissive peaks are luminance-clamped (bloom off on text side); scrim gradient reserved behind hero left column; pixel-sampled at M3 QA.

### 12.2 Typography

- **Display — Archivo variable** (VERIFIED: wght 100-900, wdth 62-125 via Google Fonts; license OFL). Roles: H1 view titles (wdth 118 / 900, `clamp(26px,3.2vw,40px)`, kinetic wdth 100→118 settle); readiness numerals (tabular, wdth 112 / 900, `clamp(64px,8vw,112px)`); verdict stamp (wdth 125 / 900, uppercase, −3°).
- **Body/UI — Inter variable** (OFL): body 14/1.55; dense 13/1.5; labels 11 uppercase +0.06em; measure 62-72ch prose, 920px question column.
- **Data — JetBrains Mono** (OFL): timers, marks, IDs, %, dates, axis labels, console lines, section stamps; tabular figures everywhere numbers are measured.
- **Specimen test list (M1 gate):** short/long H1 (incl. "Material Categorization Management"), one-word verdicts, body paragraphs, buttons, forms/tables/numerals/dates, error text, uppercase+punctuation (`PH2·FM·REGS`, `−0.25`), 375px width, 200% zoom, wdth extremes. Fallback stacks kept from current CSS.
- **Kinetic rules:** titles split by line; numerals count with axis settle; per-character only for the single verdict word (deliberate beat); semantic DOM text always readable; SplitText re-splits on resize/replace; RM = resolved static text.

### 12.3 Spatial & material

Content max-width 1480px; stage band full-bleed. Grid: 12-col / 24px gutter → 8-col ≤1080 → 4-col ≤720; spacing scale `--sp-1..8` retained (renders already use it); section breathing 24-48px (task) / 64-96px (ceremony). Radii: 10px panels, 6px controls, 2px cells/stamps. Borders: 1px rules only; elevation = surface ladder + 1px top light edge; drop shadows removed except modal depth. Z-layers: canvas −1 · content 1 · sticky 50 · modal 100 · overlay 200. Safe areas: `env(safe-area-inset-*)` on mobile rail/sheet. Grain: ≤3% data-URI noise on canvas fields (anti-sterility, keeps matte material coherent).

### 12.4 Motion tokens

`--dur-micro 120ms · --dur-std 240ms · --dur-cine 700ms · --dur-epic 1100ms`; eases: `--ease-entrance expo.out`, `--ease-control power3.out`, `--ease-lock CustomEase("M0,0 C0.7,0 0.85,1.18 1,1")` (1px overshoot settle); stagger 40-60ms semantic; distances: control 2-4px, panel 12-16px, stage 40-80px; pointer lag quickTo 0.35s; parallax only on Today band (3 planes); RM substitutes per timeline table.

---

## 13. Background system

| ID | Route/section | Narrative job | Base | Structure | Atmosphere | Narrative layer | Interaction | Contrast protection | Mobile | RM | Cost |
|---|---|---|---|---|---|---|---|---|---|---|---|
| BG1 | today hero | Observatory floor | canvas-raised | dot-grid horizon + faint 12-col rules | grain + single emerald light falloff (upper-right, ≤6%) | Core canvas + ghost mono section codes | pointer parallax on grid (subtle) | left scrim for text | grid only | static falloff | low (CSS + existing canvas) |
| BG1b | today panels | Instrument wall | canvas | engraved hairline rules per panel group | grain | threshold meter line | row hover tick | solid surfaces | same | same | minimal |
| BG2 | generator deck | Forge | surface-1 | engraved console frame + dial baselines | grain | palette-cell progress strip during T4 | slider-driven light position (existing `--gen-x/y` kept, re-skinned) | solid | same | static | low |
| BG3 | exam shell | Designed silence | canvas flat | faintest dot-grid (1.5% alpha) | none | none | none | n/a | same | same | zero |
| BG4 | pyq archive | Shelf of papers | canvas | ruled baseline grid | warm-neutral tint lift (surface-2 fields) | dossier shadows as lift | hover lift | solid | same | same | low |
| BG5 | review board | Blueprint | canvas | drafting dot-grid + measure ticks | grain | chronology strip as ambient divider | row threshold tick | solid | same | same | low |
| BG6 | essay desk | Writing room | canvas | ruled margin line (left, signal-dim) | grain | word-count ticker | none | solid | same | same | minimal |
| BG7 | sources ledger | Ledger | canvas | horizontal ledger rules | grain | authority meters | meter fill | solid | same | same | low |
| BG8 | law ledger | Gazette | canvas | engraved column rules; marginal line numbers | grain | radar sweep scene (SVG) | sweep on scan | law-text on solid | radar→dial | static radar | medium (SVG anim only on scan) |
| BG9 | updates wire | Intel feed | canvas | vertical hairline feed rail | grain | stamps/diffs | expand tween | solid | same | same | low |
| BG10 | verdict stage | Judgment | canvas vignette (radial darkening) | threshold line | single-hue emerald bloom ≤8% (non-purple) | stamp + viz | T7 cascade | text on solid center | bloom off | static vignette | low |

Section handoffs transform the Threshold Line (horizontal meter → vertical divider → radar baseline → timer ring → verdict sweep), so views feel edited, not stacked.

---

## 14. Asset manifest (code-native; no photography; no fabricated media)

| ID | Asset | Job | Format | Source/license | Variants | Alt/status |
|---|---|---|---|---|---|---|
| A1 | Archivo variable (wdth+wght) | Display | woff2 (Google CDN) | OFL | latin + latin-ext subset via css2 API | VERIFIED available |
| A2 | Inter variable | Body | woff2 (Google CDN) | OFL | latin | existing |
| A3 | JetBrains Mono | Data | woff2 (Google CDN) | OFL | latin | existing |
| A4 | GSAP core + ScrollTrigger, Flip, SplitText, DrawSVG, MotionPath, Observer, CustomEase | Motion | min.js, vendored `js/vendor/` | Free per gsap.com/pricing (post-Webflow); confirm license header at download (M2) | desktop/mobile shared | version pinned at download, recorded here |
| A5 | three.module.min.js | 3D | ESM, vendored + importmap | MIT (mrdoob) | pinned version recorded M2 | — |
| A6 | Grain texture | Atmosphere | data-URI SVG turbulence | authored | 1 tile | decorative aria-hidden |
| A7 | Core poster (`core-poster.svg`) | 3D fallback/loading | authored SVG under `js/three/` (served) | authored | desktop/mobile crop | role=img + label |
| A8 | Dormant-core glyph | Empty states | inline SVG | authored | — | decorative |
| A9 | Palette-cell mark + favicon | Brand mark | inline SVG + ico/svg favicon under `css/` mount path or head data-URI | authored | — | — |
| A10 | Topic chart hues | Data-viz | tokens only | authored | — | — |

No paid assets. No stock imagery. Provenance recorded at download time (M2/M3) in §23 decision log.

---

## 15. 3D scene manifest & design bible

| Scene | Route | Story job | Subject | Source | Material/light | Camera | GSAP labels | Desktop | Mobile | Poster/fallback | Perf plan | Status |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| S-3D-1 | R1 today hero | The machine that shows readiness | "Readiness Core": 10 machined ledger plates (one per topic cluster from `/dashboard` heatmap) in twisted stack + 1 orbiting emerald clock-ring + ascending data motes | procedural Three.js geometry (no models) | plates: MeshStandardMaterial color #14171C, metal .88, rough .34, per-plate emissive by mastery (signal ≥60%, crimson-edge weak, neutral unseen); ring: torus emissive signal; lights: key #EAF2FF (2.4, upper-left), fill signal-dim (.5), rim (#C9D4E0, rear); fog #0A0C10 | PerspectiveCamera fov 34, pos (3.4,1.9,5.2)→dolly (0,0.4,0); pointer parallax ±0.12rad via quickTo | arrival/recognize/respond/launch/return | full | 8 plates, no motes, DPR 1.25, tap-drag rotate | A7 poster; no-WebGL = poster + live numerals; RM = static frame at 55% orbit | DPR cap 1.75; loop paused via IntersectionObserver + tab switch + zen; <40k tris; dispose on unload | planned |

**Storyboard (T3):** 0% empty band, poster visible → 25% plates assemble staggered (y −2→0, rot settle, expo.out, 1.1s) → 50% emissive mastery states fade in + readiness numeral counts (recognition) → 75% ring completes first orbit; pointer response live → 100% idle drift; **launch** (Start Mock): plates scaleX→0.02, spiral into stream toward overlay (0.6s), ring contracts → becomes T4 scan bar (object handoff); **return**: post-verdict, plates re-light with updated mastery on next Today visit.
**Canvas pixel gate (M3):** screenshot must show the plate stack silhouette, not a blank mount; text-zone sample ≥7:1.

---

## 16. GSAP motion map

**Global grammar:** verbs calibrate/sweep/lock; energy curve §8; eases §12.4; stagger semantic (heatmap worst-first, panels in reading order); depth: atmosphere slowest/Core subject/grid near-static; rest = Core idle + timers only; recurring transition = lock-in; tiers (§28): T3/T4/T7 narrative · T2 structural · T8/T15 explanatory · T9 responsive · grid/grain ambient (quiet during reading & attempts). Fine-pointer: parallax+magnetism; coarse: press states, no magnetism; RM column per timeline.

| ID | Scene/component | Trigger | Labels/states | DOM | SVG | 3D/camera | Plugins | Mobile | RM | Cleanup | Acceptance |
|---|---|---|---|---|---|---|---|---|---|---|---|
| T1 | View titles | switchView | line-rise→wdth-settle | H1 | — | — | SplitText, CustomEase | shorter travel | resolved text | gsap.context per view; revert on switch | every view, 60fps |
| T2 | Tab transition + underline | switchView | out 120ms→in stagger 40ms | tabs, panels | — | — | Flip (underline), core | same | cut | context | rapid-click clean |
| T3 | Readiness Core | load/pointer/launch | arrival/recognize/respond/launch/return | hero band | — | plates/ring/camera/emissive | core+quickTo | simplified | static frame | IntersectionObserver pause; dispose | §15 storyboard |
| T4 | Generation sequence | generateSmartMock | boot→blueprint→grounding→forge(counter+cell strip)→locked→doors-open | overlay, console lines, cells | cell strip | — | timeline, DrawSVG(bar) | same, less type | single status line | bound to promise resolve; hide on error | API latency-safe (indeterminate loop until resolve) |
| T5 | Numerals | data render | count→axis settle | metric values | — | — | core | same | final value | re-init after innerHTML | dashboard+result |
| T6 | Timer ring | 1s tick | — | — | ring | — | **none (protected)** | same | same | GSAP never binds `.timer-ring-*`; `data-motion-ignore` | unchanged behavior |
| T7 | Verdict stage | submit result | console line→score count→threshold sweep→stamp slam→viz cascade | resultPage | scatter/chrono/trend | — | timeline, SplitText(stamp word), DrawSVG | scaled | all states shown | revert on close | both verdict paths |
| T8 | Radar sweep | scan action | sweep→blips | — | radar SVG | — | DrawSVG, MotionPath(blip) | compact dial | static+blips | kill on tab switch | scan states |
| T9 | Microinteractions | hover/press/focus | per catalog (§4 M4 list) | controls | — | — | quickTo (magnet ≤6px, 2 CTAs only) | press only | color-only | delegated listeners | 100% controls |
| T10 | Scroll reveals | ScrollTrigger | lock-in batches | today-below-fold, review, updates | — | — | ScrollTrigger | same, shorter | immediate | refresh after fonts/render | no layout shift |
| T11 | Today pin transform | scroll (Today only) | hero→handoff (2 states, ≈140vh) | hero band | threshold meter | Core recede | ScrollTrigger pin | **no pin; stacked** | immediate | release verified | 0/25/50/75/100 frames |
| T12 | Modal entry/exit | open/close | clip-wipe | modals | — | — | core | same | fade | focus trap pair | Esc+backdrop |

**Pin storyboard (T11):** 0% hero full (Core right, title+numeral left) · 25% numeral locked, meter drawn · 50% Core drifts right/scales .7, "days to exam + next action" plate slides over (state change #2) · 75% panel ladder rises beneath, pin progress hairline shows · 100% release into panels; continuous element = Threshold Line; fast/reverse scroll safe; focusable content never pinned under; RM/mobile = no pin. Justification: two narrative states (overview → directive) that a static stack would flatten.

---

## 17. Component inventory (primitive/composite · states · milestone)

| ID | Name | Kind | States covered | Motion | A11y notes | M |
|---|---|---|---|---|---|---|
| C1 | btn (default/primary/warn/danger) | primitive | d/h/f/a/disabled(+lock glyph)/loading | hairline draw-in; label 1px shift; magnet only on 2 CTAs | focus ring; disabled keeps contrast | M4 |
| C2 | chip (template/filter/mode) | primitive | d/h/f/active/press | border draw; active fill pop | role=tab/pressed semantics reviewed | M4 |
| C3 | input/select/textarea/slider | primitive | d/h/f/filled/error/disabled | border+ring; slider thumb signal glow + mono value tick | labels exist; error text announced | M4 |
| C4 | badge/status stamp | primitive | ok/warn/danger/neutral/verified/contradicted | pop 120ms | text+color dual coding | M4 |
| C5 | metric card | primitive | d/h/loading(skeleton console)/empty | numeral T5 | readable value markup | M4 |
| C6 | panel/surface treatments (console/ledger/dossier/stage) | composite | d/h/expanded | lock-in | landmark order kept | M4 |
| C7 | table (heat ladder/ledger) | composite | populated/empty/long/error row | row hover threshold tick | sticky th; row headers | M5 |
| C8 | modal (instructions/citation) | composite | closed/open/focus-trap/esc | T12 clip-wipe | trap, return focus, aria-modal | M4 |
| C9 | data-stream overlay → forge console | composite | idle/running/error-complete | T4 | status role=alert on error | M7 |
| C10 | exam shell + option rows | composite | answered/selected/marked/critical-timer | 80ms cut; option border draw | keyboard 1-5/A-E intact | M7 |
| C11 | palette cells + legend | composite | 5 states + current reticle | state fill pop | buttons with aria-label state | M7 |
| C12 | timer ring | composite | normal/warning/critical(steady, no blink) | protected T6 | time also as text | M7 |
| C13 | dossier card + seal | composite | d/h/attempted badge | lift+seal rotate | card is a link/button, not div-click only (keep onclick but role/button) | M6 |
| C14 | grading dials + word ticker | composite | idle/sweep/settled/out-of-range warn | dial sweep T | value announcements throttled | M6 |
| C15 | update card + diff blocks | composite | d/expanded/verified/contradicted/dismissed | expand tween | expand = button with aria-expanded | M5 |
| C16 | loading scenes (skeleton/console) | system | streaming/complete | typewriter lines | role=status | M5 |
| C17 | empty scenes | system | first-use/no-results/no-data | fade | command CTA present | M5 |
| C18 | error scenes + retry | system | fault/retrying/recovered | fade + steady retry pulse | role=alert; retry button | M5 |

---

## 18. Mobile art direction

**Thesis:** *the same engine, one-handed.* Preserve: near-black field, emerald signal, mono timers, one wow (verdict slam + simplified Core). Thumb model: bottom-anchored actions, top-anchored instruments.

| Experience | Desktop | Mobile/coarse | Reduced motion |
|---|---|---|---|
| Hero 3D (T3) | Full band, parallax, launch collapse | Core small above numerals, tap-drag rotate, no motes, DPR 1.25 | Poster frame + numerals |
| Today pin (T11) | 140vh pin, 2 states | No pin; stacked directive plate | Immediate |
| Tab nav | Sticky bar + Flip underline | Scroll-snap thumb rail, safe-area padded, active underline Flips | Cut |
| Generation (T4) | Full console sequence | Same, shorter type-on, big CTA | Status line only |
| Exam palette | Right rail | Bottom sheet with drag handle; legend collapsible; cells ≥44px | Instant states |
| Option rows | Hover affordance | Full-width ≥48px targets; selection = border+fill only | Same |
| Magnetic CTAs | quickTo ≤6px | Stable tactile press | Same |
| Kinetic titles (T1) | Line-rise + wdth settle | Fewer layers, shorter travel | Resolved text |
| Hover reveals (heat tick, meters) | Pointer-driven | Tap/inline always-visible equivalents | Immediate |
| Radar (T8) | Sweep scene | Compact dial with blips | Static radar |
| Verdict (T7) | Full cascade | Stamp scales to width; cascade stacks; count-up kept shorter | All states, no slam |
| Backgrounds | 5-layer recipes | Base+structure+grain merged; falloff static | Curated still |

Breakpoint behavior replaces current collapse-only CSS at 1080/720/420. Viewports: 375×667, 390×844, 412×915, 768×1024, 1024×768, plus 920px collision width; portrait+landscape on shell; dvh for shell height; no hover dependencies anywhere.

---

## 19. Accessibility, performance, compatibility

- **Standard:** WCAG 2.2 AA baseline + stronger motion controls. Browsers: current Chrome/Edge (primary, VERIFIED environment), Firefox/Safari best-effort; WebGL1-level features only for Core (fallback poster otherwise).
- **Semantics/keyboard:** landmarks + heading order kept; modal focus trap + Esc + focus return (fixes current gap); visible focus = 2px signal + 2px offset on every control (including qnum/chips — current inconsistency fixed); keyboard-only full exam is an M7 acceptance test; no focusable content obscured by sticky layers; no keyboard dead-ends from hover-only reveals.
- **Status coding:** palette cells keep number+state-label semantics; verdicts keep text ("CLEARED"/"NOT CLEARED") — color never alone. **Blink removal:** `.timer.critical` blink → steady crimson (photosensitivity), ring pulse replaced by static warning color.
- **Motion/vestibular:** authored RM edit (§16 RM column); no pinned traps; no autoplay loops except Core idle (paused in RM + low-power); OS-level `prefers-reduced-motion` via gsap.matchMedia + CSS.
- **Canvas/JS failure:** semantic content renders without GSAP/Three (feature-detect guards); poster replaces canvas; no-JS shows static readable page shell.
- **Budgets:** critical CSS ≤60KB gz; vendor JS deferred, Three module lazy after `load`+idle; LCP (today title/numeral) <2.5s local; CLS <0.1 (reserved hero height, size-adjust fallback metrics, `font-display:swap`); Core <40k tris, DPR capped, loop paused offscreen/zen/tab-away; transform/opacity-only DOM animation; no per-frame state writes; will-change scoped + released.
- **Degradation ladder (decided in advance):** full → no-WebGL poster → no-GSAP static-but-authored → backend-down error scenes. A beautiful still beats a slow cinematic.

---

## 20. Implementation architecture

```
frontend/
├── index.html            # MODIFIED (M2+): css link order, importmap(three), vendor <script defer>, module boot
├── css/
│   ├── tokens.css        # M1: raw palette+OKLCH, semantic map, type/space/motion tokens
│   ├── base.css          # M1: reset, typography, grid, focus, scrollbar, grain/background utilities
│   ├── components.css    # M4: C1-C8 primitives + states
│   ├── views.css         # M3-M8: per-route signatures (hero, shell, dossiers, radar, verdict…)
│   ├── motion.css        # M4+: keyframes, RM edit, zen rules
│   └── app.css           # LEGACY: loaded LAST during migration; values remapped to vars at M1; deleted M11
└── js/
    ├── vendor/           # M2: gsap.min + plugins (UMD), three.module.min.js   [served via /js mount]
    ├── motion/           # M2+: lifecycle.js (context registry + switchView wrapper + render-then-animate hooks)
    │                     #      titles.js, tab-transitions.js, forge-sequence.js, numerals.js, micro.js, verdict.js, radar.js
    ├── three/            # M3: readiness-core.js + core-poster.svg
    ├── app.js            # MODIFIED view-by-view: inline style→classes, MotionHooks.afterRender(id) calls, NO id/behavior changes
    └── exam.js           # MODIFIED minimal: data-motion-ignore guards only; behavior untouched
```

**Lifecycle patterns:** (a) central `gsap.context` per view id; `switchView` wrapped → revert+rebuild; (b) **render-then-animate** — animations attach after innerHTML via explicit hooks, never before; (c) SplitText WeakMap registry, re-split on resize/replace; (d) matchMedia branches desktop/mobile/coarse/RM; (e) Three scene: init once after load+idle, IntersectionObserver+visibility+zen pause, debounced resize, dispose-safe; (f) `.timer-ring-*` + scroll containers carry `data-motion-ignore`; GSAP selectors strictly scoped.
**Migration rule:** never touch an innerHTML template's ids/contracts; add classes, grep-verify before removing anything; exam view last.
**Testing/screenshot strategy:** browser-use MCP at the viewport matrix; evidence stored under `design_research/recordings/` per milestone; console/network captured each milestone.

---

## 21. Milestones (each leaves the app runnable at localhost:8000)

**M0 — Source of truth** · Status: complete-pending-ratification · Outcome: this document · Steps: read frontend end-to-end → research refs/versions → decide direction → write schema-complete plan · Accept: §0-27 populated; no code changed · Evidence: this file.

**M1 — Tokens & type (zero-diff gate)** · Deps: M0 · Files: css/tokens.css, css/base.css, app.css remap, index.html font link upgrade (Archivo variable) · Steps: token layer 1:1 onto current values → replace hard-coded hex in app.css with vars → font axis upgrade → focus styles unified · Accept: side-by-side screenshots visually identical; specimen checklist passes; no console errors · Risks: token drift (mitigate: visual diff), CLS from axis swap (mitigate: size-adjust) · Rollback: revert css files.

**M2 — Vendor infra + lifecycle** · Deps: M1 · Files: js/vendor/*, motion/lifecycle.js, index.html scripts/importmap · Steps: download pinned GSAP+plugins+Three (record versions/licenses §23) → feature-detect guards → context registry + switchView wrapper + render-then-animate hooks · Accept: console clean, tabs switch, all data flows intact, guards proven by disabling-script test · Rollback: remove script tags.

**M3 — Vertical slice: Today** · Deps: M2 · Files: views.css(today), three/readiness-core.js, motion/titles.js+numerals.js, app.js hooks · Steps: hero band → Core (T3 states + poster + RM) → T1 title → T5 numerals → T11 pin → backgrounds BG1/BG1b → T10 reveals · Accept: storyboard frames captured; text-zone contrast pixel-sampled; GPU idle on tab-away; zen pause; other views untouched-looking; 6 viewports · Risks: canvas mount/z-index (layer map §12.3), dashboard data shape variance (defensive reads).

**M4 — Shell, nav, primitives** · Deps: M3 · Files: components.css, motion/micro.js+tab-transitions.js, views.css(shell) · Steps: wordmark (engraved + cell mark A9) → tab rail + Flip underline → C1-C8 with full state coverage → modals + focus trap → per-view base backgrounds · Accept: rapid tab-click clean; keyboard pass; all primitive states evidenced · Risks: renderer class hooks (grep before rename).

**M5 — Task views wave 1 (sources, updates, lawSources, review)** · Deps: M4 · Files: views.css, motion/radar.js, app.js renderer classes · Steps: ledger/dossier/board composites → C15/C16/C17/C18 → radar T8 → inline styles→classes → empty/error/loading scenes live · Accept: each flow smoke-tested via API; states evidenced; viz restyle (constellation/chronology) coherent.

**M6 — Essay + PYQ** · Deps: M5 · Files: views.css, app.js/exam.js class hooks only · Steps: desk composition → dials + ticker → dossiers + seals + Flip-into-shell · Accept: essay grade flow; PYQ filters/drills/history; RM variants.

**M7 — Exam system (highest risk, last of the functional views)** · Deps: M6 · Files: views.css(exam), motion/forge-sequence.js, exam.js guards · Steps: generator console re-skin (hidden selects intact) → T4 forge sequence (promise-bound) → instructions ritual T12 → shell silence styling → palette polish + bottom-sheet mobile → strict-lock + blink removal · Accept: full mock incl. strict mode; keyboard-only attempt; timer ring untouched; submit→analysis regression clean · Rollback: views.css section revert only.

**M8 — Verdict payoff** · Deps: M7 · Files: views.css(result), motion/verdict.js · Steps: verdict stage T7 (both paths) → viz cascade T15 → PYQ analysis reuse · Accept: storyboard T7; BELOW path dignity check; mobile cascade.

**M9 — Mobile re-direction** · Deps: M8 · Files: views.css mobile blocks, motion matchMedia branches · Steps: rail tabs → bottom-sheet palette → simplified Core → targets/safe-areas → delta matrix (§18) verified row by row · Accept: 375/390/412/768 + landscape; thumb-reach review; no hover dependencies.

**M10 — Reduced motion & low power** · Deps: M9 · Files: motion.css, matchMedia edits · Steps: RM pass of every timeline; blink gone; Core poster path; low-power DPR caps · Accept: RM captures per view; toggle on/off parity.

**M11 — Performance, finish, reconciliation** · Deps: M10 · Files: all; app.css deleted after grep-verification of legacy blocks · Steps: pixel-finish pass (master prompt §44 checklist) → anti-slop audit (§43) → Lighthouse/console/network → this plan reconciled (§22-27) → retrospective · Accept: §47 definition of complete, evidenced.

---

## 22. Progress log

- **2026-08-29:** Full strict read of all 4 frontend files + serving contract + research corpus. Versions verified (GSAP free-all-plugins; Three current; Archivo variable axes live). Direction T-A decided. Plan v2.0 written. Next: M1.

## 23. Decision log

| ID | Date | Decision | Alternatives | Rationale | Impacts |
|---|---|---|---|---|---|
| DL-01 | 2026-08-29 | Territory T-A over B/C | Dark Academia; warm editorial | §7 tests; exam-clock psychology | all |
| DL-02 | 2026-08-29 | Threshold Line as recurring grammar | Scattered motifs | One film, not stacked sections | §8/§13 |
| DL-03 | 2026-08-29 | Blink → steady critical timer | Keep blink | Photosensitivity §30 | C12 |
| DL-04 | 2026-08-29 | Vendor libs in js/vendor under /js mount | Add backend mount | Zero backend edits (constraint) | M2 |
| DL-05 | 2026-08-29 | Fonts stay Google-hosted variable | Self-host | Verified working; quota of effort | A1-A3 |
| DL-06 | 2026-08-29 | No photo/video assets | Stock/generated imagery | Domain is telemetry; §4.3 truth | A-manifest |

## 24. Surprises & discoveries

- The app already contains four authored data-viz systems (constellation, scatter, chronology, trend) + timer ring — the brand's graphic language was latent in the code; the plan elevates rather than invents.
- `app.css` carries ~200 lines of likely-dead "Week 6 TCS iON compat" styles (`.exam-header`, `.palette-grid`…) — M11 grep-verify before deletion.
- Citation modal lacks focus trap/Esc — logged as a11y fix M4.
- Git hazard: arena automations push to origin/main concurrently (memory 2026-08-28) — protocol D15.

## 25. Deviations & debt

| ID | Planned | Actual | Reason | Impact | Resolution | Status |
|---|---|---|---|---|---|---|
| (none yet — implementation gated) | | | | | | |

## 26. QA evidence

_(populated per milestone; required types: baseline+post screenshots @6 viewports, storyboard frames T3/T4/T7/T11, keyboard-only exam transcript, contrast pixel samples, RM capture set, console/network captures, Lighthouse M11, no-WebGL poster capture, mobile sheet/touch pass)_

## 27. Outcomes & retrospective

_(at M11: requirements completed vs §10 matrix; thesis achieved?; §45 final creative review answers with evidence; limitations; follow-ups: e.g., SEBI-mode visual parity check, future sound design explicitly out of scope)_

---

### Anti-slop self-audit of this plan (master prompt §43, run now)

- Not a centered-hero-plus-pills page: the app is a tabbed instrument; hero is a live data machine. ✓
- No repeated rounded-card grid: 4 distinct surface treatments + per-view compositions. ✓
- Display face is conceptually justified (gazette authority + kinetic width). ✓
- Entrances vary: lock-in stagger, clip-wipe, dial sweep, stamp slam, count-up — assigned by meaning. ✓
- Interest below the fold: panel ladder, radar, dossiers, verdict cascade. ✓
- Backgrounds authored per section with contrast protection. ✓
- 3D protagonist is product data made physical; fallback designed. ✓
- Copy stays real telemetry; verdicts keep their actual strings. ✓
- Mobile translates signatures (rail/sheet/dial/stamp), doesn't delete them. ✓
- Focus/touch/loading/error states are milestone acceptance criteria, not afterthoughts. ✓
- No low-contrast "premium gray" body text (muted ≥7:1; faint restricted). ✓
- No animated field crosses text unprotected (scrim gate at M3). ✓
- One tier leads at any moment (§16 hierarchy). ✓

### §45 commitments (to be answered with evidence at M11)

1 Idea: calibration across the cut-off. 2 Only-this-product: palette cells, threshold line, verdict stamps, section codes. 3 Coherence: tokens + lock-in grammar + threshold-line handoffs. 4 Quiet: exam shell, reading panes, pre-verdict beat. 5 Core = readiness made physical; evolves arrival→launch→return. 6 GSAP = ceremony of state change, not scroll decoration. 7 Mobile wow = verdict slam + bottom-sheet palette. 8 Backgrounds = staged environments with jobs. 9 Verified pairs §12.1 + Core worst-frame. 10 States C16-C18 + strict-lock + RM prove a product, not a mockup.
