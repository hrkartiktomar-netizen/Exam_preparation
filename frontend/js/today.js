/* THE LEDGER — Today View · The cinematic scroll route.
   Cold Open → Premise → Next Action → Ticker → Statute Path →
   Proof → Quiet Beat → Burst → Finale.
   Each section pulls real data from the backend API. */
(function () {
  "use strict";

  var API = null;
  var dashData = null;
  var readinessData = null;
  var lawData = null;
  var initialized = false;

  /* ────── Utility ────── */
  function qs(sel, ctx) { return (ctx || document).querySelector(sel); }
  function qsa(sel, ctx) { return Array.from((ctx || document).querySelectorAll(sel)); }
  function el(tag, cls, html) {
    var e = document.createElement(tag);
    if (cls) e.className = cls;
    if (html) e.innerHTML = html;
    return e;
  }

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

  /* ────── A06: Next Action Card ────── */
  function renderNextAction(data) {
    var card = qs(".next-action__card");
    if (!card || !data) return;

    var priority = "low";                                  // ≤5 · emerald
    if (data.priority_score >= 10) priority = "critical";  // 10 · red
    else if (data.priority_score >= 8) priority = "high";  // 8-9 · amber
    else if (data.priority_score >= 6) priority = "medium"; // 6-7 · brass

    card.dataset.priority = priority;
    var eyebrow = qs(".next-action__eyebrow", card);
    var title = qs(".next-action__title", card);
    var reason = qs(".next-action__reason", card);
    var cta = qs(".next-action__cta", card);

    if (eyebrow) eyebrow.textContent = "§ NEXT ACTION · PRIORITY " + (data.priority_score || "—");
    if (title) title.textContent = (data.action || "STUDY") + " · " + (data.topic || "General");
    if (reason) reason.textContent = data.reason || "Based on your current progress.";
    if (cta) {
      var route = "today";
      if (data.action === "MOCK" || data.action === "DRILL_CRITICAL") route = "exam";
      else if (data.action === "ESSAY") route = "descriptive";
      else if (data.action === "AMENDMENT_REVIEW") route = "updates";
      cta.dataset.view = route;
      cta.textContent = "→ " + data.action;
    }
  }

  /* ────── A07: Module Constellation ────── */
  function renderConstellation(stats) {
    var svg = qs(".constellation__svg");
    if (!svg || !stats || !stats.length) return;

    var w = 700, h = 440;
    svg.setAttribute("viewBox", "0 0 " + w + " " + h);
    svg.innerHTML = "";

    // Deterministic ring layout — same data, same sky, every render
    var nodes = stats.map(function (t, i) {
      var angle = (i / stats.length) * Math.PI * 2;
      var radius = 150 + (i % 3) * 30;
      return {
        x: w / 2 + Math.cos(angle) * radius,
        y: h / 2 + Math.sin(angle) * radius,
        r: Math.max(8, (t.target_score || 0.3) * 28),
        topic: t.topic_name || t.topic || "Topic " + i,
        status: t.status || "medium",
        score: t.accuracy_pct || 0,
      };
    });

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

    // Draw nodes
    var statusColors = {
      critical: "var(--danger)", weak: "var(--warn)",
      medium: "var(--metal)", strong: "var(--signal)"
    };

    nodes.forEach(function (n) {
      var g = document.createElementNS("http://www.w3.org/2000/svg", "g");

      var circle = document.createElementNS("http://www.w3.org/2000/svg", "circle");
      circle.setAttribute("cx", n.x); circle.setAttribute("cy", n.y);
      circle.setAttribute("r", n.r);
      circle.setAttribute("fill", statusColors[n.status] || "var(--metal)");
      circle.setAttribute("opacity", "0.7");
      g.appendChild(circle);

      var text = document.createElementNS("http://www.w3.org/2000/svg", "text");
      text.setAttribute("x", n.x); text.setAttribute("y", n.y + n.r + 14);
      text.setAttribute("text-anchor", "middle");
      text.setAttribute("fill", "var(--ink-3)");
      text.setAttribute("font-family", "var(--f-mono)");
      text.setAttribute("font-size", "8");
      text.setAttribute("letter-spacing", "0.05em");
      text.textContent = n.topic.substring(0, 18).toUpperCase();
      g.appendChild(text);

      svg.appendChild(g);
    });

    // GSAP entrance
    if (typeof gsap !== "undefined") {
      gsap.from(svg.querySelectorAll("circle"), {
        attr: { r: 0 }, opacity: 0, duration: 0.8,
        stagger: 0.04, ease: "power3.out",
        scrollTrigger: { trigger: svg, start: "top 80%" }
      });
      gsap.from(svg.querySelectorAll("line"), {
        attr: { x2: function (i, t) { return t.getAttribute("x1"); }, y2: function (i, t) { return t.getAttribute("y1"); } },
        opacity: 0, duration: 0.6, stagger: 0.02, ease: "power2.out",
        scrollTrigger: { trigger: svg, start: "top 80%" }
      });
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
    }
  }

  /* ────── A08: Ticker Tape ────── */
  function renderTicker(data) {
    var track = qs(".ticker__track");
    if (!track || !data) return;

    var items = [
      { label: "READINESS", value: (data.readiness_percentage || 0) + "%" },
      { label: "MOCKS", value: String(data.total_mocks || 0) },
      { label: "ACCURACY", value: (data.overall_accuracy || 0).toFixed(1) + "%" },
      { label: "AMENDMENTS", value: String(data.pending_amendments || 0) },
      { label: "SRS DUE", value: String(data.srs_due || 0) },
      { label: "QUESTIONS", value: String(data.total_attempts || 0) },
    ];

    // Duplicate for seamless loop
    var html = "";
    for (var r = 0; r < 2; r++) {
      items.forEach(function (item, i) {
        html += '<div class="ticker__item">';
        if (i > 0 || r > 0) html += '<div class="ticker__dot"></div>';
        html += '<span class="ticker__label">' + item.label + '</span>';
        html += '<span class="ticker__value">' + item.value + '</span>';
        html += '</div>';
      });
    }
    track.innerHTML = html;

    // M13 · flash the freshly printed values
    if (typeof gsap !== "undefined" && !(window.LedgerMotion && window.LedgerMotion.isReduced)) {
      gsap.fromTo(qsa(".ticker__value", track),
        { opacity: 0.3 },
        { opacity: 1, duration: 0.5, stagger: 0.04, ease: "power2.out", overwrite: "auto" }
      );
    }

    // Pause button
    var pauseBtn = qs(".ticker__pause");
    if (pauseBtn) {
      pauseBtn.addEventListener("click", function () {
        var paused = track.dataset.paused === "true";
        track.dataset.paused = paused ? "false" : "true";
        pauseBtn.textContent = paused ? "PAUSE" : "PLAY";
      });
    }
  }

  /* ────── A09: Statute Path ────── */
  var STATUTES = [
    { num: "§01", title: "NOTIFY", subtitle: "The amendment radar never sleeps.",
      desc: "An autonomous agent discovers regulatory changes from the IFSCA, SEBI, and RBI gazette systems. It corroborates, extracts reasons, and persists VERIFIED or CONTRADICTED verdicts overnight." },
    { num: "§02", title: "STUDY", subtitle: "The Act, one ruled slice a day.",
      desc: "The IFSCA Act 2019, sliced into 80-line daily portions with SM-2 spaced repetition. Completion-driven: your day index only advances when you stamp the day complete." },
    { num: "§03", title: "MOCK", subtitle: "Sit the hall before it sits you.",
      desc: "Smart mock generation: targeting-weighted question allocation across 22 topics, with TCS-iON-faithful interface, server-held timer, and negative marking." },
    { num: "§04", title: "REVIEW", subtitle: "Every wrong answer is a deposition.",
      desc: "Your wrong queue: each missed question paired with its source chunk citation from the knowledge pack. Replay drills target your weakest areas." },
    { num: "§05", title: "SEAL", subtitle: "Aggregate, cutoff, stamp.",
      desc: "Paper II gates Paper I — if either falls below its cut-off, readiness drops to ≤25% regardless of aggregate. The seal strikes only when both papers pass independently." },
  ];

  function initStatutePath() {
    var panels = qs(".statute-path__panels");
    if (!panels) return;

    STATUTES.forEach(function (s, i) {
      var panel = el("div", "statute-path__panel" + (i === 0 ? " is-active" : ""));
      panel.innerHTML =
        '<div class="statute-path__statute-num">' + s.num + ' ' + s.title + '</div>' +
        '<h3 class="statute-path__title">' + s.subtitle + '</h3>' +
        '<p class="statute-path__desc">' + s.desc + '</p>';
      panels.appendChild(panel);
    });

    if (typeof gsap === "undefined" || typeof ScrollTrigger === "undefined") return;

    var section = qs(".statute-path");
    if (!section) return;

    var panelEls = qsa(".statute-path__panel", panels);
    var ringFill = qs(".statute-path__ring-fill");
    var ringNum = qs(".statute-path__ring-num");
    var totalStates = STATUTES.length;

    var lastStateIdx = -1;
    var canPin = window.LedgerMotion && !window.LedgerMotion.isReduced &&
      window.matchMedia("(min-width: 641px)").matches;

    var cfg = {
      trigger: section,
      start: "top top",
      end: "bottom bottom",
      scrub: 0.8,
      onUpdate: function (self) {
        var progress = self.progress;
        var stateIdx = Math.min(Math.floor(progress * totalStates), totalStates - 1);

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

        // Update panels
        panelEls.forEach(function (p, i) {
          if (i === stateIdx) {
            p.classList.add("is-active");
          } else {
            p.classList.remove("is-active");
          }
        });

        // Update ring
        if (ringFill) {
          var dashOffset = 283 - (283 * progress);
          ringFill.style.strokeDashoffset = dashOffset;
        }
        if (ringNum) {
          ringNum.textContent = STATUTES[stateIdx].num + " " + STATUTES[stateIdx].title;
        }
      }
    };
    if (canPin) {
      cfg.pin = qs(".statute-path__pin");
      cfg.pinSpacing = false;
      cfg.anticipatePin = 1;
    }
    ScrollTrigger.create(cfg);
  }

  /* ────── A10-A12: Proof Section ────── */
  function renderProof(data) {
    // Scatter plot
    var scatterEl = qs("[data-chart='scatter'] svg");
    if (scatterEl && data.recent_attempts && data.recent_attempts.length) {
      var w = 500, h = 250;
      scatterEl.setAttribute("viewBox", "0 0 " + w + " " + h);
      scatterEl.innerHTML = "";

      // Axes
      var xAxis = document.createElementNS("http://www.w3.org/2000/svg", "line");
      xAxis.setAttribute("x1", 40); xAxis.setAttribute("y1", h - 30);
      xAxis.setAttribute("x2", w - 10); xAxis.setAttribute("y2", h - 30);
      xAxis.setAttribute("stroke", "var(--rule-strong)"); xAxis.setAttribute("stroke-width", "1");
      scatterEl.appendChild(xAxis);

      var yAxis = document.createElementNS("http://www.w3.org/2000/svg", "line");
      yAxis.setAttribute("x1", 40); yAxis.setAttribute("y1", 10);
      yAxis.setAttribute("x2", 40); yAxis.setAttribute("y2", h - 30);
      yAxis.setAttribute("stroke", "var(--rule-strong)"); yAxis.setAttribute("stroke-width", "1");
      scatterEl.appendChild(yAxis);

      // Dots
      var maxTime = Math.max.apply(null, data.recent_attempts.map(function (a) { return a.time_spent || 60; }));
      data.recent_attempts.forEach(function (a) {
        var cx = 50 + ((a.time_spent || 30) / maxTime) * (w - 70);
        var cy = a.is_correct ? 40 + Math.random() * 60 : 160 + Math.random() * 50;
        var dot = document.createElementNS("http://www.w3.org/2000/svg", "circle");
        dot.setAttribute("cx", cx); dot.setAttribute("cy", cy);
        dot.setAttribute("r", "4");
        dot.setAttribute("fill", a.is_correct ? "var(--signal)" : "var(--danger)");
        dot.setAttribute("opacity", "0.6");
        scatterEl.appendChild(dot);
      });
    }

    // Sparkline
    var sparkEl = qs("[data-chart='sparkline'] svg");
    if (sparkEl && data.score_history && data.score_history.length > 1) {
      var sw = 500, sh = 150;
      sparkEl.setAttribute("viewBox", "0 0 " + sw + " " + sh);
      sparkEl.innerHTML = "";

      var scores = data.score_history;
      var maxScore = Math.max.apply(null, scores.map(function (s) { return s.score || 0; }));
      var points = scores.map(function (s, i) {
        var x = 20 + (i / (scores.length - 1)) * (sw - 40);
        var y = sh - 20 - ((s.score || 0) / (maxScore || 1)) * (sh - 40);
        return x + "," + y;
      }).join(" ");

      var polyline = document.createElementNS("http://www.w3.org/2000/svg", "polyline");
      polyline.setAttribute("points", points);
      polyline.setAttribute("fill", "none");
      polyline.setAttribute("stroke", "var(--signal)");
      polyline.setAttribute("stroke-width", "2");
      polyline.setAttribute("stroke-linecap", "round");
      polyline.setAttribute("stroke-linejoin", "round");
      sparkEl.appendChild(polyline);
    }
  }

  /* ────── A13: Quiet Beat ────── */
  function renderQuietBeat(lawData) {
    var textEl = qs(".quiet-beat__text");
    if (!textEl || !lawData) return;

    var text = lawData.daily_text || lawData.text || lawData.content || "Today's law revision content will appear here when available.";

    // Wrap each word for ghost→solid effect
    var words = text.split(/\s+/);
    textEl.innerHTML = words.map(function (w) {
      return '<span class="ghost-word">' + w + '</span>';
    }).join(" ");

    var eyebrow = qs(".quiet-beat__eyebrow");
    if (eyebrow) {
      var dayLines = (lawData.line_end != null && lawData.line_start != null)
        ? (lawData.line_end - lawData.line_start + 1)
        : (lawData.lines_count || 0);
      eyebrow.textContent = "§ DAILY ACT REVISION · DAY " + (lawData.day_index || 1) + " · " + dayLines + " LINES";
    }

    // Ghost→solid scroll scrub
    if (typeof gsap !== "undefined" && typeof ScrollTrigger !== "undefined") {
      var ghostWords = qsa(".ghost-word", textEl);
      if (ghostWords.length) {
        ScrollTrigger.create({
          trigger: textEl,
          start: "top 70%",
          end: "bottom 30%",
          scrub: 0.5,
          onUpdate: function (self) {
            var progress = self.progress;
            var litCount = Math.floor(progress * ghostWords.length);
            ghostWords.forEach(function (w, i) {
              if (i < litCount) {
                w.classList.add("is-lit");
              } else {
                w.classList.remove("is-lit");
              }
            });
          }
        });
      }
    }
  }

  /* ────── A15: Burst — Data-true particle field ────── */
  var burstParticles = null;
  var burstSize = { w: 0, h: 0 };
  var burstCounted = false;
  var burstTopicStats = null; // /api/topics/stats rows: {topic_id, accuracy_pct, total_attempts}

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
    var stats = Array.isArray(burstTopicStats) ? burstTopicStats : [];
    var total = (data && data.total_questions_attempted) || 0;
    var cap = (window.LedgerMotion && window.LedgerMotion.isFull) ? 220 : 60;
    var n = Math.min(total, cap);
    if (n <= 0 || !stats.length) return [];

    var sumAttempts = stats.reduce(function (s, t) { return s + (t.total_attempts || 0); }, 0) || 1;
    var particles = [];
    stats.forEach(function (t) {
      var share = Math.round(((t.total_attempts || 0) / sumAttempts) * n);
      var correct = Math.round(share * ((t.accuracy_pct || 0) / 100));
      for (var j = 0; j < share && particles.length < n; j++) {
        var i = particles.length;
        var jitter = ((i * 37) % 40) - 20;
        particles.push({
          x: ((i + 0.5) / n) * w + jitter,
          y: (j < correct ? 0.3 : 0.7) * h + (((i * 53) % 40) - 20),
          r: 1.5 + ((i * 13) % 10) / 4,
          alpha: 0.35 + ((i * 29) % 45) / 100,
          color: j < correct ? "#37C092" : "#FF4D5E",
          phase: ((i * 53) % 360) * Math.PI / 180,
        });
      }
    });
    return particles;
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
    var totalAttempts = data.total_questions_attempted || 0;
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

  /* ────── Data Loading ────── */
  async function loadData() {
    API = window.LedgerAPI;
    if (!API) return;

    try {
      // Parallel data fetch
      var results = await Promise.allSettled([
        API.dashboard(),
        API.readiness(130, 28),
        API.nextAction(),
        API.topicStats(),
        API.lawDaily(),
      ]);

      dashData = results[0].status === "fulfilled" ? results[0].value : null;
      readinessData = results[1].status === "fulfilled" ? results[1].value : null;
      var nextActionData = results[2].status === "fulfilled" ? results[2].value : null;
      var topicData = results[3].status === "fulfilled" ? results[3].value : null;
      lawData = results[4].status === "fulfilled" ? results[4].value : null;

      // A01: Counter
      var readinessPercent = 0;
      if (readinessData && readinessData.readiness_percentage != null) {
        readinessPercent = readinessData.readiness_percentage;
      } else if (dashData && dashData.readiness_percentage != null) {
        readinessPercent = dashData.readiness_percentage;
      }
      var counterContainer = qs(".splitflap");
      if (counterContainer) animateCounter(counterContainer, readinessPercent);
      document.dispatchEvent(new CustomEvent("ledger:readiness", { detail: { percent: readinessPercent } }));

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

      // A06: Next Action
      renderNextAction(nextActionData);

      // A07: Constellation
      if (topicData) {
        renderConstellation(Array.isArray(topicData) ? topicData : topicData.topics || []);
      }

      // A08: Ticker
      if (dashData) renderTicker(dashData);

      // A13: Quiet Beat
      renderQuietBeat(lawData);

      // A10-A12: Proof
      if (dashData) renderProof(dashData);

      // A15: Burst
      burstTopicStats = topicData ? (Array.isArray(topicData) ? topicData : topicData.topics || []) : [];
      if (dashData) renderBurst(dashData);

    } catch (err) {
      console.error("[today] data load error:", err);
    }
  }

  /* ────── Init ────── */
  function init() {
    if (initialized) return;
    initialized = true;

    initStatutePath();
    loadData();

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

    // Reveal animations for sections
    if (typeof gsap !== "undefined" && typeof ScrollTrigger !== "undefined") {
      qsa(".reveal").forEach(function (el) {
        ScrollTrigger.create({
          trigger: el,
          start: "top 85%",
          onEnter: function () { el.classList.add("is-visible"); },
          onLeaveBack: function () { el.classList.remove("is-visible"); },
        });
      });
    }
  }

  // Structural markers exist before any motion attaches — must precede the
  // route replay below, which runs init()'s .reveal loop synchronously.
  injectChapterMarkers();

  if (window.LedgerMotion && typeof window.LedgerMotion.register === "function") {
    window.LedgerMotion.register(attachWordReveals);
    window.LedgerMotion.register(attachPointerTilt);
  }

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
})();
