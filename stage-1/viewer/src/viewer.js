// SemiBlock Junior - stage-1 3D viewer.
// Bundled to ../viewer.bundle.js (see ../README-viewer.md). Works from file://:
// models are lazy-loaded as <script src="models/<name>.js"> that call SBV.register().
import * as THREE from 'three';
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js';
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader.js';
import { RoomEnvironment } from 'three/examples/jsm/environments/RoomEnvironment.js';

const CATALOG = window.SB_CATALOG || [];
const SCENES = [
  { id: 'scene-rover', title: 'Junior Rover', lock: true, explode: true,
    desc: 'Driving base: two encoder motors, Junior Brain, ultrasonic + line sensor, ball caster. 16 TwistLock pins hold the rails; TwistLock collars keep the wheels on. Try Unlock, Explode and Section.' },
  { id: 'scene-tl_demo', title: 'TwistLock pins in beams', lock: true,
    desc: 'Left: classic Quick Pin. Middle: TwistLock pin (friction). Right: TwistLock pin (smooth, pivots). Toggle Lock, then turn on Section to see the cam inside the fingers.' },
  { id: 'scene-collar', title: 'TwistLock collar', desc: 'Same collar open (front) and locked (back). The white pointer sits on red when open and green when locked.' },
  { id: 'scene-hub', title: 'Junior Brain hub', desc: 'ESP32-S3 hub, 11 x 6 x 4 modules. 1.54 in screen, 3 buttons, RGB ring, speaker, 6 SemiLink ports, pin holes on sides and bottom.' },
  { id: 'scene-modules', title: 'Module family', desc: 'Hub, motor and smart modules share the 8 mm grid and the SemiLink-6 port.' },
  { id: 'scene-parts_kit', title: 'Parts flat-lay', desc: 'One of most mechanical part types in the stage-1 kit.' },
  { id: 'scene-semilink', title: 'SemiLink-6 connector', desc: 'Keyed, latching plug in front of hub port B.' },
  { id: 'scene-semikey', title: 'SemiKey tool', desc: 'Lock key, axle-length gauge, pin lifter and ruler in one.' },
];
const MM = 0.001;
const cadToGl = (v) => new THREE.Vector3(v[0] * MM, v[2] * MM, -v[1] * MM);

// ------------------------------------------------------------ model loading
const cache = {}, waiting = {};
window.SBV = {
  register(name, b64) {
    // payload = base64(gzip(GLB)); decompress natively in the browser
    fetch('data:application/octet-stream;base64,' + b64)
      .then((r) => new Response(r.body.pipeThrough(new DecompressionStream('gzip'))).arrayBuffer())
      .then((buf) => {
      cache[name] = buf;
      (waiting[name] || []).forEach((fn) => fn(buf));
      delete waiting[name];
    });
  },
};
function loadBuffer(name) {
  if (cache[name]) return Promise.resolve(cache[name]);
  return new Promise((resolve, reject) => {
    const first = !waiting[name];
    (waiting[name] = waiting[name] || []).push(resolve);
    if (first) {
      const s = document.createElement('script');
      s.src = 'models/' + name + '.js';
      s.onerror = () => reject(new Error('missing model ' + name));
      document.head.appendChild(s);
    }
  });
}
const gltfLoader = new GLTFLoader();
const parseGLB = (buf) => new Promise((res, rej) => gltfLoader.parse(buf, '', res, rej));

// ------------------------------------------------------------------ three
const view = document.getElementById('view');
const renderer = new THREE.WebGLRenderer({ antialias: true, preserveDrawingBuffer: true });
renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
renderer.outputColorSpace = THREE.SRGBColorSpace;
// Neutral tone mapping keeps white parts from clipping (same idea as the Blender renders)
renderer.toneMapping = THREE.NeutralToneMapping;
renderer.toneMappingExposure = 1.0;
renderer.shadowMap.enabled = true;
renderer.shadowMap.type = THREE.PCFSoftShadowMap;
renderer.localClippingEnabled = true;
view.appendChild(renderer.domElement);

const scene = new THREE.Scene();
scene.background = new THREE.Color(0xdde3ec);
const pmrem = new THREE.PMREMGenerator(renderer);
scene.environment = pmrem.fromScene(new RoomEnvironment(), 0.04).texture;
scene.environmentIntensity = 0.45;
const camera = new THREE.PerspectiveCamera(32, 1, 0.0005, 50);
const controls = new OrbitControls(camera, renderer.domElement);
controls.enableDamping = true;
const sun = new THREE.DirectionalLight(0xffffff, 2.2);
sun.castShadow = true;
sun.shadow.mapSize.set(2048, 2048);
sun.shadow.bias = -0.0002;
const fill = new THREE.DirectionalLight(0xeaf2ff, 0.35);
scene.add(sun, sun.target, fill, fill.target, new THREE.HemisphereLight(0xffffff, 0xc9d2de, 0.25));
// thin dark lines on sharp edges so hole rims and faces read on white parts
const edgeMat = new THREE.LineBasicMaterial({ color: 0x1b222c, transparent: true, opacity: 0.38 });
let edgesOn = true;
const ground = new THREE.Mesh(new THREE.PlaneGeometry(1, 1), new THREE.ShadowMaterial({ opacity: 0.16 }));
ground.rotation.x = -Math.PI / 2;
ground.receiveShadow = true;
scene.add(ground);

