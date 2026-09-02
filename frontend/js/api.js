/* THE LEDGER — API client. Same-origin relative calls into FastAPI.
   Every failure routes through authored system states (A24). */
(function () {
  "use strict";

  async function req(method, path, body, opts) {
    var o = Object.assign({ quiet: false }, opts);
    var init = { method: method, headers: {} };
    if (body !== undefined) {
      init.headers["Content-Type"] = "application/json";
      init.body = JSON.stringify(body);
    }
    var res = await fetch(path, init);
    if (!res.ok) {
      var detail = res.status + " " + res.statusText;
      try {
        var j = await res.json();
        if (j && j.detail) detail = typeof j.detail === "string" ? j.detail : JSON.stringify(j.detail);
      } catch (e) { /* non-JSON */ }
      var err = new Error(detail);
      err.status = res.status;
      throw err;
    }
    var ct = res.headers.get("content-type") || "";
    return ct.includes("application/json") ? res.json() : res.text();
  }

  var get  = function (p, o) { return req("GET", p, undefined, o); };
  var post = function (p, b, o) { return req("POST", p, b, o); };

  window.LedgerAPI = {
    // Core
    health:            function () { return get("/health"); },
    dashboard:         function () { return get("/api/dashboard?include_ai=false"); },
    readiness:         function (target, days) { return get("/api/dashboard/readiness?target_score=" + (target || 130) + "&days_to_exam=" + (days || 28)); },
    nextAction:        function () { return get("/api/dashboard/next-action"); },

    // Topics
    weakTopics:        function () { return get("/api/topics/weak"); },
    topicStats:        function () { return get("/api/topics/stats"); },

    // Analytics
    timeline:          function () { return get("/api/analytics/timeline?limit=12"); },

    // Updates & Amendments
    updates:           function (sort) { return get("/api/updates?sort=" + (sort || "date_desc") + "&limit=60"); },
    updatesRun:        function () { return post("/api/updates/run"); },
    updatesStatus:     function (id, status) { return post("/api/updates/" + id + "/status?status=" + status); },
    amendmentsRecent:  function () { return get("/api/amendments/recent?limit=8"); },
    amendmentsAll:     function () { return get("/api/amendments?limit=500"); },
    amendmentsIntel:   function () { return get("/api/amendments/intelligence?limit=8"); },
    startupScan:       function (refresh) { return get("/api/amendments/startup-scan?refresh=" + (refresh ? "true" : "false")); },
    enrichReasons:     function () { return post("/api/updates/enrich-reasons"); },

    // SRS
    srsDue:            function () { return get("/api/srs/due-topics"); },

    // Law revision
    lawDaily:          function () { return get("/api/law/daily-revision?include_ai=false"); },
    lawComplete:       function (day, lines) { return post("/api/law/daily-revision/complete-day?day_index=" + day + "&lines_per_day=" + (lines || 60)); },

    // Exams
    examsStart:        function (body) { return post("/api/exams/start", body); },
    examTime:          function (id) { return get("/api/exams/" + id + "/time-remaining"); },
    examSubmit:        function (id, answers) { return post("/api/exams/" + id + "/submit", { answers: answers }); },
    examAnalytics:     function (id, list) { return post("/api/exams/" + id + "/analytics", list); },
    aggregate:         function (exam, p1, p2) {
      return get("/api/exams/agg/aggregate?exam=" + exam + "&paper1_score=" + p1 + "&paper2_score=" + p2).catch(function () {
        return get("/api/aggregate?exam=" + exam + "&paper1_score=" + p1 + "&paper2_score=" + p2);
      });
    },

    // PYQ
    pyqList:           function () { return get("/api/pyq/list"); },
    pyqLoad:           function (docId) { return post("/api/pyq/" + docId + "/load"); },
    pyqSitting:        function (year, phase, opts) {
      var o = opts || {};
      var q = "/api/pyq/sitting?year=" + year + "&phase=" + phase;
      if (o.exam) q += "&exam=" + encodeURIComponent(o.exam);
      if (o.paper) q += "&paper=" + o.paper;
      if (o.limit) q += "&limit=" + o.limit;
      return get(q);
    },
    pyqDrill:          function (subjectId, opts) {
      var o = opts || {};
      var q = "/api/pyq/drill?subject_id=" + encodeURIComponent(subjectId);
      if (o.exam) q += "&exam=" + encodeURIComponent(o.exam);
      q += "&limit=" + (o.limit || 20);
      return get(q);
    },
    pyqSubmit:         function (id, answers) { return post("/api/pyq/" + id + "/submit", { answers: answers }); },
    pyqAnswers:        function (id) { return get("/api/pyq/" + id + "/answers"); },
    pyqAnalytics:      function () { return get("/api/pyq/analytics"); },

    // Descriptive
    descriptiveStart:  function (exam, year) { return post("/api/descriptive/start", { exam: exam, year: year }); },
    descriptiveGrade:  function (body) { return post("/api/descriptive/grade", body); },

    // Drills
    wrongQueue:        function (limit) { return get("/api/drills/wrong-queue?limit=" + (limit || 12)); },
    replay:            function (topic, n) { return post("/api/drills/replay?topic=" + encodeURIComponent(topic) + "&question_count=" + (n || 5)); },

    // AI & Tracker
    aiStatus:          function () { return get("/api/ai/status"); },
    trackerStatus:     function () { return get("/api/updates/status"); },
  };
})();
