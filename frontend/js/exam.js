/* THE LEDGER — TCS-iON Examination Console (A17, A18)
   Server-held timer. Five-state palette. Keyboard navigation.
   Post-exam staggered score reveal. */
(function () {
  "use strict";

  var API = window.LedgerAPI;
  var examState = null; // { id, kind, questions, currentIdx, answers, states, spent, timeLimitMinutes, timerInterval }
  var starting = false; // in-flight guard for startExam (B6)

  function qs(sel, ctx) { return (ctx || document).querySelector(sel); }
  function qsa(sel, ctx) { return Array.from((ctx || document).querySelectorAll(sel)); }

  var LETTERS = ["A", "B", "C", "D", "E"];

  function esc(value) {
    return String(value == null ? "" : value)
      .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;").replace(/'/g, "&#39;");
  }

  /* An option's own label, not its position. 401 of the 1024 complete bank rows
     are missing a middle option and 399 have no option A at all, so position and
     label disagree on ~39% of PYQ questions -- grading a click by position marks
     a right answer wrong. Position is only a fallback for options that arrive as
     bare strings. */
  function labelOf(opt, i) {
    if (opt == null) return null;
    if (typeof opt === "object" && opt.label) return opt.label;
    return LETTERS[i] || null;
  }

  var STATES = {
    NOT_VISITED: "not-visited",
    NOT_ANSWERED: "not-answered",
    ANSWERED: "answered",
    MARKED: "marked",
    MARKED_ANSWERED: "marked-answered",
  };

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

  async function startExam() {
    if (!API) return;
    if (examState || starting) return; // re-entry guard (B6)
    starting = true;

    var examSelect = qs("#exam-type");
    var countInput = qs("#exam-count");
    var body = {
      exam_type: examSelect ? examSelect.value : "IFSCA",
      question_count: countInput ? parseInt(countInput.value, 10) || 50 : 50,
      allocation_mode: "targeting_weighted",
    };

    try {
      var result = await API.examsStart(body);
      if (!result || !result.exam_id) throw new Error("No exam ID returned");

      starting = false; // examState now guards re-entry
      beginSession(result.exam_id, result.questions, {
        kind: "mock",
        timeLimitMinutes: result.time_limit_minutes,
      });

    } catch (err) {
      starting = false;
      if (window.LedgerApp && window.LedgerApp.toast) {
        window.LedgerApp.toast("Failed to start exam: " + err.message, "error");
      }
    }
  }

  /* Enter the live console with an already-fetched session. Shared by the smart
     mock (fetched here) and PYQ papers/sittings/drills (fetched by views.js),
     because both responses carry the same question shape: question_id,
     question_text and options of {label, text}. */
  function beginSession(id, questions, opts) {
    var o = opts || {};
    var list = questions || [];

    examState = {
      id: id,
      kind: o.kind || "mock",
      questions: list,
      currentIdx: 0,
      answers: {},
      states: {},
      spent: {},
      timeLimitMinutes: o.timeLimitMinutes || null,
      timerInterval: null,
    };

    // Initialize all states to NOT_VISITED
    list.forEach(function (q, i) {
      examState.states[i] = STATES.NOT_VISITED;
    });
    if (list.length > 0) {
      examState.states[0] = STATES.NOT_ANSWERED;
    }

    showLiveConsole();
    startTimer();
    renderQuestion(0);
    renderPalette();
  }

  /* ────── Live Console ────── */
  function showLiveConsole() {
    var setup = qs(".exam-setup");
    var live = qs(".exam-live");
    if (setup) setup.style.display = "none";
    if (live) live.classList.add("is-active");

    // Disable smooth scroll during exam
    if (window.LedgerSmooth) window.LedgerSmooth.stop();
  }

  function hideLiveConsole() {
    var setup = qs(".exam-setup");
    var live = qs(".exam-live");
    if (setup) setup.style.display = "";
    if (live) live.classList.remove("is-active");

    if (window.LedgerSmooth) window.LedgerSmooth.start();
  }

  /* ────── Timer ────── */
  function startTimer() {
    if (!examState) return;
    var state = examState;
    var timerEl = qs(".exam-bar__timer");

    // The mock's clock is server-held and authoritative. A PYQ session has no
    // server clock to poll -- /api/exams/{id}/time-remaining resolves a mock_id,
    // so asking it about a PYQ id would 404 once a second for the whole attempt
    // -- so it counts down locally from the limit the session was served with.
    // Decided by kind, not by the presence of a limit: mock responses carry
    // time_limit_minutes too, and must keep polling the server.
    var localRemaining = null;
    if (state.kind === "pyq") {
      localRemaining = (state.timeLimitMinutes || 60) * 60;
    }
    if (localRemaining !== null) paintTimer(timerEl, localRemaining);

    state.timerInterval = setInterval(async function () {
      state.spent[state.currentIdx] = (state.spent[state.currentIdx] || 0) + 1;

      var remaining;
      if (localRemaining !== null) {
        localRemaining -= 1;
        remaining = localRemaining;
      } else {
        try {
          var timeData = await API.examTime(state.id);
          remaining = timeData.remaining_seconds || 0;
        } catch (e) {
          return; // timer fetch failed, will retry
        }
      }

      paintTimer(timerEl, remaining);

      if (remaining <= 0) {
        clearInterval(state.timerInterval);
        submitExam();
      }
    }, 1000);
  }

  function paintTimer(timerEl, remaining) {
    var h = Math.floor(remaining / 3600);
    var m = Math.floor((remaining % 3600) / 60);
    var s = remaining % 60;
    var display = String(h).padStart(2, "0") + ":" +
                  String(m).padStart(2, "0") + ":" +
                  String(s).padStart(2, "0");

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
  }

  /* ────── Render Question ────── */
  function renderQuestion(idx) {
    if (!examState || !examState.questions[idx]) return;
    examState.currentIdx = idx;

    var q = examState.questions[idx];
    var numEl = qs(".exam-question__num");
    var textEl = qs(".exam-question__text");
    var optionsEl = qs(".exam-options");

    if (numEl) numEl.textContent = "QUESTION " + (idx + 1) + " OF " + examState.questions.length;
    if (textEl) textEl.textContent = q.question_text || q.text || "";

    if (optionsEl) {
      var options = q.options || [];
      optionsEl.innerHTML = options.map(function (opt, i) {
        var selected = examState.answers[idx] === i;
        return '<div class="exam-option' + (selected ? ' is-selected' : '') + '" data-option="' + i + '">' +
          '<span class="exam-option__letter">' + esc(labelOf(opt, i)) + '</span>' +
          '<span class="exam-option__text">' + esc(opt && opt.text ? opt.text : opt) + '</span>' +
          '</div>';
      }).join("");

      qsa(".exam-option", optionsEl).forEach(function (optEl) {
        optEl.addEventListener("click", function () {
          var optIdx = parseInt(optEl.dataset.option, 10);
          selectOption(idx, optIdx);
        });
      });
    }

    // Mark as visited
    if (examState.states[idx] === STATES.NOT_VISITED) {
      examState.states[idx] = STATES.NOT_ANSWERED;
    }

    updatePaletteHighlight();
  }

  function selectOption(qIdx, optIdx) {
    if (!examState || !examState.questions[qIdx]) return;
    // The keyboard path passes a raw digit, so it can name an option this
    // question does not have. Recording it anyway showed no selection but still
    // submitted a letter that does not exist, grading the question wrong.
    var options = examState.questions[qIdx].options || [];
    if (optIdx < 0 || optIdx >= options.length) return;

    examState.answers[qIdx] = optIdx;

    var state = examState.states[qIdx];
    if (state === STATES.MARKED || state === STATES.MARKED_ANSWERED) {
      examState.states[qIdx] = STATES.MARKED_ANSWERED;
    } else {
      examState.states[qIdx] = STATES.ANSWERED;
    }

    // Update UI
    qsa(".exam-option").forEach(function (el, i) {
      el.classList.toggle("is-selected", i === optIdx);
    });
    renderPalette();
  }

  /* ────── Controls ────── */
  function initControls() {
    var saveNext = qs(".exam-btn--save");
    var markReview = qs(".exam-btn--mark");
    var clearResp = qs(".exam-btn--clear");
    var prevBtn = qs(".exam-btn--prev");
    var nextBtn = qs(".exam-btn--next");
    var submitBtn = qs(".exam-btn--submit");

    if (saveNext) saveNext.addEventListener("click", function () {
      if (examState && examState.currentIdx < examState.questions.length - 1) {
        renderQuestion(examState.currentIdx + 1);
        renderPalette();
      }
    });

    if (markReview) markReview.addEventListener("click", function () {
      if (!examState) return;
      var idx = examState.currentIdx;
      var state = examState.states[idx];
      if (state === STATES.ANSWERED || state === STATES.MARKED_ANSWERED) {
        examState.states[idx] = STATES.MARKED_ANSWERED;
      } else {
        examState.states[idx] = STATES.MARKED;
      }
      renderPalette();
      if (idx < examState.questions.length - 1) renderQuestion(idx + 1);
    });

    if (clearResp) clearResp.addEventListener("click", function () {
      if (!examState) return;
      var idx = examState.currentIdx;
      delete examState.answers[idx];
      var state = examState.states[idx];
      if (state === STATES.MARKED_ANSWERED) {
        examState.states[idx] = STATES.MARKED;
      } else {
        examState.states[idx] = STATES.NOT_ANSWERED;
      }
      qsa(".exam-option").forEach(function (el) { el.classList.remove("is-selected"); });
      renderPalette();
    });

    if (prevBtn) prevBtn.addEventListener("click", function () {
      if (examState && examState.currentIdx > 0) {
        renderQuestion(examState.currentIdx - 1);
      }
    });

    if (nextBtn) nextBtn.addEventListener("click", function () {
      if (examState && examState.currentIdx < examState.questions.length - 1) {
        renderQuestion(examState.currentIdx + 1);
      }
    });

    if (submitBtn) submitBtn.addEventListener("click", function () {
      if (confirm("Submit this exam? You cannot change answers after submission.")) {
        submitExam();
      }
    });

    // Keyboard
    document.addEventListener("keydown", function (e) {
      if (!examState || !qs(".exam-live.is-active")) return;
      if (e.key === "ArrowRight" || e.key === "n") {
        if (examState.currentIdx < examState.questions.length - 1) renderQuestion(examState.currentIdx + 1);
      } else if (e.key === "ArrowLeft" || e.key === "p") {
        if (examState.currentIdx > 0) renderQuestion(examState.currentIdx - 1);
      } else if (e.key >= "1" && e.key <= "5") {
        selectOption(examState.currentIdx, parseInt(e.key, 10) - 1);
      }
    });
  }

  /* ────── Palette ────── */
  function renderPalette() {
    var grid = qs(".exam-palette__grid");
    if (!grid || !examState) return;

    grid.innerHTML = examState.questions.map(function (q, i) {
      var state = examState.states[i] || STATES.NOT_VISITED;
      return '<button class="exam-palette__cell" data-state="' + state + '" data-idx="' + i + '">' +
        (i + 1) + '</button>';
    }).join("");

    qsa(".exam-palette__cell", grid).forEach(function (cell) {
      cell.addEventListener("click", function () {
        renderQuestion(parseInt(cell.dataset.idx, 10));
      });
    });

    updatePaletteHighlight();
  }

  function updatePaletteHighlight() {
    qsa(".exam-palette__cell").forEach(function (cell) {
      var idx = parseInt(cell.dataset.idx, 10);
      cell.style.outline = idx === examState.currentIdx ? "2px solid #1a3a5c" : "";
    });
  }

  /* ────── Submit ────── */

  /* Both submit endpoints take the same MockSubmitRequestModel: a LIST of
     {question_id, selected_answer, time_spent_seconds, marked_for_review}.
     examState.answers holds positional option indexes keyed by question index,
     which that model rejects outright, so the payload has to be rebuilt from the
     questions rather than posted as-is. */
  function buildAnswers() {
    return examState.questions.map(function (q, i) {
      var chosen = examState.answers[i];
      var state = examState.states[i];
      return {
        question_id: q.question_id,
        selected_answer: chosen === undefined
          ? null
          : labelOf((q.options || [])[chosen], chosen),
        time_spent_seconds: examState.spent[i] || 0,
        marked_for_review: state === STATES.MARKED || state === STATES.MARKED_ANSWERED,
      };
    });
  }

  async function submitExam() {
    if (!examState || !API) return;
    clearInterval(examState.timerInterval);

    try {
      var answers = buildAnswers();
      var result = examState.kind === "pyq"
        ? await API.pyqSubmit(examState.id, answers)
        : await API.examSubmit(examState.id, answers);
      hideLiveConsole();
      renderResults(result);
    } catch (err) {
      if (window.LedgerApp && window.LedgerApp.toast) {
        window.LedgerApp.toast("Submission error: " + err.message, "error");
      }
    }
  }

  /* ────── A18: Results ────── */
  function renderResults(result) {
    var resultsEl = qs(".exam-results");
    if (!resultsEl) return;
    resultsEl.style.display = "block";

    var scoreNum = qs(".exam-results__score-num", resultsEl);
    var scoreLabel = qs(".exam-results__score-label", resultsEl);
    var topicsGrid = qs(".exam-results__topics", resultsEl);

    var total = result.final_score || 0;
    var maxScore = result.max_score || examState.questions.length;

    if (scoreNum) {
      if (typeof gsap !== "undefined") {
        var obj = { val: 0 };
        gsap.to(obj, {
          val: total,
          duration: 1.5,
          ease: "power2.out",
          onUpdate: function () { scoreNum.textContent = Math.round(obj.val) + " / " + maxScore; }
        });
      } else {
        scoreNum.textContent = total + " / " + maxScore;
      }
    }

    if (scoreLabel) {
      // accuracy_pct is correct/total; final_score is net of negative marking,
      // so deriving the percentage from the score overstates every wrong answer.
      var pct = (result.accuracy_pct || 0).toFixed(1);
      scoreLabel.textContent = pct + "% ACCURACY · " + examState.questions.length + " QUESTIONS";
    }

    // Topic breakdown
    if (topicsGrid && result.topic_breakdown) {
      topicsGrid.innerHTML = result.topic_breakdown.map(function (t) {
        var pct = t.total > 0 ? Math.round((t.correct / t.total) * 100) : 0;
        var level = pct < 40 ? "data-low" : (pct < 70 ? "data-mid" : "");
        return '<div class="exam-results__topic">' +
          '<div class="exam-results__topic-name">' + (t.topic || "Unknown") + ' · ' + t.correct + '/' + t.total + '</div>' +
          '<div class="exam-results__bar"><div class="exam-results__bar-fill" ' + level + ' style="width:' + pct + '%"></div></div>' +
          '</div>';
      }).join("");

      // Staggered entrance
      if (typeof gsap !== "undefined") {
        gsap.from(qsa(".exam-results__topic", topicsGrid), {
          opacity: 0, y: 16, duration: 0.5,
          stagger: 0.08, ease: "power3.out", delay: 0.8,
        });
      }
    }

    examState = null;
  }

  /* ────── Init ────── */
  function init() {
    initSetup();
    initControls();
  }

  /* Hand an already-fetched bank session to the console. Returns false when an
     attempt is in flight or the session is not renderable, so the caller can say
     why nothing happened instead of silently navigating to an empty console. */
  function startSession(session) {
    if (examState || starting) return false;
    if (!session || !session.pyq_id) return false;
    if (!session.questions || !session.questions.length) return false;

    beginSession(session.pyq_id, session.questions, {
      kind: "pyq",
      timeLimitMinutes: session.time_limit_minutes,
    });
    return true;
  }

  window.LedgerExam = {
    startSession: startSession,
    isActive: function () { return !!examState; },
  };

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