const clipPlane = new THREE.Plane(new THREE.Vector3(-1, 0, 0), 0);
edgeMat.clippingPlanes = [clipPlane];
let current = null;            // { root, box, lockables, explodables, kind, meta }
let sectionAxis = null;
let explodeT = 0;
const ui = (id) => document.getElementById(id);

function resize() {
  const w = view.clientWidth, h = view.clientHeight;
  renderer.setSize(w, h);
  camera.aspect = w / h;
  camera.updateProjectionMatrix();
}
window.addEventListener('resize', resize);

function frameObject(box, dir = new THREE.Vector3(1.0, 0.75, 1.1)) {
  const size = box.getSize(new THREE.Vector3());
  const center = box.getCenter(new THREE.Vector3());
  const radius = size.length() / 2;
  const dist = radius / Math.sin(THREE.MathUtils.degToRad(camera.fov / 2)) * 1.05;
  camera.position.copy(center).add(dir.normalize().multiplyScalar(dist));
  camera.near = dist / 200; camera.far = dist * 20;
  camera.updateProjectionMatrix();
  controls.target.copy(center);
  controls.update();
  ground.position.set(center.x, box.min.y - 0.00002, center.z);
  ground.scale.setScalar(radius * 12);
  sun.position.copy(center).add(new THREE.Vector3(-0.6, 1.4, 0.8).multiplyScalar(radius * 3));
  sun.target.position.copy(center);
  fill.position.copy(center).add(new THREE.Vector3(1.2, 0.4, -0.2).multiplyScalar(radius * 3));
  fill.target.position.copy(center);
  const sc = sun.shadow.camera;
  sc.left = sc.bottom = -radius * 1.6; sc.right = sc.top = radius * 1.6;
  sc.near = radius * 0.5; sc.far = radius * 8;
  sc.updateProjectionMatrix();
}

function prepare(root) {
  const lockables = [], explodables = [];
  const nodes = [];
  const tuned = new Set();
  root.traverse((o) => nodes.push(o));          // snapshot: we add children below
  nodes.forEach((o) => {
    if (o.isMesh) {
      o.castShadow = o.receiveShadow = true;
      const m = o.material;
      if (!tuned.has(m)) {
        tuned.add(m);
        if (m.name === 'sb_white') m.color.multiplyScalar(0.82);   // real white ABS reflects ~80%
        m.polygonOffset = true;                                     // keep edge lines on top
        m.polygonOffsetFactor = 1;
        m.polygonOffsetUnits = 1;
      }
      m.clippingPlanes = [clipPlane];
      m.clipShadows = true;
      m.side = THREE.FrontSide;
      m.needsUpdate = true;
      const edges = new THREE.LineSegments(new THREE.EdgesGeometry(o.geometry, 35), edgeMat);
      edges.userData.isEdge = true;
      edges.visible = edgesOn;
      o.add(edges);
      const cap = new THREE.Mesh(o.geometry, new THREE.MeshBasicMaterial({
        color: m.color ? m.color.clone().multiplyScalar(0.55) : 0x444444, side: THREE.BackSide,
        clippingPlanes: [clipPlane] }));
      cap.visible = false;
      cap.userData.isCap = true;
      o.add(cap);
    }
    const ex = o.userData || {};
    if (ex.lock) {
      const core = o.children.find((c) => c.name.startsWith(ex.lock.node));
      if (core) {
        const pivot = new THREE.Group();
        const p = new THREE.Vector3(...ex.lock.pivot);
        pivot.position.copy(p);
        o.add(pivot);
        pivot.attach(core);
        lockables.push({ pivot, axis: new THREE.Vector3(...ex.lock.axis).normalize(), turn: THREE.MathUtils.degToRad(ex.lock.turn),
                         locked: ex.lock.state === 'locked', angle: 0 });
      }
    }
    if (ex.explode !== undefined) explodables.push({ obj: o, base: o.position.clone(), hide: ex.explode === 'hide',
                                                     off: ex.explode === 'hide' ? null : cadToGl(ex.explode) });
  });
  return { lockables, explodables };
}

function setEdges(on) {
  edgesOn = on;
  ui('edgesBtn').classList.toggle('on', on);
  if (current) current.root.traverse((o) => { if (o.userData.isEdge) o.visible = on; });
}

