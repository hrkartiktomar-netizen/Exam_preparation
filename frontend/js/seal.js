/* THE LEDGER — Three.js Brass Seal · Readiness Gauge (A04)
   PBR brass material. 24-tick ring. Ring arc = readiness %.
   Camera: scroll orbit in hero, fixed in nav, return orbit in finale.
   Fallback: SVG poster when WebGL unavailable or quality=reduced. */
(function () {
  "use strict";

  var scene, camera, renderer, sealGroup, ringMesh;
  var isWebGL = false;
  var readinessPercent = 0;
  var targetPercent = 0;
  var animFrame = null;
  var mouseX = 0, mouseY = 0;

  function hasWebGL() {
    try {
      var c = document.createElement("canvas");
      return !!(c.getContext("webgl2") || c.getContext("webgl"));
    } catch (e) { return false; }
  }

  function init(container, percent) {
    readinessPercent = 0;
    targetPercent = percent || 0;

    if (!hasWebGL() || (window.LedgerMedia && window.LedgerMedia.isReduced)) {
      renderSVGFallback(container, percent);
      return;
    }

    if (typeof THREE === "undefined") {
      // Three.js not loaded — use SVG fallback
      renderSVGFallback(container, percent);
      return;
    }

    isWebGL = true;
    var quality = (window.LedgerMedia && window.LedgerMedia.quality) || "full";
    var dpr = quality === "full" ? Math.min(window.devicePixelRatio, 2) : 1.25;

    var w = container.clientWidth || 300;
    var h = container.clientHeight || 300;

    // Scene
    scene = new THREE.Scene();
    scene.background = null; // Transparent

    // Camera
    camera = new THREE.PerspectiveCamera(35, w / h, 0.1, 100);
    camera.position.set(0, 0, 4.5);

    // Renderer
    renderer = new THREE.WebGLRenderer({ alpha: true, antialias: true });
    renderer.setSize(w, h);
    renderer.setPixelRatio(dpr);
    renderer.toneMapping = THREE.ACESFilmicToneMapping;
    renderer.toneMappingExposure = 1.1;
    container.appendChild(renderer.domElement);

    // Lighting — warm key + cool fill + emerald rim
    var keyLight = new THREE.DirectionalLight(0xE3C07C, 1.2);
    keyLight.position.set(2, 3, 4);
    scene.add(keyLight);

    var fillLight = new THREE.DirectionalLight(0x3A4A46, 0.4);
    fillLight.position.set(-3, -1, 2);
    scene.add(fillLight);

    var rimLight = new THREE.PointLight(0x37C092, 0.6, 10);
    rimLight.position.set(0, -2, 3);
    scene.add(rimLight);

    var ambient = new THREE.AmbientLight(0x2A2520, 0.3);
    scene.add(ambient);

    // Seal group
    sealGroup = new THREE.Group();

    // Outer ring (24 ticks + progress arc)
    var brassColor = 0xC79E4F;
    var brassMat = new THREE.MeshStandardMaterial({
      color: brassColor,
      metalness: 0.85,
      roughness: 0.25,
    });

    // Outer ring torus
    var outerRing = new THREE.Mesh(
      new THREE.TorusGeometry(1.4, 0.04, 16, 64),
      brassMat
    );
    sealGroup.add(outerRing);

    // Inner ring (progress — drawn as torus arc)
    var innerRingGeo = new THREE.TorusGeometry(1.2, 0.06, 16, 64, Math.PI * 2);
    var progressMat = new THREE.MeshStandardMaterial({
      color: 0x37C092,
      metalness: 0.7,
      roughness: 0.3,
      emissive: 0x37C092,
      emissiveIntensity: 0.15,
    });
    ringMesh = new THREE.Mesh(innerRingGeo, progressMat);
    ringMesh.rotation.z = -Math.PI / 2; // Start from top
    sealGroup.add(ringMesh);

    // 24 tick marks
    for (var i = 0; i < 24; i++) {
      var angle = (i / 24) * Math.PI * 2;
      var tickGeo = new THREE.BoxGeometry(0.015, 0.08, 0.01);
      var tick = new THREE.Mesh(tickGeo, brassMat);
      tick.position.x = Math.cos(angle) * 1.4;
      tick.position.y = Math.sin(angle) * 1.4;
      tick.rotation.z = angle + Math.PI / 2;
      sealGroup.add(tick);
    }

    // Center disc
    var discGeo = new THREE.CircleGeometry(0.5, 32);
    var discMat = new THREE.MeshStandardMaterial({
      color: brassColor,
      metalness: 0.9,
      roughness: 0.2,
      side: THREE.DoubleSide,
    });
    var disc = new THREE.Mesh(discGeo, discMat);
    sealGroup.add(disc);

    scene.add(sealGroup);

    // Pointer tracking
    container.addEventListener("mousemove", function (e) {
      var rect = container.getBoundingClientRect();
      mouseX = ((e.clientX - rect.left) / rect.width - 0.5) * 2;
      mouseY = ((e.clientY - rect.top) / rect.height - 0.5) * 2;
    }, { passive: true });

    animate();
  }

  function animate() {
    animFrame = requestAnimationFrame(animate);

    // Lerp readiness toward target
    readinessPercent += (targetPercent - readinessPercent) * 0.02;

    // Update ring arc
    if (ringMesh) {
      var progress = Math.max(0, Math.min(1, readinessPercent / 100));
      ringMesh.geometry.dispose();
      ringMesh.geometry = new THREE.TorusGeometry(1.2, 0.06, 16, 64, Math.PI * 2 * progress);
    }

    // Pointer-responsive rotation
    if (sealGroup) {
      sealGroup.rotation.y += (mouseX * 0.3 - sealGroup.rotation.y) * 0.05;
      sealGroup.rotation.x += (-mouseY * 0.15 - sealGroup.rotation.x) * 0.05;
    }

    if (renderer && scene && camera) {
      renderer.render(scene, camera);
    }
  }

  function updateReadiness(percent) {
    targetPercent = percent;
  }

  function resize(container) {
    if (!renderer || !camera) return;
    var w = container.clientWidth;
    var h = container.clientHeight;
    camera.aspect = w / h;
    camera.updateProjectionMatrix();
    renderer.setSize(w, h);
  }

  function destroy() {
    if (animFrame) cancelAnimationFrame(animFrame);
    if (renderer) {
      renderer.dispose();
      renderer.domElement.remove();
    }
    if (scene) {
      scene.traverse(function (obj) {
        if (obj.geometry) obj.geometry.dispose();
        if (obj.material) {
          if (Array.isArray(obj.material)) obj.material.forEach(function (m) { m.dispose(); });
          else obj.material.dispose();
        }
      });
    }
  }

  /* ────── SVG Fallback ────── */
  function renderSVGFallback(container, percent) {
    var pct = percent || 0;
    var circumference = 283;
    var offset = circumference - (circumference * pct / 100);

    container.innerHTML =
      '<svg viewBox="0 0 100 100" width="100%" height="100%">' +
        '<circle cx="50" cy="50" r="45" fill="none" stroke="rgba(239,234,224,0.08)" stroke-width="1.5" />' +
        '<circle cx="50" cy="50" r="38" fill="none" stroke="#C79E4F" stroke-width="2" opacity="0.3" />' +
        '<circle cx="50" cy="50" r="38" fill="none" stroke="#37C092" stroke-width="2.5" ' +
          'stroke-dasharray="' + circumference + '" stroke-dashoffset="' + offset + '" ' +
          'stroke-linecap="round" transform="rotate(-90 50 50)" />' +
        // 24 ticks
        Array.from({ length: 24 }, function (_, i) {
          var angle = (i / 24) * Math.PI * 2 - Math.PI / 2;
          var x1 = 50 + Math.cos(angle) * 43;
          var y1 = 50 + Math.sin(angle) * 43;
          var x2 = 50 + Math.cos(angle) * 45;
          var y2 = 50 + Math.sin(angle) * 45;
          return '<line x1="' + x1 + '" y1="' + y1 + '" x2="' + x2 + '" y2="' + y2 + '" stroke="#C79E4F" stroke-width="0.5" opacity="0.5" />';
        }).join("") +
        '<circle cx="50" cy="50" r="16" fill="#C79E4F" opacity="0.15" />' +
        '<circle cx="50" cy="50" r="16" fill="none" stroke="#C79E4F" stroke-width="0.8" />' +
        '<text x="50" y="52" text-anchor="middle" font-family="var(--f-mono)" font-size="10" fill="#EFEAE0" font-weight="300">' + pct + '</text>' +
      '</svg>';
  }

  /* ────── Public API ────── */
  window.LedgerSeal = {
    init: init,
    updateReadiness: updateReadiness,
    resize: resize,
    destroy: destroy,
    isWebGL: function () { return isWebGL; },
  };
})();
