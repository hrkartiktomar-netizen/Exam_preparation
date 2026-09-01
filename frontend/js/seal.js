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
        s.src = "/app/vendor/three.min.js?v=r160-umd";
        // UMD build prints an r150+ deprecation warning on execution — mute it
        var prevWarn = console.warn;
        console.warn = function (msg) {
          if (typeof msg === "string" && msg.indexOf("three.min.js") !== -1) return;
          prevWarn.apply(console, arguments);
        };
        s.onload = function () { console.warn = prevWarn; resolve(window.THREE); };
        s.onerror = function () { console.warn = prevWarn; threePromise = null; reject(new Error("three.js failed to load")); };
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