function setCaps(on) {
  if (!current) return;
  current.root.traverse((o) => { if (o.userData.isCap) o.visible = on; });
}

function applySection() {
  const on = sectionAxis !== null && current;
  if (on) {
    const c = current.box.getCenter(new THREE.Vector3());
    const n = { x: new THREE.Vector3(-1, 0, 0), y: new THREE.Vector3(0, 0, -1), z: new THREE.Vector3(0, -1, 0) }[sectionAxis];
    const t = parseFloat(ui('sectionPos').value) / 100;
    const size = current.box.getSize(new THREE.Vector3());
    const ext = { x: size.x, y: size.z, z: size.y }[sectionAxis];
    const pt = c.clone().add(n.clone().multiplyScalar(-(t - 0.5) * ext));
    clipPlane.setFromNormalAndCoplanarPoint(n, pt);
  } else {
    clipPlane.set(new THREE.Vector3(-1, 0, 0), 1e6);
  }
  setCaps(!!on);
  document.querySelectorAll('[data-section]').forEach((b) => b.classList.toggle('on', (b.dataset.section || null) === (sectionAxis || '')));
  ui('sectionPos').disabled = !on;
}

function setLock(lock) {
  if (!current) return;
  current.lockables.forEach((l) => { l.target = lock ? (l.locked ? 0 : l.turn) : (l.locked ? -l.turn : 0); });
  ui('lockBtn').textContent = lock ? 'Unlock all' : 'Lock all';
  ui('lockBtn').dataset.state = lock ? 'locked' : 'open';
  ui('lockState').textContent = lock ? 'All TwistLocks locked (green windows)' : 'All TwistLocks open (red windows)';
}

function setExplode(t) {
  explodeT = t;
  if (!current) return;
  current.explodables.forEach((e) => {
    if (e.hide) { e.obj.visible = t < 0.02; return; }
    e.obj.position.copy(e.base).addScaledVector(e.off, t);
  });
}

async function show(name, kind) {
  ui('loading').hidden = false;
  ui('error').hidden = true;
  try {
    const buf = await loadBuffer(name);
    const gltf = await parseGLB(buf);
    if (current) scene.remove(current.root);
    const root = gltf.scene;
    scene.add(root);
    const extras = prepare(root);
    root.updateMatrixWorld(true);
    const box = new THREE.Box3().setFromObject(root);
    current = { root, box, kind, name, ...extras };
    frameObject(box, kind === 'part' ? new THREE.Vector3(1.0, 0.85, 1.15) : new THREE.Vector3(1.0, 0.7, 1.05));
    const meta = SCENES.find((s) => s.id === name);
    ui('lockGroup').hidden = extras.lockables.length === 0;
    ui('explodeGroup').hidden = extras.explodables.length === 0;
    ui('explode').value = 0; setExplode(0);
    if (extras.lockables.length) setLock(extras.lockables.every((l) => l.locked));
    applySection();
    const s = box.getSize(new THREE.Vector3());
    ui('dims').textContent = `${(s.x * 1000).toFixed(1)} x ${(s.z * 1000).toFixed(1)} x ${(s.y * 1000).toFixed(1)} mm (bounding box)`;
    renderInfo(kind === 'part' ? CATALOG.find((r) => r.id === name) : meta, kind);
    document.querySelectorAll('.item').forEach((el) => el.classList.toggle('active', el.dataset.name === name));
  } catch (err) {
    ui('error').hidden = false;
    ui('error').textContent = 'Could not load ' + name + ': ' + err.message;
  } finally {
    ui('loading').hidden = true;
  }
}

const esc = (s) => String(s ?? '').replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
function renderInfo(row, kind) {
  const el = ui('info');
  if (!row) { el.innerHTML = ''; return; }
  if (kind !== 'part') {
    el.innerHTML = `<h2>${esc(row.title)}</h2><p>${esc(row.desc)}</p>`;
    return;
  }
  const m = row.module;
  const rows = [['ID', row.id], ['Family', row.family], ['Size', row.size_mm.join(' x ') + ' mm']];
  if (row.qty) rows.push(['Core kit qty', row.qty]);
  if (m) rows.push(['Chinese', m.zh], ['Phase', m.phase], ['Chip', m.chip], ['Replaces', m.replaces || '-']);
  el.innerHTML = `<h2>${esc(row.title)}</h2>${row.note ? `<p>${esc(row.note)}</p>` : ''}
    <dl>${rows.map(([k, v]) => `<dt>${esc(k)}</dt><dd>${esc(v)}</dd>`).join('')}</dl>
    <div class="files"><b>Download</b>
      ${row.dwg_sheets ? `<a href="../drawings/${esc(row.id)}.pdf" target="_blank">2D drawing PDF (${row.dwg_sheets} sheet${row.dwg_sheets > 1 ? 's' : ''})</a>` : ''}
      <a href="../cad/fcstd/${esc(row.id)}.FCStd" download>FreeCAD (.FCStd)</a>
      <a href="../cad/step/${esc(row.id)}.step" download>STEP</a>
      <a href="../cad/stl/${esc(row.id)}.stl" download>STL</a></div>`;
}

