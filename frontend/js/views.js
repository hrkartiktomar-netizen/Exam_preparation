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

  /* msg is a runtime err.message at every call site -- server-supplied detail
     text -- so it is escaped here rather than at each of them. The button is
     rendered only when the caller supplies something to retry: it is styled in
     views.css but was never bound, so it used to render as a dead control. */
  function showError(container, msg, retry) {
    container.innerHTML =
      '<div class="error-state"><div class="error-state__message">' + esc(msg) + '</div>' +
      (retry ? '<button class="error-state__retry" type="button">Retry</button>' : '') +
      '</div>';

    if (!retry) return;
    var btn = qs(".error-state__retry", container);
    if (btn) btn.addEventListener("click", retry);
  }

  function showEmpty(container, msg) {
    container.innerHTML = '<div class="empty-state"><div class="empty-state__text">' + (msg || "No entries yet.") + '</div></div>';
  }

  /* For a request that succeeded and returned no rows. showError would render
     that as a raw status string on an otherwise empty screen, and inventing an
     empty panel for a *failed* request is worse: it made a missing endpoint read
     as a deliberately blank tab. This keeps the section eyebrow so the route
     still reads as the view it is, and turns the blank into an invitation.
     hint and cta are optional; the button is only rendered when the caller
     supplies a label, mirroring showError's retry contract. */
  function showEmptyView(container, eyebrow, message, hint, cta) {
    container.innerHTML =
      '<div class="view-eyebrow">' + esc(eyebrow) + '</div>' +
      '<div class="empty-state">' +
        '<div class="empty-state__text">' + esc(message) + '</div>' +
        (hint ? '<div class="empty-state__hint">' + esc(hint) + '</div>' : '') +
        (cta && cta.label ? '<button class="updates-btn empty-state__cta" type="button">' + esc(cta.label) + '</button>' : '') +
      '</div>';

    if (!cta || !cta.onClick) return;
    var btn = qs(".empty-state__cta", container);
    if (btn) btn.addEventListener("click", cta.onClick);
  }

  /* ────── PYQ View ────── */

  /* Three ways into the bank, because they are not interchangeable: a paper is
     one (exam, year, phase, paper) tuple; a sitting is every row for one
     (year, phase), which spans exams and papers; a drill is one subject across
     all years and exams. /api/pyq/list publishes the papers and the subject
     enum -- the sittings are the distinct (year, phase) pairs among those
     papers, so no second request is needed to offer them. */
  function sittingsFrom(papers) {
    var seen = {};
    var sittings = [];
    papers.forEach(function (p) {
      var key = p.year + ":" + p.phase;
      if (seen[key]) {
        seen[key].question_count += p.question_count || 0;
        return;
      }
      seen[key] = { year: p.year, phase: p.phase, question_count: p.question_count || 0 };
      sittings.push(seen[key]);
    });
    return sittings.sort(function (a, b) {
      return (b.year - a.year) || (a.phase - b.phase);
    });
  }

  /* subject_id arrives as SUBJ_COMMERCE_ACCOUNTS and the card wants COMMERCE
     ACCOUNTS. Deliberately not title-cased: SUBJ_GA would render as "Ga". */
  function prettySubject(subjectId) {
    return String(subjectId || "").replace(/^SUBJ_/, "").replace(/_/g, " ");
  }

  /* The cards are divs, not buttons, so they need an explicit role and key
     binding to be reachable without a mouse. */
  function activate(el, fn) {
    el.setAttribute("role", "button");
    el.setAttribute("tabindex", "0");
    el.addEventListener("click", fn);
    el.addEventListener("keydown", function (e) {
      if (e.key === "Enter" || e.key === " ") {
        e.preventDefault();
        fn();
      }
    });
  }

  function toast(msg, kind) {
    if (window.LedgerApp && window.LedgerApp.toast) window.LedgerApp.toast(msg, kind);
  }

  /* Enter the examination console with a fetched bank session.

     The in-flight check runs BEFORE the fetch, not after. Each of these
     endpoints caches its answers under the pyq_id it mints, so fetching while an
     attempt is live can overwrite the key that attempt will be graded against. */
  async function openPYQSession(fetchSession, label) {
    if (!API) return;
    if (!window.LedgerExam) {
      toast("Examination console unavailable", "error");
      return;
    }
    if (window.LedgerExam.isActive()) {
      toast("Finish or submit the attempt in progress first", "error");
      return;
    }

    try {
      var session = await fetchSession();
      // Start before navigating: showView skips its Flip transition when
      // .exam-live is already active, which is the intended hall entrance.
      if (!window.LedgerExam.startSession(session)) {
        throw new Error("the console could not open this session");
      }
      window.LedgerRouter.navigate("exam");
    } catch (err) {
      toast("Failed to load " + label + ": " + err.message, "error");
    }
  }

  async function loadPYQ() {
    if (loaded.pyq) return;
    var content = qs("#pyq-content");
    if (!content) return;

    showLoading(content);
    try {
      var payload = await API.pyqList();
      // {status, papers, subjects} -- not a bare array, so testing the response
      // itself for .length always fell through to the empty state.
      var papers = (payload && payload.papers) || [];
      var subjects = (payload && payload.subjects) || [];
      var sittings = sittingsFrom(papers);

      if (!papers.length && !subjects.length) {
        showEmpty(content, "No previous year papers found.");
        return;
      }

      content.innerHTML =
        '<div class="pyq-view__group">' +
          '<div class="view-eyebrow">§03 · PREVIOUS YEAR PAPERS · ' + papers.length + ' PAPERS</div>' +
          '<div class="pyq-view__grid" id="pyq-grid"></div>' +
        '</div>' +
        (sittings.length
          ? '<div class="pyq-view__group">' +
              '<div class="view-eyebrow">FULL SITTINGS · ' + sittings.length + '</div>' +
              '<div class="pyq-view__grid" id="pyq-sittings"></div>' +
            '</div>'
          : '') +
        (subjects.length
          ? '<div class="pyq-view__group">' +
              '<div class="view-eyebrow">SUBJECT DRILLS · ' + subjects.length + '</div>' +
              '<div class="pyq-view__grid" id="pyq-subjects"></div>' +
            '</div>'
          : '');

      var grid = qs("#pyq-grid", content);
      if (grid) {
        grid.innerHTML = papers.map(function (p) {
          return '<div class="pyq-card" data-doc-id="' + esc(p.pyq_doc_id) + '">' +
            '<div class="pyq-card__year">' + esc(p.year) + '</div>' +
            '<div class="pyq-card__paper">' + esc(p.exam) + ' · Phase ' + esc(p.phase) +
              ' · Paper ' + esc(p.paper) + '</div>' +
            '<div class="pyq-card__meta"><span>' + esc(p.question_count) + ' questions</span>' +
              (p.incomplete_count
                ? '<span>' + esc(p.incomplete_count) + ' incomplete</span>'
                : '') +
            '</div>' +
            '</div>';
        }).join("");

        qsa(".pyq-card", grid).forEach(function (card) {
          activate(card, function () { loadPYQPaper(card.dataset.docId); });
        });
      }

      var sittingGrid = qs("#pyq-sittings", content);
      if (sittingGrid) {
        sittingGrid.innerHTML = sittings.map(function (s) {
          return '<div class="pyq-card" data-year="' + esc(s.year) + '" data-phase="' + esc(s.phase) + '">' +
            '<div class="pyq-card__year">' + esc(s.year) + '</div>' +
            '<div class="pyq-card__paper">Full sitting · Phase ' + esc(s.phase) + '</div>' +
            '<div class="pyq-card__meta"><span>' + esc(s.question_count) + ' in bank</span></div>' +
            '</div>';
        }).join("");

        qsa(".pyq-card", sittingGrid).forEach(function (card) {
          var year = parseInt(card.dataset.year, 10);
          var phase = parseInt(card.dataset.phase, 10);
          activate(card, function () {
            openPYQSession(
              function () { return API.pyqSitting(year, phase); },
              year + " Phase " + phase + " sitting"
            );
          });
        });
      }

      var subjectGrid = qs("#pyq-subjects", content);
      if (subjectGrid) {
        subjectGrid.innerHTML = subjects.map(function (s) {
          return '<div class="pyq-card" data-subject="' + esc(s.subject_id) + '">' +
            '<div class="pyq-card__year">' + esc(prettySubject(s.subject_id)) + '</div>' +
            '<div class="pyq-card__paper">Subject drill</div>' +
            '<div class="pyq-card__meta"><span>' + esc(s.question_count) + ' questions</span></div>' +
            '</div>';
        }).join("");

        qsa(".pyq-card", subjectGrid).forEach(function (card) {
          var subjectId = card.dataset.subject;
          activate(card, function () {
            openPYQSession(
              function () { return API.pyqDrill(subjectId, { limit: 20 }); },
              prettySubject(subjectId) + " drill"
            );
          });
        });
      }

      loaded.pyq = true;
    } catch (err) {
      showError(content, err.message, loadPYQ);
    }
  }

  async function loadPYQPaper(docId) {
    // The session carries pyq_id, never exam_id -- gating on the latter meant a
    // successful load navigated nowhere.
    return openPYQSession(function () { return API.pyqLoad(docId); }, "paper " + docId);
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
          // A topic that was never sat is unmeasured, not failing -- without this
          // distinction a fresh install reads as eight red critical 0% cells.
          var unmeasured = t.status === "UNKNOWN" || !t.attempts;
          var heat = unmeasured ? "unmeasured"
            : (score < 30 ? "critical" : (score < 50 ? "weak" : (score < 70 ? "medium" : "strong")));
          return '<div class="heat-grid__cell" data-heat="' + heat + '">' +
            '<div class="heat-grid__cell-label">' + esc((t.topic_name || t.topic || "—").substring(0, 20)) + '</div>' +
            '<div class="heat-grid__cell-score">' + (unmeasured ? "NOT SIT" : Math.round(score) + "%") + '</div>' +
            '</div>';
        }).join("");
      }

      // SRS list
      var srsList = qs("#srs-list", content);
      if (srsList && Array.isArray(srsDue) && srsDue.length) {
        srsList.innerHTML = srsDue.map(function (item) {
          // display_name is nullable (get_due_topics LEFT JOINs topics), so
          // topic_id is a real fallback rather than dead weight. due_at is a full
          // ISO timestamp, hence the same date slice §06 uses.
          return '<div class="srs-item">' +
            '<span class="srs-item__topic">' + esc(item.display_name || item.topic_id) + '</span>' +
            '<span class="srs-item__due">' + esc(item.due_at.substring(0, 10)) + '</span>' +
            '</div>';
        }).join("");
      }

      loaded.tracker = true;
    } catch (err) {
      showError(content, err.message, loadTracker);
    }
  }

  /* ────── Corpus source reader ──────
     One overlay, rebuilt per open. The markdown is written with textContent,
     never parsed into HTML: the corpus is OCR output, so injecting it would be
     an XSS surface and would collapse the whitespace that makes it readable. */
  var readerOverlay = null;
  var readerOnKey = null;

  function closeSourceReader() {
    if (!readerOverlay) return;
    if (readerOnKey) document.removeEventListener("keydown", readerOnKey);
    readerOnKey = null;
    readerOverlay.remove();
    readerOverlay = null;
    if (window.LedgerSmooth && window.LedgerSmooth.start) window.LedgerSmooth.start();
  }

  async function openSourceReader(name) {
    closeSourceReader();

    var overlay = document.createElement("div");
    overlay.className = "doc-reader";
    overlay.setAttribute("role", "dialog");
    overlay.setAttribute("aria-modal", "true");
    overlay.setAttribute("aria-label", "Source document " + name);
    // hall-paper is the warm cream palette, applied to the sheet rather than the
    // backdrop: the scene also redefines --scrim, which would wash out the veil
    // behind it. journey.js crossfades only #view-today [data-scene], so this
    // attribute drives the static palette and nothing else.
    overlay.innerHTML =
      '<div class="doc-reader__panel" data-scene="hall-paper">' +
        '<div class="doc-reader__bar">' +
          '<span class="doc-reader__title">' + esc(name) + '</span>' +
          '<button class="doc-reader__close" type="button">CLOSE ✕</button>' +
        '</div>' +
        '<div class="doc-reader__meta">OPENING…</div>' +
        '<div class="doc-reader__body"></div>' +
      '</div>';
    document.body.appendChild(overlay);
    readerOverlay = overlay;
    if (window.LedgerSmooth && window.LedgerSmooth.stop) window.LedgerSmooth.stop();

    var closeBtn = qs(".doc-reader__close", overlay);
    if (closeBtn) closeBtn.addEventListener("click", closeSourceReader);
    overlay.addEventListener("click", function (e) {
      if (e.target === overlay) closeSourceReader();
    });
    readerOnKey = function (e) { if (e.key === "Escape") closeSourceReader(); };
    document.addEventListener("keydown", readerOnKey);

    var body = qs(".doc-reader__body", overlay);
    var meta = qs(".doc-reader__meta", overlay);
    try {
      var doc = await API.corpusDocument(name);
      if (!readerOverlay) return; // closed while the fetch was in flight
      meta.textContent = doc.bucket + " · " + doc.lines + " LINES · " + doc.bytes + " BYTES";
      body.textContent = doc.text;
    } catch (err) {
      if (!readerOverlay) return;
      meta.textContent = "SOURCE UNAVAILABLE";
      body.textContent = "Could not open " + name + ": " + err.message;
    }
  }

  /* The curated ledger has no "before" side to show: every surviving row carries
     a NULL old_value, so the delta renders one column and says what it is rather
     than inventing a prior text to differ against. */
  function amendmentDetailHtml(u) {
    var oldText = u.old_value;
    var newText = u.new_value || u.summary || "";
    var delta = "";

    if (oldText) {
      delta +=
        '<div class="amendment-delta__col amendment-delta__col--old">' +
          '<span class="amendment-delta__label">WAS</span>' +
          '<p class="amendment-delta__text">' + esc(oldText) + '</p>' +
        '</div>';
    }
    if (newText) {
      delta +=
        '<div class="amendment-delta__col amendment-delta__col--new">' +
          '<span class="amendment-delta__label">' + (oldText ? "NOW" : "AS FILED") + '</span>' +
          '<p class="amendment-delta__text">' + esc(newText) + '</p>' +
        '</div>';
    }
    if (!delta) delta = '<p class="amendment-delta__text">No text recorded for this row.</p>';

    var facts = [];
    if (u.topic_id) facts.push(u.topic_id);
    if (u.update_date) facts.push("EFFECTIVE " + String(u.update_date).substring(0, 10));
    if (u.category) facts.push(u.category);

    return '<div class="amendment-delta' + (oldText ? ' amendment-delta--paired' : '') + '">' + delta + '</div>' +
      (facts.length
        ? '<div class="amendment-entry__facts">' + facts.map(function (f) { return esc(f); }).join(" · ") + '</div>'
        : '');
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
      // The tracker feed and the curated corpus are different provenance; without
      // a marker, rows the tracker never discovered read as its output.
      var sourceTag = updates && updates.source === "corpus" ? " · CURATED LEDGER" : "";

      content.innerHTML =
        '<div class="view-eyebrow">§06 · AMENDMENT INTELLIGENCE · ' + items.length + ' UPDATES' + sourceTag + '</div>' +
        '<div class="updates-controls">' +
          '<button class="updates-btn updates-btn--primary" id="run-tracker">RUN TRACKER</button>' +
          '<button class="updates-btn" id="startup-scan">STARTUP SCAN</button>' +
          '<button class="updates-btn" id="enrich-reasons">ENRICH REASONS</button>' +
        '</div>' +
        '<div class="amendment-log" id="amendment-log"></div>';

      var log = qs("#amendment-log", content);
      if (log) {
        if (!items.length) {
          // Into the log slot rather than `content`, so the eyebrow and the three
          // action buttons above stay live -- RUN TRACKER is how this fills up.
          showEmptyView(log, "TRACKER FEED · EMPTY",
            "The amendment ledger has not been opened yet.",
            "Regulatory updates from IFSCA & SEBI collect here once the tracker is wired to the ledger.");
        } else {
          log.innerHTML = items.slice(0, 50).map(function (u, i) {
            var verdict = esc((u.verification_status || u.status || "pending").toLowerCase());
            var dateStr = u.discovered_at || u.date || "";
            if (dateStr) dateStr = dateStr.substring(0, 10);
            // source_urls_json is a list on both feeds; the corpus maps the row's
            // single source_url into it. The store takes a bare basename, which is
            // exactly the shape the curated rows already hold.
            var srcs = Array.isArray(u.source_urls_json) ? u.source_urls_json.filter(Boolean) : [];
            var src = srcs.length ? String(srcs[0]) : "";
            return '<div class="amendment-entry" data-idx="' + i + '">' +
              '<span class="amendment-entry__date">' + esc(dateStr) + '</span>' +
              '<span class="amendment-entry__text">' + esc(u.title || u.summary || "—") + '</span>' +
              '<span class="amendment-entry__tools">' +
                '<span class="amendment-entry__chip" data-verdict="' + verdict + '">' + verdict.toUpperCase() + '</span>' +
                '<button class="amendment-entry__btn" type="button" data-act="detail" aria-expanded="false">DETAIL</button>' +
                (src
                  ? '<button class="amendment-entry__btn amendment-entry__btn--source" type="button" data-act="source" data-src="' + esc(src) + '">READ SOURCE</button>'
                  : '') +
              '</span>' +
              '<div class="amendment-entry__detail"></div>' +
            '</div>';
          }).join("");

          // One delegated listener for every row: details are built on first open
          // so fifty rows do not each pay for markup nobody reads.
          log.addEventListener("click", function (e) {
            var btn = e.target && e.target.closest ? e.target.closest("[data-act]") : null;
            if (!btn || !log.contains(btn)) return;

            if (btn.dataset.act === "source") {
              openSourceReader(btn.dataset.src);
              return;
            }

            var entry = btn.closest(".amendment-entry");
            if (!entry) return;
            var detail = qs(".amendment-entry__detail", entry);
            if (!detail) return;
            var open = entry.classList.toggle("is-open");
            btn.setAttribute("aria-expanded", open ? "true" : "false");
            if (open && !detail.dataset.filled) {
              var row = items[Number(entry.dataset.idx)];
              detail.innerHTML = row ? amendmentDetailHtml(row) : "";
              detail.dataset.filled = "1";
            }
          });
        }
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
      showError(content, err.message, loadUpdates);
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

      if (!items.length) {
        showEmptyView(content, "§07 · WRONG QUEUE",
          "Nothing to review — no wrong answers banked yet.",
          "Sit a mock and every missed question queues here for replay.",
          {
            label: "GO TO EXAM",
            onClick: function () { if (window.LedgerRouter) window.LedgerRouter.navigate("exam"); }
          });
        return;
      }

      content.innerHTML =
        '<div class="view-eyebrow">§07 · WRONG QUEUE · ' + items.length + ' ITEMS</div>' +
        '<div id="wrong-list"></div>';

      var list = qs("#wrong-list", content);
      list.innerHTML = items.map(function (item, i) {
        return '<div class="wrong-item" data-idx="' + i + '">' +
          '<div class="wrong-item__header">' +
            '<div class="wrong-item__question">' + esc(item.question_text || item.text || "Question " + (i + 1)) + '</div>' +
            '<span class="wrong-item__toggle">▼</span>' +
          '</div>' +
          '<div class="wrong-item__body"><div class="wrong-item__detail">' +
            '<div class="wrong-item__correct">✓ ' + esc(item.correct_option || "—") + '</div>' +
            '<div style="color:var(--ink-2);font-size:var(--fs-200)">' +
              '<strong>Your answer:</strong> ' + esc(item.your_option || "—") +
            '</div>' +
            (item.topic ? '<div class="wrong-item__topic">' + esc(item.topic) + '</div>' : '') +
            (item.source_document ? '<div class="wrong-item__source">' + esc(item.source_document) + '</div>' : '') +
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
      showError(content, err.message, loadReview);
    }
  }

  /* ────── Results View ────── */

  /* The two post-attempt PYQ endpoints compose: /api/pyq/analytics lists the
     last ten completed attempts and yields their pyq_ids, and
     /api/pyq/{id}/answers reveals the model answers for one of them. The reveal
     is fetched on first expand, not up front -- ten attempts of up to 50
     questions each is a lot of payload for a list the user may never open. */
  function renderPyqAttempts(container, attempts) {
    container.innerHTML =
      '<div class="view-eyebrow">PYQ ATTEMPTS · ' + attempts.length + ' RECORDED</div>' +
      attempts.map(function (a) {
        var attempted = a.questions_attempted || 0;
        var correct = a.correct_count || 0;
        return '<div class="wrong-item" data-pyq-id="' + esc(a.pyq_id) + '">' +
          '<div class="wrong-item__header">' +
            '<div class="wrong-item__question">' + esc(a.pyq_title || a.pyq_id) + '</div>' +
            '<span class="wrong-item__toggle">▼</span>' +
          '</div>' +
          '<div class="wrong-item__body"><div class="wrong-item__detail">' +
            '<div class="wrong-item__correct">' + correct + ' / ' + attempted + ' CORRECT</div>' +
            '<div class="wrong-item__topic">SCORE ' + esc(a.score) + ' · ACCURACY ' + esc(a.accuracy) + '%</div>' +
            '<div class="wrong-item__source">Expand to reveal the model answers</div>' +
          '</div></div>' +
          '</div>';
      }).join("");

    qsa(".wrong-item__header", container).forEach(function (header) {
      header.addEventListener("click", function () {
        var item = header.parentElement;
        item.classList.toggle("is-open");
        if (item.classList.contains("is-open") && !item.dataset.revealed) {
          item.dataset.revealed = "1";
          revealPyqAnswers(item);
        }
      });
    });
  }

  async function revealPyqAnswers(item) {
    var detail = qs(".wrong-item__detail", item);
    // The hint ("Expand to reveal...") and any previous fetch error both live in
    // a .wrong-item__source line; dropping it keeps the expanded body from
    // showing a stale instruction or stacking errors across retries.
    var stale = qs(".wrong-item__source", detail);
    if (stale) stale.remove();
    try {
      var data = await API.pyqAnswers(item.dataset.pyqId);
      var answers = (data && data.answers) || [];
      var reveal = answers.length
        ? '<div class="pyq-reveal">' + answers.map(function (a) {
            return '<div class="pyq-reveal__row" ' + (a.is_correct === 1 ? 'data-pass' : 'data-fail') + '>' +
              '<span>Q' + esc(a.question_number) + '</span>' +
              '<span>YOU ' + esc(a.selected_answer || "—") + '</span>' +
              '<span>KEY ' + esc(a.official_answer || "—") + '</span>' +
              '<span>' + esc(a.time_spent_seconds || 0) + 's</span>' +
              '</div>';
          }).join("") + '</div>'
        : '<div class="wrong-item__source">No per-question rows were stored for this attempt.</div>';
      detail.insertAdjacentHTML("beforeend", reveal);
    } catch (err) {
      // Clearing the flag lets a second click retry instead of leaving the row
      // permanently stuck on the error text.
      delete item.dataset.revealed;
      detail.insertAdjacentHTML(
        "beforeend",
        '<div class="wrong-item__source">' + esc(err.message) + '</div>'
      );
    }
  }

  async function loadResults() {
    if (loaded.results) return;
    var content = qs("#results-content");
    if (!content) return;

    showLoading(content);
    try {
      var settled = await Promise.all([API.timeline(), API.pyqAnalytics()]);
      var timeline = settled[0];
      var entries = Array.isArray(timeline) ? timeline : timeline.entries || [];
      var attempts = (settled[1] && settled[1].attempts) || [];

      // Guarding on entries alone used to blank the whole view, so a user who had
      // sat PYQ papers but no mock was told they had no history at all.
      if (!entries.length && !attempts.length) {
        showEmpty(content, "No exam history yet. Complete a mock or a PYQ paper to see results.");
        return;
      }

      content.innerHTML =
        (entries.length
          ? '<div class="view-eyebrow">§08 · EXAMINATION RESULTS · ' + entries.length + ' ENTRIES</div>' +
            '<div class="results-timeline" id="results-timeline"></div>' +
            '<div class="results-gate" id="results-gate"></div>'
          : '') +
        (attempts.length ? '<div class="results-pyq" id="results-pyq"></div>' : '');

      if (entries.length) {
        // get_analytics_timeline orders by generated_at DESC, so the array
        // arrives newest-first. A progression chart has to read left to right in
        // time, and "latest" is the first element, not the last.
        var chronological = entries.slice().reverse();

        // Timeline bars
        var timelineEl = qs("#results-timeline", content);
        var maxScore = Math.max.apply(null, chronological.map(function (e) { return e.score || 0; }));
        timelineEl.innerHTML = chronological.map(function (e) {
          var pct = maxScore > 0 ? ((e.score || 0) / maxScore) * 100 : 0;
          var pass = pct >= 60;
          return '<div class="results-bar" ' + (pass ? 'data-pass' : 'data-fail') + ' style="height:' + Math.max(pct, 4) + '%">' +
            '<span class="results-bar__label">' + esc((e.created_at || "").substring(5, 10)) + '</span>' +
            '</div>';
        }).join("");

        // Gate vis. The timeline carries one combined score per mock: there is no
        // paper split to show. mock_sessions has no paper1/paper2 columns and
        // /api/exams/{exam_id}/aggregate takes both scores as inputs rather than
        // storing them, so a PAPER II cell could only ever read 0 and an
        // AGGREGATE cell only ever equalled Paper I. These are the three figures
        // the endpoint really returns; 40 is the cut-off that endpoint uses.
        var gateEl = qs("#results-gate", content);
        var latest = chronological[chronological.length - 1] || {};
        var lastScore = Math.round((latest.score || 0) * 10) / 10;
        var lastAccuracy = Math.round(latest.accuracy || 0);
        var lastTopicAccuracy = Math.round(latest.avg_topic_accuracy || 0);
        gateEl.innerHTML =
          '<div class="results-gate__item"><div class="results-gate__value" ' + (lastScore >= 40 ? 'data-pass' : 'data-fail') + '>' + esc(lastScore) + '</div><div class="results-gate__label">LATEST SCORE</div></div>' +
          '<div class="results-gate__item"><div class="results-gate__value" ' + (lastAccuracy >= 40 ? 'data-pass' : 'data-fail') + '>' + esc(lastAccuracy) + '%</div><div class="results-gate__label">ACCURACY</div></div>' +
          '<div class="results-gate__item"><div class="results-gate__value" ' + (lastTopicAccuracy >= 40 ? 'data-pass' : 'data-fail') + '>' + esc(lastTopicAccuracy) + '%</div><div class="results-gate__label">AVG TOPIC</div></div>';
      }

      if (attempts.length) {
        renderPyqAttempts(qs("#results-pyq", content), attempts);
      }

      loaded.results = true;
    } catch (err) {
      showError(content, err.message, loadResults);
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
