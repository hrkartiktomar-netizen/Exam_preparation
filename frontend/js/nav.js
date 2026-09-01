/* THE LEDGER — instrument navigation (A05)
   IST clock tick, health dot polling, quality toggle, brass tab indicator
   animated by GSAP, seal-mini visibility. */
(function () {
  "use strict";

  const TABS = [
    { id: "today",       num: "01", label: "Today",       hash: "#today" },
    { id: "exam",        num: "02", label: "Mock Hall",    hash: "#exam" },
    { id: "pyq",         num: "03", label: "PYQ",          hash: "#pyq" },
    { id: "descriptive", num: "04", label: "Descriptive",  hash: "#descriptive" },
    { id: "tracker",     num: "05", label: "Tracker",      hash: "#tracker" },
    { id: "updates",     num: "06", label: "Updates",      hash: "#updates" },
    { id: "review",      num: "07", label: "Review",       hash: "#review" },
    { id: "results",     num: "08", label: "Results",      hash: "#results" },
  ];

  let indicator = null;
  let clockEl = null;
  let healthEl = null;
  let qualityBtn = null;
  let clockInterval = null;

  /* ---------- IST clock ---------- */
  function tickClock() {
    if (!clockEl) return;
    const now = new Date();
    // IST = UTC + 5:30
    const ist = new Date(now.getTime() + (5.5 * 60 * 60 * 1000) - (now.getTimezoneOffset() * 60 * 1000));
    const h = String(ist.getHours()).padStart(2, "0");
    const m = String(ist.getMinutes()).padStart(2, "0");
    const s = String(ist.getSeconds()).padStart(2, "0");
    clockEl.textContent = h + ":" + m + ":" + s;
  }

  /* ---------- health dot ---------- */
  async function pollHealth() {
    if (!healthEl) return;
    try {
      const res = await fetch("/health");
      if (res.ok) {
        healthEl.dataset.status = "ok";
      } else {
        healthEl.dataset.status = "warning";
      }
    } catch (e) {
      healthEl.dataset.status = "error";
    }
  }

  /* ---------- quality toggle ---------- */
  function cycleQuality() {
    const tiers = ["full", "lite", "reduced"];
    const current = document.body.dataset.quality || "full";
    const idx = tiers.indexOf(current);
    const next = tiers[(idx + 1) % tiers.length];
    document.body.dataset.quality = next;
    if (qualityBtn) qualityBtn.textContent = next;

    // Notify smooth.js and other modules
    if (window.LedgerSmooth) {
      window.LedgerSmooth.quality = next;
    }

    // Refresh ScrollTrigger for any quality-dependent changes
    if (typeof ScrollTrigger !== "undefined") {
      ScrollTrigger.refresh();
    }
  }

  /* ---------- brass tab indicator animation ---------- */
  function moveIndicator(tabEl) {
    if (!indicator || !tabEl || typeof gsap === "undefined") return;

    const rect = tabEl.getBoundingClientRect();
    const parentRect = tabEl.parentElement.getBoundingClientRect();

    gsap.to(indicator, {
      left: rect.left - parentRect.left,
      width: rect.width,
      duration: 0.35,
      ease: "power3.out",
    });
  }

  function selectTab(tabId) {
    const nav = document.querySelector(".ledger-nav");
    if (!nav) return;

    const tabs = nav.querySelectorAll(".nav__tab");
    tabs.forEach(function (tab) {
      const isSelected = tab.dataset.tab === tabId;
      tab.setAttribute("aria-selected", isSelected ? "true" : "false");
      if (isSelected) moveIndicator(tab);
    });
  }

  /* ---------- build nav DOM ---------- */
  function buildNav() {
    const nav = document.querySelector(".ledger-nav");
    if (!nav) return;

    // Seal mini
    const sealSlot = nav.querySelector(".nav__seal");

    // Tab list
    const tabList = nav.querySelector(".nav__tabs");
    if (tabList) {
      indicator = document.createElement("div");
      indicator.className = "nav__indicator";
      indicator.setAttribute("aria-hidden", "true");
      tabList.appendChild(indicator);

      TABS.forEach(function (t) {
        const btn = document.createElement("button");
        btn.className = "nav__tab";
        btn.dataset.tab = t.id;
        btn.setAttribute("role", "tab");
        btn.setAttribute("aria-selected", "false");
        btn.innerHTML =
          '<span class="nav__tab-num">§' + t.num + '</span>' +
          '<span class="nav__tab-label">' + t.label + '</span>';

        btn.addEventListener("click", function () {
          window.location.hash = t.hash;
        });

        tabList.appendChild(btn);
      });
    }

    // Meta cluster
    clockEl = nav.querySelector(".nav__clock");
    healthEl = nav.querySelector(".nav__health");
    qualityBtn = nav.querySelector(".nav__quality");

    if (qualityBtn) {
      qualityBtn.textContent = document.body.dataset.quality || "full";
      qualityBtn.addEventListener("click", cycleQuality);
    }

    // Start clock
    tickClock();
    clockInterval = setInterval(tickClock, 1000);

    // Start health polling
    pollHealth();
    setInterval(pollHealth, 30000);
  }

  /* ---------- hash-based tab sync ---------- */
  function syncTabFromHash() {
    const hash = window.location.hash.replace("#", "") || "today";
    selectTab(hash);
  }

  /* ---------- scroll-based nav hide/show ---------- */
  function setupScrollBehavior() {
    if (typeof ScrollTrigger === "undefined") return;

    // Hide nav during pinned scrollytelling, show otherwise
    const nav = document.querySelector(".ledger-nav");
    if (!nav) return;

    let lastY = 0;
    let ticking = false;

    window.addEventListener("scroll", function () {
      if (ticking) return;
      ticking = true;
      requestAnimationFrame(function () {
        const y = window.scrollY;
        const delta = y - lastY;

        // Show seal mini in nav when scrolled past hero
        const sealMini = nav.querySelector(".nav__seal");
        if (sealMini) {
          if (y > window.innerHeight * 0.5) {
            sealMini.dataset.active = "";
          } else {
            delete sealMini.dataset.active;
          }
        }

        lastY = y;
        ticking = false;
      });
    }, { passive: true });
  }

  /* ---------- init ---------- */
  function init() {
    buildNav();
    syncTabFromHash();
    window.addEventListener("hashchange", syncTabFromHash);
    setupScrollBehavior();

    // Expose for router integration
    window.LedgerNav = {
      selectTab: selectTab,
      tabs: TABS,
    };
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
