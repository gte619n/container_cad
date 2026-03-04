"""Minimal web preview server for cadbox STEP/STL files.

Serves an embedded Three.js viewer over localhost HTTP and auto-opens
the browser.  No external Python dependencies required - Three.js is
loaded from a CDN.
"""

from __future__ import annotations

import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

# ---------------------------------------------------------------------------
# Embedded HTML page
# ---------------------------------------------------------------------------

_HTML_TEMPLATE = """\
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>cadbox preview</title>
  <style>
    * { margin: 0; padding: 0; box-sizing: border-box; }
    body { background: #1a1a2e; overflow: hidden; }
    canvas { display: block; }
    #info {
      position: absolute;
      top: 12px;
      left: 50%;
      transform: translateX(-50%);
      color: #aab4d4;
      font-family: monospace;
      font-size: 13px;
      background: rgba(0,0,0,0.45);
      padding: 4px 14px;
      border-radius: 4px;
      pointer-events: none;
      white-space: nowrap;
    }
  </style>
</head>
<body>
  <div id="info">cadbox &mdash; drag to rotate &nbsp;|&nbsp; scroll to zoom &nbsp;|&nbsp; right-drag to pan</div>

  <!-- Three.js r158 (ES module build) -->
  <script type="importmap">
  {
    "imports": {
      "three": "https://cdn.jsdelivr.net/npm/three@0.158.0/build/three.module.js",
      "three/addons/": "https://cdn.jsdelivr.net/npm/three@0.158.0/examples/jsm/"
    }
  }
  </script>

  <script type="module">
    import * as THREE from 'three';
    import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
    import { STLLoader } from 'three/addons/loaders/STLLoader.js';

    // -----------------------------------------------------------------------
    // Scene setup
    // -----------------------------------------------------------------------
    const renderer = new THREE.WebGLRenderer({ antialias: true });
    renderer.setPixelRatio(window.devicePixelRatio);
    renderer.setSize(window.innerWidth, window.innerHeight);
    renderer.shadowMap.enabled = true;
    renderer.shadowMap.type = THREE.PCFSoftShadowMap;
    document.body.appendChild(renderer.domElement);

    const scene = new THREE.Scene();
    scene.background = new THREE.Color(0x1a1a2e);

    const camera = new THREE.PerspectiveCamera(
      45,
      window.innerWidth / window.innerHeight,
      0.1,
      10000
    );
    camera.position.set(150, 120, 200);

    // -----------------------------------------------------------------------
    // Lighting
    // -----------------------------------------------------------------------
    const ambientLight = new THREE.AmbientLight(0xffffff, 0.6);
    scene.add(ambientLight);

    const dirLight = new THREE.DirectionalLight(0xffffff, 1.2);
    dirLight.position.set(200, 300, 200);
    dirLight.castShadow = true;
    dirLight.shadow.mapSize.set(2048, 2048);
    dirLight.shadow.camera.near = 1;
    dirLight.shadow.camera.far = 2000;
    dirLight.shadow.camera.left = -300;
    dirLight.shadow.camera.right = 300;
    dirLight.shadow.camera.top = 300;
    dirLight.shadow.camera.bottom = -300;
    scene.add(dirLight);

    const fillLight = new THREE.DirectionalLight(0x8899cc, 0.4);
    fillLight.position.set(-100, 50, -150);
    scene.add(fillLight);

    // -----------------------------------------------------------------------
    // Controls
    // -----------------------------------------------------------------------
    const controls = new OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;
    controls.dampingFactor = 0.08;
    controls.screenSpacePanning = true;
    controls.minDistance = 5;
    controls.maxDistance = 5000;

    // -----------------------------------------------------------------------
    // Grid helper (floor plane)
    // -----------------------------------------------------------------------
    const grid = new THREE.GridHelper(500, 50, 0x334466, 0x223355);
    grid.position.y = 0;
    scene.add(grid);

    // -----------------------------------------------------------------------
    // STL model
    // -----------------------------------------------------------------------
    const material = new THREE.MeshStandardMaterial({
      color: 0x8899aa,
      metalness: 0.25,
      roughness: 0.55,
      side: THREE.DoubleSide,
    });

    const loader = new STLLoader();
    loader.load(
      '/model.stl',
      (geometry) => {
        geometry.computeVertexNormals();

        const mesh = new THREE.Mesh(geometry, material);
        mesh.castShadow = true;
        mesh.receiveShadow = true;
        scene.add(mesh);

        // Auto-fit camera to model bounds
        geometry.computeBoundingBox();
        const box = geometry.boundingBox;
        const center = new THREE.Vector3();
        box.getCenter(center);
        const size = new THREE.Vector3();
        box.getSize(size);

        const maxDim = Math.max(size.x, size.y, size.z);
        const fov = camera.fov * (Math.PI / 180);
        const distance = (maxDim / 2) / Math.tan(fov / 2) * 2.0;

        // Reposition mesh so it sits on the grid
        mesh.position.set(-center.x, -box.min.y, -center.z);

        // Update grid to model footprint size
        grid.scale.setScalar(Math.max(maxDim / 200, 1));

        // Orbit target at model base centre
        controls.target.set(0, size.y / 2, 0);

        camera.position.set(
          distance * 0.4,
          distance * 0.9,
          distance * 0.5
        );
        camera.near = distance * 0.001;
        camera.far = distance * 20;
        camera.updateProjectionMatrix();
        controls.update();
      },
      undefined,
      (err) => {
        console.error('Failed to load STL:', err);
        const div = document.getElementById('info');
        div.style.color = '#ff6b6b';
        div.textContent = 'Failed to load model. Check browser console for details.';
      }
    );

    // -----------------------------------------------------------------------
    // Resize handling
    // -----------------------------------------------------------------------
    window.addEventListener('resize', () => {
      camera.aspect = window.innerWidth / window.innerHeight;
      camera.updateProjectionMatrix();
      renderer.setSize(window.innerWidth, window.innerHeight);
    });

    // -----------------------------------------------------------------------
    // Render loop
    // -----------------------------------------------------------------------
    function animate() {
      requestAnimationFrame(animate);
      controls.update();
      renderer.render(scene, camera);
    }
    animate();
  </script>
</body>
</html>
"""