// ------------------------------------------------------------------ sidebar
function buildSidebar() {
  const list = ui('list');
  const q = ui('search').value.trim().toLowerCase();
  const groups = [['Assemblies', SCENES.map((s) => ({ name: s.id, title: s.title, kind: 'scene' }))]];
  const fam = {};
  CATALOG.forEach((r) => {
    const key = r.module ? 'Modules: ' + ({ sense: 'Sensing', env: 'Environment', output: 'Output', connect: 'Connect',
                                             ai: 'AI & voice', power: 'Power' })[r.module.cat] : r.family;
    (fam[key] = fam[key] || []).push({ name: r.id, title: r.title, kind: 'part', zh: r.module?.zh || '', img: r.id });
  });
  Object.entries(fam).forEach((e) => groups.push(e));
  list.innerHTML = '';
  groups.forEach(([title, items]) => {
    const hits = items.filter((i) => !q || (i.title + ' ' + i.name + ' ' + (i.zh || '')).toLowerCase().includes(q));
    if (!hits.length) return;
    const g = document.createElement('details');
    g.open = !!q || title === 'Assemblies';
    g.innerHTML = `<summary>${esc(title)} <span>${hits.length}</span></summary>`;
    hits.forEach((i) => {
      const a = document.createElement('a');
      a.className = 'item';
      a.dataset.name = i.name;
      a.href = '#' + (i.kind === 'part' ? 'part=' : 'scene=') + i.name.replace('scene-', '');
      a.innerHTML = (i.img ? `<img loading="lazy" src="../renders/parts/${esc(i.img)}.png" alt="">` : '<span class="ico">3D</span>') +
        `<span class="t">${esc(i.title)}<small>${esc(i.kind === 'part' ? i.name : 'assembly')}${i.zh ? ' &middot; ' + esc(i.zh) : ''}</small></span>`;
      g.appendChild(a);
    });
    list.appendChild(g);
  });
}

// #part=SB-TL2 or #scene=tl_demo, optionally &lock=open|locked &section=x|y|z &explode=0..1
async function route() {
  const params = Object.fromEntries(decodeURIComponent(location.hash.slice(1)).split('&')
    .filter(Boolean).map((kv) => kv.split('=')));
  if (params.part) await show(params.part, 'part');
  else await show('scene-' + (params.scene || 'rover'), 'scene');
  if (params.lock && current && current.lockables.length) setLock(params.lock === 'locked');
  if (params.explode && current && current.explodables.length) {
    ui('explode').value = params.explode;
    setExplode(parseFloat(params.explode));
  }
  if (params.section) { sectionAxis = params.section; applySection(); }
}

// ------------------------------------------------------------------ wiring
ui('search').addEventListener('input', buildSidebar);
ui('lockBtn').addEventListener('click', () => setLock(ui('lockBtn').dataset.state !== 'locked'));
ui('explode').addEventListener('input', (e) => setExplode(parseFloat(e.target.value)));
document.querySelectorAll('[data-section]').forEach((b) => b.addEventListener('click', () => {
  sectionAxis = b.dataset.section || null; applySection();
}));
ui('sectionPos').addEventListener('input', applySection);
ui('edgesBtn').addEventListener('click', () => setEdges(!edgesOn));
ui('reset').addEventListener('click', () => current && frameObject(current.box));
ui('spin').addEventListener('click', () => { controls.autoRotate = !controls.autoRotate; ui('spin').classList.toggle('on', controls.autoRotate); });
ui('shot').addEventListener('click', () => {
  const a = document.createElement('a');
  a.download = (current ? current.name : 'semiblock') + '.png';
  a.href = renderer.domElement.toDataURL('image/png');
  a.click();
});
ui('menu').addEventListener('click', () => document.body.classList.toggle('show-side'));
window.addEventListener('hashchange', route);

const clock = new THREE.Clock();
function tick() {
  const dt = Math.min(clock.getDelta(), 0.05);
  if (current) {
    current.lockables.forEach((l) => {
      if (l.target === undefined) return;
      const d = l.target - l.angle;
      if (Math.abs(d) < 1e-3) return;
      const step = Math.sign(d) * Math.min(Math.abs(d), dt * 5);
      l.angle += step;
      l.pivot.quaternion.setFromAxisAngle(l.axis, l.angle);
    });
  }
  controls.update();
  renderer.render(scene, camera);
  requestAnimationFrame(tick);
}
resize();
buildSidebar();
route();
tick();
