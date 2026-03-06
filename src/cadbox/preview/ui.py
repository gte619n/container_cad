"""HTML/JS/CSS template for the cadbox web UI."""

from __future__ import annotations

HTML_TEMPLATE = """\
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>cadbox</title>
  <link rel="icon" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'><rect x='10' y='30' width='80' height='60' rx='6' fill='%237aa2f7' stroke='%23333' stroke-width='3'/><rect x='20' y='40' width='25' height='25' rx='3' fill='%231a1b26'/><rect x='55' y='40' width='25' height='25' rx='3' fill='%231a1b26'/><path d='M10 30 L50 10 L90 30' fill='none' stroke='%23333' stroke-width='3' stroke-linecap='round'/></svg>">
  <style>
    :root {
      --bg: #12131a;
      --sidebar-bg: #1a1b26;
      --surface: #222336;
      --surface-hover: #2a2b3d;
      --border: #333456;
      --text: #c0caf5;
      --text-dim: #787c9e;
      --accent: #7aa2f7;
      --accent-hover: #89b4fa;
      --danger: #f7768e;
      --success: #9ece6a;
      --warning: #e0af68;
      --input-bg: #1e1f2e;
      --radius: 6px;
    }
    * { margin: 0; padding: 0; box-sizing: border-box; }
    body {
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', system-ui, sans-serif;
      background: var(--bg);
      color: var(--text);
      display: flex;
      height: 100vh;
      overflow: hidden;
    }

    /* Sidebar */
    #sidebar {
      width: 360px;
      min-width: 360px;
      background: var(--sidebar-bg);
      border-right: 1px solid var(--border);
      display: flex;
      flex-direction: column;
      overflow: hidden;
    }
    #sidebar-header {
      padding: 16px;
      border-bottom: 1px solid var(--border);
      font-size: 18px;
      font-weight: 600;
      display: flex;
      align-items: center;
      gap: 8px;
    }
    #sidebar-header .logo { color: var(--accent); }
    #sidebar-scroll {
      flex: 1;
      overflow-y: auto;
      padding: 12px;
    }
    #sidebar-scroll::-webkit-scrollbar { width: 6px; }
    #sidebar-scroll::-webkit-scrollbar-track { background: transparent; }
    #sidebar-scroll::-webkit-scrollbar-thumb { background: var(--border); border-radius: 3px; }

    /* Sections */
    .section {
      margin-bottom: 16px;
      background: var(--surface);
      border-radius: var(--radius);
      border: 1px solid var(--border);
    }
    .section-header {
      padding: 10px 12px;
      font-size: 12px;
      font-weight: 600;
      text-transform: uppercase;
      letter-spacing: 0.5px;
      color: var(--text-dim);
      cursor: pointer;
      display: flex;
      justify-content: space-between;
      align-items: center;
      user-select: none;
    }
    .section-header:hover { color: var(--text); }
    .section-header .chevron { transition: transform 0.2s; font-size: 10px; }
    .section.collapsed .section-body { display: none; }
    .section.collapsed .chevron { transform: rotate(-90deg); }
    .section-body { padding: 0 12px 12px; }

    /* Form elements */
    label {
      display: block;
      font-size: 11px;
      color: var(--text-dim);
      margin-bottom: 3px;
      margin-top: 8px;
    }
    label:first-child { margin-top: 0; }
    input[type="number"], input[type="text"], select {
      width: 100%;
      padding: 6px 8px;
      background: var(--input-bg);
      border: 1px solid var(--border);
      border-radius: 4px;
      color: var(--text);
      font-size: 13px;
      outline: none;
      transition: border-color 0.15s;
    }
    input:focus, select:focus {
      border-color: var(--accent);
    }
    .row { display: flex; gap: 8px; }
    .row > div { flex: 1; }

    /* Buttons */
    .btn {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      gap: 4px;
      padding: 7px 12px;
      border: 1px solid var(--border);
      border-radius: 4px;
      background: var(--surface);
      color: var(--text);
      font-size: 12px;
      cursor: pointer;
      transition: all 0.15s;
      white-space: nowrap;
    }
    .btn:hover { background: var(--surface-hover); border-color: var(--accent); }
    .btn-primary {
      background: var(--accent);
      color: #1a1b26;
      border-color: var(--accent);
      font-weight: 600;
    }
    .btn-primary:hover { background: var(--accent-hover); }
    .btn-danger { color: var(--danger); }
    .btn-danger:hover { border-color: var(--danger); }
    .btn-sm { padding: 4px 8px; font-size: 11px; }
    .btn-block { width: 100%; }

    /* Saved configs list */
    .config-item {
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: 8px;
      margin-bottom: 4px;
      border-radius: 4px;
      cursor: pointer;
      transition: background 0.15s;
    }
    .config-item:hover { background: var(--surface-hover); }
    .config-item.active { background: var(--accent); color: #1a1b26; }
    .config-item .name { font-size: 13px; font-weight: 500; }
    .config-item .meta { font-size: 10px; color: var(--text-dim); }
    .config-item.active .meta { color: rgba(26,27,38,0.7); }
    .config-item .actions { display: flex; gap: 2px; }

    /* Cavity cards */
    .cavity-card {
      background: var(--input-bg);
      border: 1px solid var(--border);
      border-radius: var(--radius);
      padding: 10px;
      margin-bottom: 8px;
      position: relative;
    }
    .cavity-card-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 6px;
    }
    .cavity-card-title {
      font-size: 12px;
      font-weight: 600;
      color: var(--accent);
    }
    .remove-cavity {
      background: none;
      border: none;
      color: var(--danger);
      cursor: pointer;
      font-size: 16px;
      padding: 0 4px;
      line-height: 1;
      opacity: 0.6;
    }
    .remove-cavity:hover { opacity: 1; }

    /* Main area */
    #main {
      flex: 1;
      display: flex;
      flex-direction: column;
      position: relative;
    }
    #toolbar {
      padding: 8px 16px;
      border-bottom: 1px solid var(--border);
      display: flex;
      align-items: center;
      gap: 8px;
      background: var(--sidebar-bg);
    }
    #viewer {
      flex: 1;
      position: relative;
    }
    #viewer canvas { display: block; }
    #viewer-info {
      position: absolute;
      bottom: 12px;
      left: 50%;
      transform: translateX(-50%);
      color: var(--text-dim);
      font-size: 11px;
      background: rgba(0,0,0,0.5);
      padding: 4px 12px;
      border-radius: 4px;
      pointer-events: none;
    }

    /* Status bar */
    #status {
      padding: 6px 16px;
      border-top: 1px solid var(--border);
      font-size: 11px;
      color: var(--text-dim);
      background: var(--sidebar-bg);
      display: flex;
      justify-content: space-between;
    }
    .status-ok { color: var(--success); }
    .status-err { color: var(--danger); }
    .status-busy { color: var(--warning); }

    /* Save dialog overlay */
    .overlay {
      display: none;
      position: fixed;
      inset: 0;
      background: rgba(0,0,0,0.6);
      z-index: 100;
      align-items: center;
      justify-content: center;
    }
    .overlay.visible { display: flex; }
    .dialog {
      background: var(--sidebar-bg);
      border: 1px solid var(--border);
      border-radius: 8px;
      padding: 20px;
      min-width: 320px;
    }
    .dialog h3 { margin-bottom: 12px; font-size: 15px; }
    .dialog .btn-row { display: flex; gap: 8px; justify-content: flex-end; margin-top: 16px; }

    /* Template section */
    .template-card {
      background: var(--input-bg);
      border: 1px solid var(--border);
      border-radius: var(--radius);
      padding: 10px;
      margin-bottom: 8px;
    }
    .template-card-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 6px;
    }
    .template-card-title {
      font-size: 12px;
      font-weight: 600;
      color: var(--warning);
    }
  </style>
</head>
<body>

<!-- Sidebar -->
<div id="sidebar">
  <div id="sidebar-header">
    <span class="logo">&#x25A3;</span> cadbox
  </div>
  <div id="sidebar-scroll">

    <!-- Saved Configs -->
    <div class="section">
      <div class="section-header" onclick="toggleSection(this)">
        Saved Configurations <span class="chevron">&#x25BC;</span>
      </div>
      <div class="section-body">
        <div id="config-list"></div>
        <div style="display:flex;gap:6px;margin-top:8px;">
          <button class="btn btn-sm btn-block" onclick="showSaveDialog()">Save Current</button>
          <button class="btn btn-sm btn-block" onclick="importConfig()">Import JSON</button>
        </div>
      </div>
    </div>

    <!-- Box Type -->
    <div class="section">
      <div class="section-header" onclick="toggleSection(this)">
        Box Type <span class="chevron">&#x25BC;</span>
      </div>
      <div class="section-body">
        <div class="row">
          <div><label>Mode</label>
            <select id="box-type" onchange="onBoxTypeChange()">
              <option value="custom">Custom Box</option>
              <option value="gridfinity">Gridfinity Bin</option>
            </select>
          </div>
        </div>
        <!-- Gridfinity grid settings (hidden by default) -->
        <div id="gridfinity-settings" style="display:none;">
          <div class="row" style="margin-top:8px;">
            <div><label>Grid Units X</label><input type="number" id="gf-units-x" value="2" min="1" step="1"></div>
            <div><label>Grid Units Y</label><input type="number" id="gf-units-y" value="2" min="1" step="1"></div>
            <div><label>Height Units</label><input type="number" id="gf-height-units" value="3" min="1" step="1"></div>
          </div>
          <div class="row" style="margin-top:4px;">
            <div><label>Magnet Holes</label>
              <select id="gf-magnets">
                <option value="false">No</option>
                <option value="true">Yes</option>
              </select>
            </div>
            <div><label>Footprint</label><span id="gf-footprint" style="font-size:12px;color:var(--accent);display:block;margin-top:6px;">83.5 x 83.5 mm</span></div>
          </div>
        </div>
      </div>
    </div>

    <!-- Box Parameters -->
    <div class="section" id="custom-params-section">
      <div class="section-header" onclick="toggleSection(this)">
        Box Parameters <span class="chevron">&#x25BC;</span>
      </div>
      <div class="section-body">
        <div class="row">
          <div><label>Width (mm)</label><input type="number" id="box-width" value="200" step="1" min="10"></div>
          <div><label>Length (mm)</label><input type="number" id="box-length" value="150" step="1" min="10"></div>
          <div><label>Height (mm)</label><input type="number" id="box-height" value="40" step="1" min="5"></div>
        </div>
        <div class="row">
          <div><label>Wall Thickness</label><input type="number" id="box-wall" value="2.0" step="0.1" min="0.4"></div>
          <div><label>Rib Thickness</label><input type="number" id="box-rib" value="1.6" step="0.1" min="0.4"></div>
          <div><label>Floor Thickness</label><input type="number" id="box-floor" value="1.2" step="0.1" min="0.4"></div>
        </div>
        <div class="row">
          <div><label>Corner Fillet</label><input type="number" id="box-fillet" value="1.0" step="0.1" min="0"></div>
          <div><label>Layout</label>
            <select id="box-layout">
              <option value="packed">Packed (tight)</option>
              <option value="centered">Centered</option>
              <option value="even">Even spacing</option>
            </select>
          </div>
        </div>
        <div class="row">
          <div><label>Outer Fillet Upper</label><input type="number" id="box-fillet-upper" value="0" step="0.1" min="0"></div>
          <div><label>Outer Fillet Lower</label><input type="number" id="box-fillet-lower" value="0" step="0.1" min="0"></div>
          <div><label>Cavity Fillet Top</label><input type="number" id="box-cavity-fillet" value="0" step="0.1" min="0"></div>
        </div>
      </div>
    </div>

    <!-- Stacking -->
    <div class="section" id="stacking-section">
      <div class="section-header" onclick="toggleSection(this)">
        Stacking <span class="chevron">&#x25BC;</span>
      </div>
      <div class="section-body">
        <div class="row">
          <div><label>Stacking Mode</label>
            <select id="stacking-mode" onchange="onStackingChange()">
              <option value="none">None</option>
              <option value="receiver">Receiver (top rim)</option>
              <option value="stacker">Stacker (bottom step)</option>
              <option value="both">Both</option>
            </select>
          </div>
        </div>
        <div id="stacking-params" style="display:none;">
          <div class="row" style="margin-top:8px;">
            <div><label>Shelf Depth (mm)</label><input type="number" id="stack-shelf-depth" value="2.0" step="0.1" min="0.5"></div>
            <div><label>Shelf Height (mm)</label><input type="number" id="stack-shelf-height" value="3.5" step="0.1" min="1.0"></div>
          </div>
          <div class="row">
            <div><label>Clearance (mm)</label><input type="number" id="stack-clearance" value="0.3" step="0.05" min="0"></div>
            <div><label>Lead-in Chamfer</label><input type="number" id="stack-chamfer" value="0.5" step="0.1" min="0"></div>
          </div>
        </div>
      </div>
    </div>

    <!-- Templates -->
    <div class="section">
      <div class="section-header" onclick="toggleSection(this)">
        Cavity Templates <span class="chevron">&#x25BC;</span>
      </div>
      <div class="section-body">
        <div id="template-list"></div>
        <button class="btn btn-sm btn-block" onclick="addTemplate()" style="margin-top:6px;">+ Add Template</button>
      </div>
    </div>

    <!-- Cavities -->
    <div class="section">
      <div class="section-header" onclick="toggleSection(this)">
        Cavities <span class="chevron">&#x25BC;</span>
      </div>
      <div class="section-body">
        <div id="cavity-list"></div>
        <div style="display:flex;gap:6px;margin-top:6px;">
          <button class="btn btn-sm" onclick="addCavity('rect')">+ Rectangle</button>
          <button class="btn btn-sm" onclick="addCavity('circle')">+ Circle</button>
          <button class="btn btn-sm" onclick="addCavityRef()">+ From Template</button>
        </div>
      </div>
    </div>
  </div>
</div>

<!-- Main area -->
<div id="main">
  <div id="toolbar">
    <button class="btn btn-primary" onclick="generateBox()">Generate</button>
    <button class="btn" onclick="validateConfig()">Validate</button>
    <button class="btn" onclick="exportConfig()">Export JSON</button>
    <span style="margin-left:auto;"></span>
    <button class="btn" onclick="downloadFile('step')" id="dl-step-btn" disabled>Download STEP</button>
    <button class="btn" onclick="downloadFile('stl')" id="dl-stl-btn" disabled>Download STL</button>
    <span id="gen-status" style="margin-left:8px;font-size:12px;"></span>
  </div>
  <div id="viewer">
    <div id="viewer-info">Drag to rotate &nbsp;|&nbsp; Scroll to zoom &nbsp;|&nbsp; Right-drag to pan</div>
  </div>
  <div id="status">
    <span id="status-left">Ready</span>
    <span id="status-right"></span>
  </div>
</div>

<!-- Save dialog -->
<div class="overlay" id="save-overlay">
  <div class="dialog">
    <h3>Save Configuration</h3>
    <label>Name</label>
    <input type="text" id="save-name" placeholder="my-container">
    <div class="btn-row">
      <button class="btn" onclick="hideSaveDialog()">Cancel</button>
      <button class="btn btn-primary" onclick="doSave()">Save</button>
    </div>
  </div>
</div>

<!-- Import dialog -->
<div class="overlay" id="import-overlay">
  <div class="dialog">
    <h3>Import JSON Configuration</h3>
    <label>Paste JSON</label>
    <textarea id="import-json" rows="10" style="width:100%;background:var(--input-bg);border:1px solid var(--border);border-radius:4px;color:var(--text);padding:8px;font-family:monospace;font-size:12px;resize:vertical;"></textarea>
    <div class="btn-row">
      <button class="btn" onclick="hideImportDialog()">Cancel</button>
      <button class="btn btn-primary" onclick="doImport()">Import</button>
    </div>
  </div>
</div>

<!-- Three.js -->
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
const container = document.getElementById('viewer');
const renderer = new THREE.WebGLRenderer({ antialias: true });
renderer.setPixelRatio(window.devicePixelRatio);
renderer.shadowMap.enabled = true;
renderer.shadowMap.type = THREE.PCFSoftShadowMap;
container.insertBefore(renderer.domElement, container.firstChild);

const scene = new THREE.Scene();
scene.background = new THREE.Color(0x12131a);

const camera = new THREE.PerspectiveCamera(45, 1, 0.1, 10000);
camera.position.set(150, 120, 200);

// Lighting
scene.add(new THREE.AmbientLight(0xffffff, 0.6));
const dirLight = new THREE.DirectionalLight(0xffffff, 1.2);
dirLight.position.set(200, 300, 200);
dirLight.castShadow = true;
dirLight.shadow.mapSize.set(2048, 2048);
dirLight.shadow.camera.near = 1;
dirLight.shadow.camera.far = 2000;
[-300, 300, 300, -300].forEach((v, i) => {
  ['left','right','top','bottom'][i].split('').length;
  dirLight.shadow.camera[['left','right','top','bottom'][i]] = v;
});
scene.add(dirLight);

const fillLight = new THREE.DirectionalLight(0x8899cc, 0.4);
fillLight.position.set(-100, 50, -150);
scene.add(fillLight);

// Controls
const controls = new OrbitControls(camera, renderer.domElement);
controls.enableDamping = true;
controls.dampingFactor = 0.08;
controls.screenSpacePanning = true;
controls.minDistance = 5;
controls.maxDistance = 5000;

// Grid
const grid = new THREE.GridHelper(500, 50, 0x334466, 0x223355);
scene.add(grid);

// Material
const material = new THREE.MeshStandardMaterial({
  color: 0x7aa2f7,
  metalness: 0.2,
  roughness: 0.5,
  side: THREE.DoubleSide,
});

let currentMesh = null;
let hasLoadedOnce = false;

function fitCamera(geometry, resetView) {
  geometry.computeBoundingBox();
  const box = geometry.boundingBox;
  const center = new THREE.Vector3();
  box.getCenter(center);
  const size = new THREE.Vector3();
  box.getSize(size);
  const maxDim = Math.max(size.x, size.y, size.z);
  const fov = camera.fov * (Math.PI / 180);
  const distance = (maxDim / 2) / Math.tan(fov / 2) * 2.0;

  if (currentMesh) {
    // Center on XZ, sit flat on Y=0
    currentMesh.position.set(-center.x, -box.min.y, -center.z);
  }
  grid.scale.setScalar(Math.max(maxDim / 200, 1));

  if (resetView) {
    controls.target.set(0, size.y / 2, 0);
    camera.position.set(distance * 0.4, distance * 0.9, distance * 0.5);
  }
  camera.near = distance * 0.001;
  camera.far = distance * 20;
  camera.updateProjectionMatrix();
  controls.update();
}

window._loadSTL = function(url) {
  const loader = new STLLoader();
  loader.load(url + '?t=' + Date.now(), (geometry) => {
    // Rotate Z-up (CadQuery) to Y-up (Three.js) before anything else
    geometry.rotateX(-Math.PI / 2);
    geometry.computeVertexNormals();
    if (currentMesh) scene.remove(currentMesh);
    currentMesh = new THREE.Mesh(geometry, material);
    currentMesh.castShadow = true;
    currentMesh.receiveShadow = true;
    scene.add(currentMesh);
    const resetView = !hasLoadedOnce;
    hasLoadedOnce = true;
    fitCamera(geometry, resetView);
  }, undefined, (err) => {
    console.error('Failed to load STL:', err);
  });
};

// Resize
function onResize() {
  const w = container.clientWidth;
  const h = container.clientHeight;
  camera.aspect = w / h;
  camera.updateProjectionMatrix();
  renderer.setSize(w, h);
}
window.addEventListener('resize', onResize);
new ResizeObserver(onResize).observe(container);
onResize();

// Render loop
function animate() {
  requestAnimationFrame(animate);
  controls.update();
  renderer.render(scene, camera);
}
animate();
</script>

<script>
// -----------------------------------------------------------------------
// State
// -----------------------------------------------------------------------
let cavities = [];
let templates = [];
let activeConfigName = null;
let cavityIdCounter = 0;
let templateIdCounter = 0;

// -----------------------------------------------------------------------
// Helpers
// -----------------------------------------------------------------------
function toggleSection(header) {
  header.parentElement.classList.toggle('collapsed');
}

function setStatus(msg, cls) {
  const el = document.getElementById('status-left');
  el.textContent = msg;
  el.className = cls || '';
}

function setGenStatus(msg, cls) {
  const el = document.getElementById('gen-status');
  el.textContent = msg;
  el.className = cls || '';
}

function val(id) { return parseFloat(document.getElementById(id).value) || 0; }
function sval(id) { return document.getElementById(id).value; }

// -----------------------------------------------------------------------
// Build config from UI
// -----------------------------------------------------------------------
function onBoxTypeChange() {
  const isGF = sval('box-type') === 'gridfinity';
  document.getElementById('gridfinity-settings').style.display = isGF ? 'block' : 'none';
  document.getElementById('custom-params-section').style.display = isGF ? 'none' : '';
  document.getElementById('stacking-section').style.display = isGF ? 'none' : '';
  if (isGF) updateGfFootprint();
}

function onStackingChange() {
  const mode = sval('stacking-mode');
  document.getElementById('stacking-params').style.display = mode === 'none' ? 'none' : 'block';
}

function updateGfFootprint() {
  const ux = parseInt(document.getElementById('gf-units-x').value) || 1;
  const uy = parseInt(document.getElementById('gf-units-y').value) || 1;
  const hu = parseInt(document.getElementById('gf-height-units').value) || 1;
  const w = (ux * 42 - 0.5).toFixed(1);
  const l = (uy * 42 - 0.5).toFixed(1);
  const h = (7 + hu * 7 + 4.4).toFixed(1);
  document.getElementById('gf-footprint').textContent = w + ' x ' + l + ' x ' + h + ' mm';
}
document.getElementById('gf-units-x').addEventListener('input', updateGfFootprint);
document.getElementById('gf-units-y').addEventListener('input', updateGfFootprint);
document.getElementById('gf-height-units').addEventListener('input', updateGfFootprint);

function downloadFile(fmt) {
  window.open('/download/' + fmt, '_blank');
}

function buildConfig() {
  const boxType = sval('box-type');
  const config = {
    box_type: boxType,
    width: val('box-width'),
    length: val('box-length'),
    height: val('box-height'),
    outer_wall: val('box-wall'),
    rib_thickness: val('box-rib'),
    floor_thickness: val('box-floor'),
    fillet_radius: val('box-fillet'),
    outer_fillet_upper: val('box-fillet-upper'),
    outer_fillet_lower: val('box-fillet-lower'),
    cavity_fillet_top: val('box-cavity-fillet'),
    layout: sval('box-layout'),
    templates: templates.map(t => {
      const obj = { name: t.name, shape: t.shape, depth: t.depth };
      if (t.shape === 'rect') { obj.width = t.width; obj.length = t.length; }
      if (t.shape === 'circle') { obj.diameter = t.diameter; }
      if (t.fillet_top > 0) obj.fillet_top = t.fillet_top;
      return obj;
    }),
    // Stacking (custom boxes only)
    stacking: boxType === 'custom' ? sval('stacking-mode') : 'none',
    stacking_shelf_depth: val('stack-shelf-depth'),
    stacking_shelf_height: val('stack-shelf-height'),
    stacking_clearance: val('stack-clearance'),
    stacking_chamfer: val('stack-chamfer'),
    // Gridfinity
    grid_units_x: parseInt(document.getElementById('gf-units-x').value) || 1,
    grid_units_y: parseInt(document.getElementById('gf-units-y').value) || 1,
    height_units: parseInt(document.getElementById('gf-height-units').value) || 3,
    gridfinity_magnets: document.getElementById('gf-magnets').value === 'true',
    cavities: cavities.map(c => {
      if (c.type === 'ref') {
        const obj = { template: c.template };
        if (c.depth) obj.depth = c.depth;
        if (c.fillet_top > 0) obj.fillet_top = c.fillet_top;
        if (c.grid) { obj.grid = c.grid; }
        else if (c.count > 1) { obj.count = c.count; }
        return obj;
      }
      const obj = { shape: c.shape, depth: c.depth };
      if (c.shape === 'rect') { obj.width = c.width; obj.length = c.length; }
      if (c.shape === 'circle') { obj.diameter = c.diameter; }
      if (c.fillet_top > 0) obj.fillet_top = c.fillet_top;
      if (c.grid) { obj.grid = c.grid; }
      else if (c.count > 1) { obj.count = c.count; }
      return obj;
    }),
  };
  return config;
}

// -----------------------------------------------------------------------
// Load config into UI
// -----------------------------------------------------------------------
function loadConfigIntoUI(config) {
  // Box type
  document.getElementById('box-type').value = config.box_type || 'custom';
  onBoxTypeChange();

  // Dimensions
  document.getElementById('box-width').value = config.width || 200;
  document.getElementById('box-length').value = config.length || 150;
  document.getElementById('box-height').value = config.height || 40;
  document.getElementById('box-wall').value = config.outer_wall ?? 2.0;
  document.getElementById('box-rib').value = config.rib_thickness ?? 1.6;
  document.getElementById('box-floor').value = config.floor_thickness ?? 1.2;
  document.getElementById('box-fillet').value = config.fillet_radius ?? 1.0;
  document.getElementById('box-fillet-upper').value = config.outer_fillet_upper ?? 0;
  document.getElementById('box-fillet-lower').value = config.outer_fillet_lower ?? 0;
  document.getElementById('box-cavity-fillet').value = config.cavity_fillet_top ?? 0;
  document.getElementById('box-layout').value = config.layout || 'packed';

  // Stacking
  document.getElementById('stacking-mode').value = config.stacking || 'none';
  document.getElementById('stack-shelf-depth').value = config.stacking_shelf_depth ?? 2.0;
  document.getElementById('stack-shelf-height').value = config.stacking_shelf_height ?? 3.5;
  document.getElementById('stack-clearance').value = config.stacking_clearance ?? 0.3;
  document.getElementById('stack-chamfer').value = config.stacking_chamfer ?? 0.5;
  onStackingChange();

  // Gridfinity
  document.getElementById('gf-units-x').value = config.grid_units_x || 1;
  document.getElementById('gf-units-y').value = config.grid_units_y || 1;
  document.getElementById('gf-height-units').value = config.height_units || 3;
  document.getElementById('gf-magnets').value = config.gridfinity_magnets ? 'true' : 'false';
  updateGfFootprint();

  // Templates
  templates = (config.templates || []).map(t => ({
    _id: templateIdCounter++,
    name: t.name,
    shape: t.shape,
    width: t.width || 0,
    length: t.length || 0,
    diameter: t.diameter || 0,
    depth: t.depth,
    fillet_top: t.fillet_top || 0,
  }));
  renderTemplates();

  // Cavities
  cavities = (config.cavities || []).map(c => {
    if (c.template) {
      return {
        _id: cavityIdCounter++,
        type: 'ref',
        template: c.template,
        depth: c.depth || null,
        fillet_top: c.fillet_top || 0,
        count: c.count || 1,
        grid: c.grid || null,
      };
    }
    return {
      _id: cavityIdCounter++,
      type: 'spec',
      shape: c.shape,
      width: c.width || 0,
      length: c.length || 0,
      diameter: c.diameter || 0,
      depth: c.depth,
      fillet_top: c.fillet_top || 0,
      count: c.count || 1,
      grid: c.grid || null,
    };
  });
  renderCavities();
}

// -----------------------------------------------------------------------
// Render templates
// -----------------------------------------------------------------------
function renderTemplates() {
  const list = document.getElementById('template-list');
  list.innerHTML = '';
  templates.forEach((t, idx) => {
    const card = document.createElement('div');
    card.className = 'template-card';
    const shapeFields = t.shape === 'circle'
      ? `<div><label>Diameter</label><input type="number" value="${t.diameter}" step="0.5" min="1" onchange="updateTemplate(${idx},'diameter',this.value)"></div>`
      : `<div><label>Width</label><input type="number" value="${t.width}" step="0.5" min="1" onchange="updateTemplate(${idx},'width',this.value)"></div>
         <div><label>Length</label><input type="number" value="${t.length}" step="0.5" min="1" onchange="updateTemplate(${idx},'length',this.value)"></div>`;
    card.innerHTML = `
      <div class="template-card-header">
        <span class="template-card-title">${t.name || 'unnamed'}</span>
        <button class="remove-cavity" onclick="removeTemplate(${idx})">&times;</button>
      </div>
      <div class="row">
        <div><label>Name</label><input type="text" value="${t.name}" onchange="updateTemplate(${idx},'name',this.value)"></div>
        <div><label>Shape</label>
          <select onchange="updateTemplate(${idx},'shape',this.value);renderTemplates()">
            <option value="rect" ${t.shape==='rect'?'selected':''}>Rectangle</option>
            <option value="circle" ${t.shape==='circle'?'selected':''}>Circle</option>
          </select>
        </div>
      </div>
      <div class="row">
        ${shapeFields}
        <div><label>Depth</label><input type="number" value="${t.depth}" step="0.5" min="1" onchange="updateTemplate(${idx},'depth',this.value)"></div>
      </div>
      <div class="row">
        <div><label>Fillet Top</label><input type="number" value="${t.fillet_top||0}" step="0.1" min="0" onchange="updateTemplate(${idx},'fillet_top',this.value)"></div>
      </div>`;
    list.appendChild(card);
  });
}

function addTemplate() {
  templates.push({
    _id: templateIdCounter++,
    name: 'template_' + templates.length,
    shape: 'rect',
    width: 20,
    length: 20,
    diameter: 20,
    depth: 10,
    fillet_top: 0,
  });
  renderTemplates();
}

function removeTemplate(idx) {
  templates.splice(idx, 1);
  renderTemplates();
}

function updateTemplate(idx, field, val) {
  const v = (field === 'name' || field === 'shape') ? val : parseFloat(val) || 0;
  templates[idx][field] = v;
}

// -----------------------------------------------------------------------
// Render cavities
// -----------------------------------------------------------------------
function renderCavities() {
  const list = document.getElementById('cavity-list');
  list.innerHTML = '';
  cavities.forEach((c, idx) => {
    const card = document.createElement('div');
    card.className = 'cavity-card';

    if (c.type === 'ref') {
      const templateNames = templates.map(t => t.name);
      const options = templateNames.map(n =>
        `<option value="${n}" ${c.template===n?'selected':''}>${n}</option>`
      ).join('');
      card.innerHTML = `
        <div class="cavity-card-header">
          <span class="cavity-card-title">Ref: ${c.template}</span>
          <button class="remove-cavity" onclick="removeCavity(${idx})">&times;</button>
        </div>
        <div class="row">
          <div><label>Template</label><select onchange="updateCavity(${idx},'template',this.value)">${options}</select></div>
          <div><label>Count</label><input type="number" value="${c.count}" min="1" onchange="updateCavity(${idx},'count',this.value)"></div>
        </div>
        <div class="row">
          <div><label>Grid (cols,rows)</label><input type="text" value="${c.grid ? c.grid.join(',') : ''}" placeholder="e.g. 3,2" onchange="updateCavityGrid(${idx},this.value)"></div>
          <div><label>Depth Override</label><input type="number" value="${c.depth||''}" step="0.5" min="0" placeholder="default" onchange="updateCavity(${idx},'depth',this.value)"></div>
        </div>`;
    } else {
      const shapeFields = c.shape === 'circle'
        ? `<div><label>Diameter</label><input type="number" value="${c.diameter}" step="0.5" min="1" onchange="updateCavity(${idx},'diameter',this.value)"></div>`
        : `<div><label>Width</label><input type="number" value="${c.width}" step="0.5" min="1" onchange="updateCavity(${idx},'width',this.value)"></div>
           <div><label>Length</label><input type="number" value="${c.length}" step="0.5" min="1" onchange="updateCavity(${idx},'length',this.value)"></div>`;
      card.innerHTML = `
        <div class="cavity-card-header">
          <span class="cavity-card-title">${c.shape === 'circle' ? 'Circle' : 'Rectangle'}</span>
          <button class="remove-cavity" onclick="removeCavity(${idx})">&times;</button>
        </div>
        <div class="row">
          ${shapeFields}
          <div><label>Depth</label><input type="number" value="${c.depth}" step="0.5" min="1" onchange="updateCavity(${idx},'depth',this.value)"></div>
        </div>
        <div class="row">
          <div><label>Count</label><input type="number" value="${c.count}" min="1" onchange="updateCavity(${idx},'count',this.value)"></div>
          <div><label>Grid (cols,rows)</label><input type="text" value="${c.grid ? c.grid.join(',') : ''}" placeholder="e.g. 3,2" onchange="updateCavityGrid(${idx},this.value)"></div>
        </div>
        <div class="row">
          <div><label>Fillet Top</label><input type="number" value="${c.fillet_top||0}" step="0.1" min="0" onchange="updateCavity(${idx},'fillet_top',this.value)"></div>
        </div>`;
    }
    list.appendChild(card);
  });
}

function addCavity(shape) {
  cavities.push({
    _id: cavityIdCounter++,
    type: 'spec',
    shape: shape,
    width: 20,
    length: 20,
    diameter: 20,
    depth: 10,
    fillet_top: 0,
    count: 1,
    grid: null,
  });
  renderCavities();
}

function addCavityRef() {
  if (templates.length === 0) {
    alert('Add a template first');
    return;
  }
  cavities.push({
    _id: cavityIdCounter++,
    type: 'ref',
    template: templates[0].name,
    depth: null,
    fillet_top: 0,
    count: 1,
    grid: null,
  });
  renderCavities();
}

function removeCavity(idx) {
  cavities.splice(idx, 1);
  renderCavities();
}

function updateCavity(idx, field, val) {
  if (field === 'template') {
    cavities[idx][field] = val;
  } else {
    cavities[idx][field] = parseFloat(val) || 0;
    if (field === 'depth' && !val) cavities[idx][field] = null;
  }
}

function updateCavityGrid(idx, val) {
  if (!val.trim()) {
    cavities[idx].grid = null;
    return;
  }
  const parts = val.split(',').map(s => parseInt(s.trim()));
  if (parts.length === 2 && parts[0] > 0 && parts[1] > 0) {
    cavities[idx].grid = parts;
    cavities[idx].count = 1;
  }
}

// -----------------------------------------------------------------------
// API calls
// -----------------------------------------------------------------------
async function generateBox() {
  const config = buildConfig();
  console.log('[generateBox] sending config:', JSON.stringify(config, null, 2));
  setGenStatus('Generating...', 'status-busy');
  setStatus('Generating container...', 'status-busy');
  try {
    const resp = await fetch('/api/generate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(config),
    });
    const data = await resp.json();
    if (!resp.ok) {
      setGenStatus('Error', 'status-err');
      setStatus(data.error || 'Generation failed', 'status-err');
      return;
    }
    setGenStatus('Done', 'status-ok');
    setStatus(
      `Generated: ${data.placements} cavities, ${data.utilization}% utilization`,
      'status-ok'
    );
    document.getElementById('dl-step-btn').disabled = false;
    document.getElementById('dl-stl-btn').disabled = false;
    window._loadSTL('/model.stl');
  } catch (e) {
    setGenStatus('Error', 'status-err');
    setStatus('Request failed: ' + e.message, 'status-err');
  }
}

async function validateConfig() {
  const config = buildConfig();
  try {
    const resp = await fetch('/api/validate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(config),
    });
    const data = await resp.json();
    if (data.valid) {
      setStatus('Validation passed', 'status-ok');
    } else {
      setStatus('Validation errors: ' + data.errors.join('; '), 'status-err');
    }
  } catch (e) {
    setStatus('Validation request failed: ' + e.message, 'status-err');
  }
}

async function loadConfigList() {
  try {
    const resp = await fetch('/api/configs');
    const configs = await resp.json();
    const list = document.getElementById('config-list');
    list.innerHTML = '';
    if (configs.length === 0) {
      list.innerHTML = '<div style="font-size:12px;color:var(--text-dim);padding:8px;">No saved configurations</div>';
      return;
    }
    configs.forEach(c => {
      const item = document.createElement('div');
      item.className = 'config-item' + (c.name === activeConfigName ? ' active' : '');
      const safeName = c.name.replace(/'/g, "\\'");
      const date = new Date(c.modified * 1000);
      const dateStr = date.toLocaleDateString() + ' ' + date.toLocaleTimeString([], {hour:'2-digit',minute:'2-digit'});
      item.setAttribute('onclick', "loadSavedConfig('" + safeName + "')");
      item.innerHTML = `
        <div>
          <div class="name">${c.name}</div>
          <div class="meta">${dateStr}</div>
        </div>
        <div class="actions">
          <button class="btn btn-sm btn-danger" onclick="event.stopPropagation();deleteSavedConfig('${safeName}')">&#x2715;</button>
        </div>`;
      list.appendChild(item);
    });
  } catch (e) {
    console.error('Failed to load config list', e);
  }
}

async function loadSavedConfig(name) {
  try {
    const resp = await fetch('/api/configs/' + encodeURIComponent(name));
    if (!resp.ok) {
      const err = await resp.json().catch(() => ({}));
      setStatus('Load failed: ' + (err.error || resp.statusText), 'status-err');
      return;
    }
    const config = await resp.json();
    console.log('Loaded config:', name, config);
    loadConfigIntoUI(config);
    activeConfigName = name;
    setStatus('Loaded: ' + name, 'status-ok');
    loadConfigList();
  } catch (e) {
    console.error('loadSavedConfig error:', e);
    setStatus('Failed to load config: ' + e.message, 'status-err');
  }
}

async function deleteSavedConfig(name) {
  if (!confirm('Delete "' + name + '"?')) return;
  try {
    await fetch('/api/configs/' + encodeURIComponent(name), { method: 'DELETE' });
    if (activeConfigName === name) activeConfigName = null;
    loadConfigList();
    setStatus('Deleted: ' + name, '');
  } catch (e) {
    setStatus('Failed to delete: ' + e.message, 'status-err');
  }
}

function showSaveDialog() {
  document.getElementById('save-name').value = activeConfigName || '';
  document.getElementById('save-overlay').classList.add('visible');
  document.getElementById('save-name').focus();
}
function hideSaveDialog() {
  document.getElementById('save-overlay').classList.remove('visible');
}

async function doSave() {
  const name = document.getElementById('save-name').value.trim();
  if (!name) { alert('Enter a name'); return; }
  let config;
  try {
    config = buildConfig();
  } catch (e) {
    alert('Error building config: ' + e.message);
    console.error('buildConfig error:', e);
    return;
  }
  try {
    const resp = await fetch('/api/configs/' + encodeURIComponent(name), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(config),
    });
    if (resp.ok) {
      activeConfigName = name;
      hideSaveDialog();
      loadConfigList();
      setStatus('Saved: ' + name, 'status-ok');
    } else {
      const data = await resp.json().catch(() => ({}));
      const msg = 'Save failed: ' + (data.error || resp.statusText);
      setStatus(msg, 'status-err');
      alert(msg);
    }
  } catch (e) {
    setStatus('Save failed: ' + e.message, 'status-err');
    alert('Save error: ' + e.message);
    console.error('doSave error:', e);
  }
}

function exportConfig() {
  const config = buildConfig();
  const json = JSON.stringify(config, null, 2);
  const blob = new Blob([json], { type: 'application/json' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = (activeConfigName || 'cadbox-config') + '.json';
  a.click();
  URL.revokeObjectURL(url);
}

function importConfig() {
  document.getElementById('import-json').value = '';
  document.getElementById('import-overlay').classList.add('visible');
  document.getElementById('import-json').focus();
}
function hideImportDialog() {
  document.getElementById('import-overlay').classList.remove('visible');
}
function doImport() {
  try {
    const config = JSON.parse(document.getElementById('import-json').value);
    loadConfigIntoUI(config);
    hideImportDialog();
    activeConfigName = null;
    setStatus('Imported configuration', 'status-ok');
  } catch (e) {
    alert('Invalid JSON: ' + e.message);
  }
}

// Enter key in save dialog
document.getElementById('save-name').addEventListener('keydown', e => {
  if (e.key === 'Enter') doSave();
});

// -----------------------------------------------------------------------
// Init
// -----------------------------------------------------------------------
loadConfigList();

// Load default config
loadConfigIntoUI({
  width: 200, length: 150, height: 40,
  outer_wall: 2.0, rib_thickness: 1.6, floor_thickness: 1.2,
  fillet_radius: 1.0, layout: 'packed',
  templates: [], cavities: [],
});
</script>
</body>
</html>
"""