# ---------------------------------------------------------------------------
# HTTP handler
# ---------------------------------------------------------------------------


def _make_handler(model_path: Path, html: str) -> type[BaseHTTPRequestHandler]:
    """Return a request handler class closed over the model path and HTML."""

    class _Handler(BaseHTTPRequestHandler):
        def log_message(self, format: str, *args: object) -> None:  # noqa: A002
            # Suppress default request logging to keep the terminal clean.
            pass

        def do_GET(self) -> None:  # noqa: N802
            if self.path == "/" or self.path == "/index.html":
                self._serve_html()
            elif self.path == "/model.stl":
                self._serve_stl()
            else:
                self.send_error(404, "Not Found")

        def _serve_html(self) -> None:
            body = html.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self._cors_headers()
            self.end_headers()
            self.wfile.write(body)

        def _serve_stl(self) -> None:
            try:
                data = model_path.read_bytes()
            except OSError as exc:
                self.send_error(500, f"Cannot read model file: {exc}")
                return
            self.send_response(200)
            self.send_header("Content-Type", "model/stl")
            self.send_header("Content-Length", str(len(data)))
            self._cors_headers()
            self.end_headers()
            self.wfile.write(data)

        def _cors_headers(self) -> None:
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Cache-Control", "no-store, no-cache, must-revalidate")
            self.send_header("Pragma", "no-cache")

    return _Handler


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def launch_preview(stl_path: str | Path, port: int = 8123) -> None:
    """Start a local HTTP server and open the 3-D STL viewer in the browser.

    Args:
        stl_path: Path to the STL (or STEP) file to preview.
        port:     Local TCP port for the HTTP server (default 8123).

    The function blocks until the user presses Ctrl-C.
    """
    stl_path = Path(stl_path)
    if not stl_path.exists():
        raise FileNotFoundError(f"Model file not found: {stl_path}")

    html = _HTML_TEMPLATE  # already formatted; no substitutions needed

    handler_class = _make_handler(stl_path, html)
    server = HTTPServer(("127.0.0.1", port), handler_class)

    url = f"http://localhost:{port}"
    print(f"Preview server running at {url}  (Ctrl-C to stop)")

    # Open browser slightly after server starts.
    def _open_browser() -> None:
        webbrowser.open(url)

    timer = threading.Timer(0.4, _open_browser)
    timer.daemon = True
    timer.start()

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        timer.cancel()
        server.server_close()
