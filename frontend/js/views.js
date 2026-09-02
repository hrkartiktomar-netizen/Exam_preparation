/* THE LEDGER — Secondary Views
   PYQ, Descriptive, Tracker, Updates, Review, Results.
   Each view loads data on first route entry, renders into DOM. */
(function () {
  "use strict";

  var API = window.LedgerAPI;
  var loaded = {};

  function qs(sel, ctx) { return (ctx || document).querySelector(sel); }
  function qsa(sel, ctx) { return Array.from((ctx || document).querySelectorAll(sel)); }

  /* Views build markup with innerHTML, and some interpolated values are
     externally generated (Gemini grading feedback, stored passage text), so
     anything not authored here is escaped before it reaches the DOM. */
  function esc(value) {
    return String(value == null ? "" : value)
      .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;").replace(/'/g, "&#39;");
  }

  function showLoading(container) {
    container.innerHTML = '<div class="loading-state"><div class="loading-state__ring"></div><div class="loading-state__text">Decoding ledger…</div></div>';
  }

  function showError(container, msg) {
    container.innerHTML = '<div class="error-state"><div class="error-state__message">' + msg + '</div><button class="error-state__retry">Retry</button></div>';
  }

  function showEmpty(container, msg) {
    container.innerHTML = '<div class="empty-state"><div class="empty-state__text">' + (msg || "No entries yet.") + '</div></div>';
  }

  /* ────── PYQ View ────── */
  async function loadPYQ() {
    if (loaded.pyq) return;
    var content = qs("#pyq-content");
    if (!content) return;

    showLoading(content);
    try {
      var papers = await API.pyqList();
      if (!papers || !papers.length) { showEmpty(content, "No previous year papers found."); return; }

      content.innerHTML =
        '<div class="view-eyebrow">§03 · PREVIOUS YEAR PAPERS · ' + papers.length + ' PAPERS</div>' +
        '<div class="pyq-view__grid" id="pyq-grid"></div>';

      var grid = qs("#pyq-grid", content);
      grid.innerHTML = papers.map(function (p) {
        return '<div class="pyq-card" data-doc-id="' + p.doc_id + '">' +
          '<div class="pyq-card__year">' + (p.year || "—") + '</div>' +
          '<div class="pyq-card__paper">' + (p.exam_type || "IFSCA") + ' · ' + (p.paper_type || "Paper I") + '</div>' +
          '<div class="pyq-card__meta"><span>' + (p.question_count || 0) + ' questions</span></div>' +
          '</div>';
      }).join("");

      qsa(".pyq-card", grid).forEach(function (card) {
        card.addEventListener("click", function () {
          loadPYQPaper(card.dataset.docId);
        });
      });

      loaded.pyq = true;
    } catch (err) {
      showError(content, err.message);
    }
  }

  async function loadPYQPaper(docId) {
    if (!API) return;
    try {
      var result = await API.pyqLoad(docId);
      if (result && result.exam_id) {
        window.LedgerRouter.navigate("exam");
      }
    } catch (err) {
      if (window.LedgerApp) window.LedgerApp.toast("Failed to load paper: " + err.message, "error");
    }
  }

  /* ────── Descriptive View ────── */
  async function loadDescriptive() {
    if (loaded.descriptive) return;
    var content = qs("#descriptive-content");
    if (!content) return;

    content.innerHTML =
      '<div class="view-eyebrow">§04 · DESCRIPTIVE PRACTICE</div>' +
      '<div class="descriptive-view__content">' +
        '<div class="descriptive-prompt" id="desc-prompt">' +
          '<div class="descriptive-prompt__type">ESSAY</div>' +
          '<div class="descriptive-prompt__text">Select an exam type and year to begin a descriptive practice session.</div>' +
        '</div>' +
        '<div style="display:flex;gap:var(--sp-4);margin-bottom:var(--sp-5);flex-wrap:wrap">' +
          '<select id="desc-exam" class="exam-setup__select"><option value="IFSCA">IFSCA Grade A</option><option value="SEBI">SEBI Grade A</option></select>' +
          '<select id="desc-year" class="exam-setup__select">' +
            '<option value="">AUTO — best gradable paper</option>' +
            '<option value="2025">2025</option>' +
            '<option value="2024">2024</option>' +
            '<option value="2023">2023</option>' +
          '</select>' +
          '<select id="desc-component" class="exam-setup__select" style="display:none"></select>' +
          '<button class="next-action__cta" id="desc-start">START SESSION</button>' +
        '</div>' +
        '<textarea class="descriptive-editor" id="desc-editor" placeholder="Begin writing your response here…" rows="12"></textarea>' +
        '<div class="descriptive-wordcount" id="desc-wordcount">0 WORDS</div>' +
        '<div style="margin-top:var(--sp-4);display:flex;gap:var(--sp-3)">' +
          '<button class="next-action__cta" id="desc-grade" style="display:none">SUBMIT FOR GRADING</button>' +
        '</div>' +
        '<div id="desc-result" style="margin-top:var(--sp-6)"></div>' +
      '</div>';

    var editor = qs("#desc-editor");
    var wordcount = qs("#desc-wordcount");
    var startBtn = qs("#desc-start");
    var gradeBtn = qs("#desc-grade");
    var resultEl = qs("#desc-result");
    var componentSel = qs("#desc-component");

    /* The sitting on screen. `year` is the one the backend resolved, which
       differs from the dropdown when AUTO picks the best gradable paper, and it
       has to be echoed back on grade -- the grade endpoint re-derives the paper
       from exam+year, so omitting it silently grades a different sitting. */
    var sitting = null;

    var COMPONENT_ORDER = ["essay", "precis", "rc"];
    var COMPONENT_FIELD = { essay: "essay_text", precis: "precis_text", rc: "rc_answers" };

    function activeKey() {
      return componentSel ? componentSel.value : "";
    }

    function activeComponent() {
      return (sitting && sitting.components && sitting.components[activeKey()]) || null;
    }

    function renderPrompt() {
      var promptEl = qs("#desc-prompt");
      var item = activeComponent();
      if (!promptEl || !item) return;
      qs(".descriptive-prompt__type", promptEl).textContent = item.item_type || "ESSAY";
      // Précis and RC refer to a passage; without it the item cannot be answered.
      var body = [item.prompt_text, item.passage_text].filter(Boolean).join("\n\n");
      qs(".descriptive-prompt__text", promptEl).textContent = body || "No prompt text for this item.";
    }

    function resetAnswer() {
      if (editor) editor.value = "";
      if (wordcount) wordcount.textContent = "0 WORDS";
      if (gradeBtn) gradeBtn.style.display = "none";
    }

    if (editor) {
      editor.addEventListener("input", function () {
        var words = editor.value.trim().split(/\s+/).filter(function (w) { return w.length > 0; });
        wordcount.textContent = words.length + " WORDS";
        if (gradeBtn) gradeBtn.style.display = words.length > 10 ? "" : "none";
      });
    }

    if (componentSel) {
      componentSel.addEventListener("change", function () {
        renderPrompt();
        resetAnswer();
        if (resultEl) resultEl.innerHTML = "";
      });
    }

    if (startBtn) {
      startBtn.addEventListener("click", async function () {
        try {
          var yearSel = qs("#desc-year");
          // "" is not a valid `int | None`, so AUTO must serialise as null.
          var year = yearSel.value ? Number(yearSel.value) : null;
          var result = await API.descriptiveStart(qs("#desc-exam").value, year);
          if (!result) return;
          sitting = result;

          // A sitting may omit components entirely (SEBI 2024 has no essay), so
          // the picker lists only what the backend actually returned.
          var components = result.components || {};
          var available = COMPONENT_ORDER.filter(function (key) { return components[key]; });
          if (componentSel) {
            componentSel.innerHTML = available.map(function (key) {
              var item = components[key];
              var marks = item.marks ? " · " + esc(item.marks) + " marks" : "";
              return '<option value="' + key + '">' + esc(item.item_type || key) + marks + '</option>';
            }).join("");
            componentSel.style.display = available.length > 1 ? "" : "none";
          }

          renderPrompt();
          resetAnswer();
          if (editor) editor.focus();
          if (resultEl) {
            resultEl.innerHTML =
              '<div class="view-eyebrow">§ ' + esc(result.exam) + ' ' + esc(result.year) +
              ' · ' + esc(result.time_limit_minutes) + ' MIN · CUT-OFF ' + esc(result.cutoff_pct) + '%</div>';
          }
        } catch (err) {
          if (window.LedgerApp) window.LedgerApp.toast(err.message, "error");
        }
      });
    }

    if (gradeBtn) {
      gradeBtn.addEventListener("click", async function () {
        if (!sitting || !activeComponent()) {
          if (window.LedgerApp) window.LedgerApp.toast("Start a session first.", "error");
          return;
        }
        try {
          gradeBtn.textContent = "GRADING…";
          gradeBtn.disabled = true;

          var field = COMPONENT_FIELD[activeKey()];
          var payload = { exam: sitting.exam, year: sitting.year };
          payload[field] = field === "rc_answers" ? [editor.value] : editor.value;

          var result = await API.descriptiveGrade(payload);
          if (!resultEl || !result) return;

          var graded = result.components || [];
          resultEl.innerHTML =
            '<div class="view-eyebrow">§ GRADING RESULT · ' + esc(result.total_score) + ' / ' + esc(result.total_max_marks) +
              ' · ' + (result.cleared_cutoff ? "CLEARED" : "BELOW") + ' CUT-OFF ' + esc(result.cutoff_pct) + '%</div>' +
            (graded.length
              ? '<div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(200px,1fr));gap:var(--sp-4)">' +
                graded.map(function (c) {
                  var max = c.max_marks || 0;
                  // Bars are a ratio of the item's own marks, which are 30/35
                  // here -- not a fixed 10-point scale.
                  var pct = max > 0 ? (((c.score || 0) / max) * 100).toFixed(1) : 0;
                  return '<div class="exam-results__topic"><div class="exam-results__topic-name">' + esc(c.component) + '</div>' +
                    '<div class="exam-results__bar"><div class="exam-results__bar-fill" style="width:' + pct + '%"></div></div>' +
                    '<div style="font-family:var(--f-mono);font-size:var(--fs-050);color:var(--ink-3);margin-top:var(--sp-1)">' +
                      esc(c.score) + '/' + esc(max) + '</div>' +
                    (c.feedback
                      ? '<p style="margin-top:var(--sp-3);color:var(--ink-2);font-size:var(--fs-200)">' + esc(c.feedback) + '</p>'
                      : '') +
                    '</div>';
                }).join("") +
                '</div>'
              : '<p style="margin-top:var(--sp-4);color:var(--ink-2)">This item has no stored model answer, so it cannot be graded.</p>');
        } catch (err) {
          if (window.LedgerApp) window.LedgerApp.toast(err.message, "error");
        } finally {
          gradeBtn.textContent = "SUBMIT FOR GRADING";
          gradeBtn.disabled = false;
        }
      });
    }

    loaded.descriptive = true;
  }

  /* ────── Tracker View ────── */
  async function loadTracker() {
    if (loaded.tracker) return;
    var content = qs("#tracker-content");
    if (!content) return;

    showLoading(content);
    try {
      var results = await Promise.allSettled([API.weakTopics(), API.srsDue()]);
      var weakTopics = results[0].status === "fulfilled" ? results[0].value : [];
      var srsDue = results[1].status === "fulfilled" ? results[1].value : [];

      var topics = Array.isArray(weakTopics) ? weakTopics : weakTopics.topics || [];

      content.innerHTML =
        '<div class="view-eyebrow">§05 · TOPIC TRACKER · ' + topics.length + ' TOPICS</div>' +
        '<div class="heat-grid" id="heat-grid"></div>' +
        '<div class="rule"></div>' +
        '<div class="view-eyebrow">SRS DUE · ' + (Array.isArray(srsDue) ? srsDue.length : 0) + ' ITEMS</div>' +
        '<div class="srs-list" id="srs-list"></div>';

      // Heat grid
      var grid = qs("#heat-grid", content);
      if (grid && topics.length) {
        grid.innerHTML = topics.map(function (t) {
          var score = t.weakness_score || t.accuracy || 0;
          var heat = score < 30 ? "critical" : (score < 50 ? "weak" : (score < 70 ? "medium" : "strong"));
          return '<div class="heat-grid__cell" data-heat="' + heat + '">' +
            '<div class="heat-grid__cell-label">' + (t.topic_name || t.topic || "—").substring(0, 20) + '</div>' +
            '<div class="heat-grid__cell-score">' + Math.round(score) + '%</div>' +
            '</div>';
        }).join("");
      }

      // SRS list
      var srsList = qs("#srs-list", content);
      if (srsList && Array.isArray(srsDue) && srsDue.length) {
        srsList.innerHTML = srsDue.map(function (item) {
          return '<div class="srs-item">' +
            '<span class="srs-item__topic">' + (item.topic || item.topic_name || "—") + '</span>' +
            '<span class="srs-item__due">' + (item.due_date || "TODAY") + '</span>' +
            '</div>';
        }).join("");
      }

      loaded.tracker = true;
    } catch (err) {
      showError(content, err.message);
    }
  }

  /* ────── Updates View ────── */
  async function loadUpdates() {
    if (loaded.updates) return;
    var content = qs("#updates-content");
    if (!content) return;

    showLoading(content);
    try {
      var updates = await API.updates("date_desc");
      var items = Array.isArray(updates) ? updates : updates.updates || [];

      content.innerHTML =
        '<div class="view-eyebrow">§06 · AMENDMENT INTELLIGENCE · ' + items.length + ' UPDATES</div>' +
        '<div class="updates-controls">' +
          '<button class="updates-btn updates-btn--primary" id="run-tracker">RUN TRACKER</button>' +
          '<button class="updates-btn" id="startup-scan">STARTUP SCAN</button>' +
          '<button class="updates-btn" id="enrich-reasons">ENRICH REASONS</button>' +
        '</div>' +
        '<div class="amendment-log" id="amendment-log"></div>';

      var log = qs("#amendment-log", content);
      if (log) {
        log.innerHTML = items.slice(0, 50).map(function (u) {
          var verdict = (u.verification_status || u.status || "pending").toLowerCase();
          var dateStr = u.discovered_at || u.date || "";
          if (dateStr) dateStr = dateStr.substring(0, 10);
          return '<div class="amendment-entry">' +
            '<span class="amendment-entry__date">' + dateStr + '</span>' +
            '<span class="amendment-entry__text">' + (u.title || u.summary || "—") + '</span>' +
            '<span class="amendment-entry__chip" data-verdict="' + verdict + '">' + verdict.toUpperCase() + '</span>' +
            '</div>';
        }).join("");
      }

      // Button handlers
      var runBtn = qs("#run-tracker", content);
      if (runBtn) runBtn.addEventListener("click", async function () {
        runBtn.textContent = "RUNNING…"; runBtn.disabled = true;
        try { await API.updatesRun(); if (window.LedgerApp) window.LedgerApp.toast("Tracker run started.", "success"); }
        catch (e) { if (window.LedgerApp) window.LedgerApp.toast(e.message, "error"); }
        finally { runBtn.textContent = "RUN TRACKER"; runBtn.disabled = false; }
      });

      var scanBtn = qs("#startup-scan", content);
      if (scanBtn) scanBtn.addEventListener("click", async function () {
        scanBtn.textContent = "SCANNING…"; scanBtn.disabled = true;
        try { await API.startupScan(true); if (window.LedgerApp) window.LedgerApp.toast("Scan complete.", "success"); }
        catch (e) { if (window.LedgerApp) window.LedgerApp.toast(e.message, "error"); }
        finally { scanBtn.textContent = "STARTUP SCAN"; scanBtn.disabled = false; }
      });

      var enrichBtn = qs("#enrich-reasons", content);
      if (enrichBtn) enrichBtn.addEventListener("click", async function () {
        enrichBtn.textContent = "ENRICHING…"; enrichBtn.disabled = true;
        try { await API.enrichReasons(); if (window.LedgerApp) window.LedgerApp.toast("Reasons enriched.", "success"); }
        catch (e) { if (window.LedgerApp) window.LedgerApp.toast(e.message, "error"); }
        finally { enrichBtn.textContent = "ENRICH REASONS"; enrichBtn.disabled = false; }
      });

      loaded.updates = true;
    } catch (err) {
      showError(content, err.message);
    }
  }

  /* ────── Review View ────── */
  async function loadReview() {
    if (loaded.review) return;
    var content = qs("#review-content");
    if (!content) return;

    showLoading(content);
    try {
      var data = await API.wrongQueue(30);
      var items = Array.isArray(data) ? data : data.wrong_answers || [];

      if (!items.length) { showEmpty(content, "No wrong answers yet. Take a mock to populate."); return; }

      content.innerHTML =
        '<div class="view-eyebrow">§07 · WRONG QUEUE · ' + items.length + ' ITEMS</div>' +
        '<div id="wrong-list"></div>';

      var list = qs("#wrong-list", content);
      list.innerHTML = items.map(function (item, i) {
        return '<div class="wrong-item" data-idx="' + i + '">' +
          '<div class="wrong-item__header">' +
            '<div class="wrong-item__question">' + (item.question_text || item.text || "Question " + (i + 1)) + '</div>' +
            '<span class="wrong-item__toggle">▼</span>' +
          '</div>' +
          '<div class="wrong-item__body"><div class="wrong-item__detail">' +
            '<div class="wrong-item__correct">✓ ' + (item.correct_option || "—") + '</div>' +
            '<div style="color:var(--ink-2);font-size:var(--fs-200)">' +
              '<strong>Your answer:</strong> ' + (item.your_option || "—") +
            '</div>' +
            (item.topic ? '<div class="wrong-item__topic">' + item.topic + '</div>' : '') +
            (item.source_document ? '<div class="wrong-item__source">' + item.source_document + '</div>' : '') +
          '</div></div>' +
          '</div>';
      }).join("");

      qsa(".wrong-item__header", list).forEach(function (header) {
        header.addEventListener("click", function () {
          header.parentElement.classList.toggle("is-open");
        });
      });

      loaded.review = true;
    } catch (err) {
      showError(content, err.message);
    }
  }

  /* ────── Results View ────── */
  async function loadResults() {
    if (loaded.results) return;
    var content = qs("#results-content");
    if (!content) return;

    showLoading(content);
    try {
      var timeline = await API.timeline();
      var entries = Array.isArray(timeline) ? timeline : timeline.entries || [];

      if (!entries.length) { showEmpty(content, "No exam history yet. Complete a mock to see results."); return; }

      content.innerHTML =
        '<div class="view-eyebrow">§08 · EXAMINATION RESULTS · ' + entries.length + ' ENTRIES</div>' +
        '<div class="results-timeline" id="results-timeline"></div>' +
        '<div class="results-gate" id="results-gate"></div>';

      // Timeline bars
      var timelineEl = qs("#results-timeline", content);
      var maxScore = Math.max.apply(null, entries.map(function (e) { return e.score || e.percentage || 0; }));
      timelineEl.innerHTML = entries.map(function (e) {
        var pct = maxScore > 0 ? ((e.score || e.percentage || 0) / maxScore) * 100 : 0;
        var pass = pct >= 60;
        return '<div class="results-bar" ' + (pass ? 'data-pass' : 'data-fail') + ' style="height:' + Math.max(pct, 4) + '%">' +
          '<span class="results-bar__label">' + (e.date || "").substring(5, 10) + '</span>' +
          '</div>';
      }).join("");

      // Gate vis
      var gateEl = qs("#results-gate", content);
      var lastEntry = entries[entries.length - 1] || {};
      var p1 = lastEntry.paper1_score || lastEntry.score || 0;
      var p2 = lastEntry.paper2_score || 0;
      var agg = p1 + p2;
      gateEl.innerHTML =
        '<div class="results-gate__item"><div class="results-gate__value" ' + (p1 >= 40 ? 'data-pass' : 'data-fail') + '>' + p1 + '</div><div class="results-gate__label">PAPER I</div></div>' +
        '<div class="results-gate__item"><div class="results-gate__value" ' + (p2 >= 40 ? 'data-pass' : 'data-fail') + '>' + p2 + '</div><div class="results-gate__label">PAPER II</div></div>' +
        '<div class="results-gate__item"><div class="results-gate__value" ' + (agg >= 130 ? 'data-pass' : 'data-fail') + '>' + agg + '</div><div class="results-gate__label">AGGREGATE</div></div>';

      loaded.results = true;
    } catch (err) {
      showError(content, err.message);
    }
  }

  /* ────── Route-aware loading ────── */
  function onRoute(route) {
    switch (route) {
      case "pyq": loadPYQ(); break;
      case "descriptive": loadDescriptive(); break;
      case "tracker": loadTracker(); break;
      case "updates": loadUpdates(); break;
      case "review": loadReview(); break;
      case "results": loadResults(); break;
    }
  }

  function init() {
    if (window.LedgerRouter) {
      window.LedgerRouter.onRoute(onRoute);
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
