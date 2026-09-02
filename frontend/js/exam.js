/* THE LEDGER — TCS-iON Examination Console (A17, A18)
   Server-held timer. Five-state palette. Keyboard navigation.
   Post-exam staggered score reveal. */
(function () {
  "use strict";

  var API = window.LedgerAPI;
  var examState = null; // { id, questions, currentIdx, answers, states, timerInterval }
  var starting = false; // in-flight guard for startExam (B6)

  function qs(sel, ctx) { return (ctx || document).querySelector(sel); }
  function qsa(sel, ctx) { return Array.from((ctx || document).querySelectorAll(sel)); }

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

      examState = {
        id: result.exam_id,
        questions: result.questions || [],
        currentIdx: 0,
        answers: {},
        states: {},
        timerInterval: null,
      };
      starting = false; // examState now guards re-entry

      // Initialize all states to NOT_VISITED
      examState.questions.forEach(function (q, i) {
        examState.states[i] = STATES.NOT_VISITED;
      });
      if (examState.questions.length > 0) {
        examState.states[0] = STATES.NOT_ANSWERED;
      }

      showLiveConsole();
      startTimer();
      renderQuestion(0);
      renderPalette();

    } catch (err) {
      starting = false;
      if (window.LedgerApp && window.LedgerApp.toast) {
        window.LedgerApp.toast("Failed to start exam: " + err.message, "error");
      }
    }
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
    var timerEl = qs(".exam-bar__timer");

    examState.timerInterval = setInterval(async function () {
      try {
        var timeData = await API.examTime(examState.id);
        var remaining = timeData.remaining_seconds || 0;

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

        if (remaining <= 0) {
          clearInterval(examState.timerInterval);
          submitExam();
        }
      } catch (e) { /* timer fetch failed, will retry */ }
    }, 1000);
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
      var letters = ["A", "B", "C", "D"];
      optionsEl.innerHTML = options.map(function (opt, i) {
        var selected = examState.answers[idx] === i;
        return '<div class="exam-option' + (selected ? ' is-selected' : '') + '" data-option="' + i + '">' +
          '<span class="exam-option__letter">' + letters[i] + '</span>' +
          '<span class="exam-option__text">' + (opt.text || opt) + '</span>' +
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
      } else if (e.key >= "1" && e.key <= "4") {
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
  async function submitExam() {
    if (!examState || !API) return;
    clearInterval(examState.timerInterval);

    try {
      var result = await API.examSubmit(examState.id, examState.answers);
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

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
