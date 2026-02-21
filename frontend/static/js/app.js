// global guards
window.addEventListener('unhandledrejection', function(event) {
  console.warn('Unhandled promise rejection captured:', event.reason);
});
window.addEventListener('error', function(ev) {
  console.warn('Global error captured:', ev.error || ev.message, ev);
});

// helpers
function el(tag, cls='', txt='') {
  const e = document.createElement(tag);
  if (cls) e.className = cls;
  if (txt !== undefined && txt !== null && txt !== '') e.innerText = txt;
  return e;
}
function log(msg) {
  const logsEl = document.getElementById('logs');
  if (!logsEl) return console.log(msg);
  const at = new Date().toLocaleTimeString();
  const row = document.createElement('div');
  row.innerText = `[${at}] ${msg}`;
  logsEl.prepend(row);
}

// small helpers for sim status keys/ids
function simKey(piKey, id) {
  return `${piKey}:${id}`;
}
function safeDomId(piKey, id) {
  const a = (piKey || '').replace(/[^a-zA-Z0-9]/g, '');
  const b = (id || '').replace(/[^a-zA-Z0-9]/g, '');
  return `status-${a}-${b}`;
}

// state
const sensorHist = {};
const charts = {};
const socket = io();

// fetch sim status and return a Set of running keys
async function fetchSimStatusSet() {
  try {
    const res = await fetch('/api/sim/status');
    if (!res.ok) return new Set();
    const data = await res.json();
    const s = new Set();
    (data.running || []).forEach(r => {
      if (r && r.key) s.add(r.key);
    });
    return s;
  } catch (e) {
    console.warn('fetchSimStatusSet error', e);
    return new Set();
  }
}

// start a simulation for a given pi/id or a special component
async function startSim(params) {
  try {
    const res = await fetch('/api/sim/start', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(params)
    });
    const txt = await res.text().catch(()=>null);
    if (!res.ok) { log('Failed starting simulation: ' + (txt || res.status)); return false; }
    log('Started simulation: ' + (txt || 'ok'));
    // refresh badges/UI
    try {
      const running = await fetchSimStatusSet();
      refreshSimBadgesForCurrentDevice(running);
    } catch(_) {}
    return true;
  } catch (e) {
    log('Error startSim: ' + e.message);
    return false;
  }
}

async function stopSim(params) {
  try {
    const res = await fetch('/api/sim/stop', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(params)
    });
    const txt = await res.text().catch(()=>null);
    if (!res.ok) { log('Failed stopping simulation: ' + (txt || res.status)); return false; }
    log('Stopped simulation: ' + (txt || 'ok'));
    // refresh badges/UI
    try {
      const running = await fetchSimStatusSet();
      refreshSimBadgesForCurrentDevice(running);
    } catch(_) {}
    return true;
  } catch (e) {
    log('Error stopSim: ' + e.message);
    return false;
  }
}

async function startMQTT() {
  try {
    const res = await fetch('/api/mqtt/start', { method: 'POST' });
    const txt = await res.text().catch(()=>null);
    if (!res.ok) { log('Failed starting MQTT: ' + (txt||res.status)); return; }
    log('MQTT started: ' + (txt||'ok'));
  } catch (e) { log('Error startMQTT: ' + e.message); }
}
async function stopMQTT() {
  try {
    const res = await fetch('/api/mqtt/stop', { method: 'POST' });
    const txt = await res.text().catch(()=>null);
    if (!res.ok) { log('Failed stopping MQTT: ' + (txt||res.status)); return; }
    log('MQTT stopped: ' + (txt||'ok'));
  } catch (e) { log('Error stopMQTT: ' + e.message); }
}

document.addEventListener('DOMContentLoaded', () => {
  // hook simulation control buttons (if present)
  const startSimBtn = document.getElementById('startSimBtn');
  const stopSimBtn = document.getElementById('stopSimBtn');
  const startMqttBtn = document.getElementById('startMqttBtn');
  const stopMqttBtn = document.getElementById('stopMqttBtn');
  // Sidebar start/stop -> controller (explicit) to avoid empty/invalid requests
  if (startSimBtn) startSimBtn.onclick = () => startSim({ component: 'controller' });
  if (stopSimBtn) stopSimBtn.onclick = () => stopSim({ component: 'controller' });
  if (startMqttBtn) startMqttBtn.onclick = startMQTT;
  if (stopMqttBtn) stopMqttBtn.onclick = stopMQTT;
});

// fetch devices
async function fetchDevices() {
  try {
    const res = await fetch('/api/devices');
    if (!res.ok) throw new Error('Failed to fetch devices');
    const devices = await res.json();
    renderDevices(devices);
  } catch (err) {
    log('Error fetching devices: ' + err.message);
    console.error(err);
  }
}

function renderDevices(devices) {
  const list = document.getElementById('devicesList');
  list.innerHTML = '';
  devices.forEach(d => {
    const a = el('a', 'list-group-item list-group-item-action device-card');
    a.href = '#';
    a.dataset.deviceId = d.id;
    a.innerHTML = `<div class="d-flex w-100 justify-content-between">
      <h6 class="mb-1">${d.name}</h6>
      <small class="text-muted">PI: ${d.pi}</small>
    </div>
    <p class="mb-1"><small>${d.description || ''}</small></p>`;
    a.addEventListener('click', (ev) => {
      ev.preventDefault();
      selectDevice(d.id);
      document.querySelectorAll('.list-group-item').forEach(x=>x.classList.remove('active'));
      a.classList.add('active');
    });
    list.appendChild(a);
  });
}

async function selectDevice(deviceId) {
  const main = document.getElementById('mainArea');
  main.innerHTML = '<div class="spinner-border" role="status"><span class="visually-hidden">Loading...</span></div> Loading...';
  try {
    const res = await fetch(`/api/devices/${deviceId}/details`);
    if (!res.ok) throw new Error('Device details fetch failed');
    const data = await res.json();
    renderDeviceDetails(data);
    // fetch sim status and update badges immediately
    const running = await fetchSimStatusSet();
    refreshSimBadgesForCurrentDevice(running, data);
  } catch (err) {
    main.innerHTML = `<div class="alert alert-danger">Failed to load device: ${err.message}</div>`;
    console.error(err);
  }
}

function refreshSimBadgesForCurrentDevice(runningSet, data=null) {
  if (!data) {
    // nothing to update globally without context
  }
  // sensors
  document.querySelectorAll('[data-sim-type="sensor-card"]').forEach(card => {
    const piKey = card.dataset.piKey;
    const id = card.dataset.compId;
    const key = simKey(piKey, id);
    const sid = safeDomId(piKey, id);
    const st = document.getElementById(sid);
    if (!st) return;
    if (runningSet.has(key)) {
      st.style.display = 'inline-block';
      st.innerText = 'running';
    } else {
      st.style.display = 'none';
    }
  });
  // actuators
  document.querySelectorAll('[data-sim-type="actuator-card"]').forEach(card => {
    const piKey = card.dataset.piKey;
    const id = card.dataset.compId;
    const key = simKey(piKey, id);
    const sid = safeDomId(piKey, id);
    const st = document.getElementById(sid);
    if (!st) return;
    if (runningSet.has(key)) {
      st.style.display = 'inline-block';
      st.innerText = 'running';
    } else {
      st.style.display = 'none';
    }
  });
}

function renderDeviceDetails(data) {
  const main = document.getElementById('mainArea');
  main.innerHTML = '';
  const header = el('div', 'd-flex mb-3 align-items-center');

  // header controls container
  const headerCtrl = el('div', 'ms-auto d-flex gap-2 align-items-center');

  const startBtn = el('button','btn btn-sm btn-outline-success','Start sim');
  // start all sensors & actuators for this device
  startBtn.onclick = async () => {
    const piKey = data.pi_key || `PI${data.pi}`;
    for (const s of (data.sensors || [])) {
      await startSim({ pi: piKey, id: s.id });
    }
    for (const a of (data.actuators || [])) {
      await startSim({ pi: piKey, id: a.id });
    }
    const running = await fetchSimStatusSet();
    refreshSimBadgesForCurrentDevice(running, data);
  };
  const stopBtn = el('button','btn btn-sm btn-outline-danger ms-2','Stop sim');
  stopBtn.onclick = async () => {
    const piKey = data.pi_key || `PI${data.pi}`;
    for (const s of (data.sensors || [])) {
      await stopSim({ pi: piKey, id: s.id });
    }
    for (const a of (data.actuators || [])) {
      await stopSim({ pi: piKey, id: a.id });
    }
    const running = await fetchSimStatusSet();
    refreshSimBadgesForCurrentDevice(running, data);
  };
  headerCtrl.appendChild(startBtn);
  headerCtrl.appendChild(stopBtn);

  header.appendChild(el('h3','me-3', `${data.name} (PI${data.pi})`));
  header.appendChild(el('small','text-muted', data.description || ''));
  header.appendChild(headerCtrl);
  main.appendChild(header);

  // sensors
  main.appendChild(el('h5','mt-3','Sensors'));
  const sensorsRow = el('div','row g-3');
  data.sensors.forEach(s => {
    const col = el('div','col-md-4');
    const card = el('div','card device-card p-2');
    card.dataset.simType = 'sensor-card';
    card.dataset.piKey = data.pi_key || `PI${data.pi}`;
    card.dataset.compId = s.id;
    const body = el('div','card-body p-2');
    body.appendChild(el('h6','card-title mb-1', `${s.name} (${s.code})`));
    const meta = el('div','mb-1 sensor-meta');
    meta.appendChild(el('span','badge bg-secondary sensor-tag', s.type || 'sensor'));

    // running badge (hidden by default)
    const statusId = safeDomId(data.pi_key || `PI${data.pi}`, s.id);
    const runBadge = el('span','badge bg-success ms-1', 'running');
    runBadge.id = statusId;
    runBadge.style.display = 'none';
    meta.appendChild(runBadge);

    if (s.simulated) meta.appendChild(el('span','badge bg-warning ms-1 sensor-tag','simulated'));
    body.appendChild(meta);

    const valueEl = el('div','fs-4 fw-bold mb-1','—');
    valueEl.id = `value-${s.id}`;
    body.appendChild(valueEl);

    const canvas = el('canvas','sparkline');
    canvas.id = `chart-${s.id}`;
    body.appendChild(canvas);

    // controls for manual activation
    const ctrl = el('div','mt-2');
    const stype = (s.type || '').toLowerCase();
    if (['binary','door','button','membrane','ir','infrared','motion'].includes(stype)) {
      const btn = el('button','btn btn-sm btn-primary','Trigger');
      btn.onclick = () => sendSensorCommand(s.id, {command: 'trigger'});
      ctrl.appendChild(btn);
      const tog = el('button','btn btn-sm btn-secondary ms-2','Toggle');
      tog.onclick = () => sendSensorCommand(s.id, {command: 'toggle'});
      ctrl.appendChild(tog);
    } else if (['distance','ultrasonic'].includes(stype)) {
      const input = el('input','form-control form-control-sm d-inline-block me-2');
      input.type = 'number'; input.placeholder = 'cm'; input.style.width = '110px';
      const btn = el('button','btn btn-sm btn-primary','Set');
      btn.onclick = () => {
        const v = parseFloat(input.value);
        if (isNaN(v)) { log('Unesi broj za distance'); return; }
        sendSensorCommand(s.id, {command:'set', value: v});
      };
      ctrl.appendChild(input); ctrl.appendChild(btn);
    } else if (stype === 't/h' || stype === 'dht') {
      const tinput = el('input','form-control form-control-sm d-inline-block me-2');
      tinput.type = 'number'; tinput.placeholder = 'temp';
      const hinput = el('input','form-control form-control-sm d-inline-block me-2');
      hinput.type = 'number'; hinput.placeholder = 'hum';
      const btn = el('button','btn btn-sm btn-primary','Set T/H');
      btn.onclick = () => {
        const t = parseFloat(tinput.value);
        const h = parseFloat(hinput.value);
        const payloadVal = {};
        if (!isNaN(t)) payloadVal.temperature = t;
        if (!isNaN(h)) payloadVal.humidity = h;
        if (Object.keys(payloadVal).length === 0) { log('Unesi temp ili hum'); return; }
        sendSensorCommand(s.id, {command:'set', value: payloadVal});
      };
      ctrl.appendChild(tinput); ctrl.appendChild(hinput); ctrl.appendChild(btn);
      const rnd = el('button','btn btn-sm btn-outline-secondary ms-2','Random');
      rnd.onclick = () => {
        const rt = (18 + Math.random()*10).toFixed(1);
        const rh = (30 + Math.random()*40).toFixed(1);
        sendSensorCommand(s.id, {command:'set', value: {temperature: Number(rt), humidity: Number(rh)}});
      };
      ctrl.appendChild(rnd);
    } else if (['display','text'].includes(stype)) {
      const txt = el('input','form-control form-control-sm d-inline-block me-2');
      txt.type = 'text'; txt.placeholder = 'text';
      const btn = el('button','btn btn-sm btn-primary','Send');
      btn.onclick = () => {
        if (!txt.value) { log('Unesi tekst'); return; }
        sendSensorCommand(s.id, {command:'set', value: String(txt.value)});
      };
      ctrl.appendChild(txt); ctrl.appendChild(btn);
    }
    body.appendChild(ctrl);

    card.appendChild(body);
    col.appendChild(card);
    sensorsRow.appendChild(col);

    sensorHist[s.id] = sensorHist[s.id] || [];
    renderSparkline(s.id);
  });
  main.appendChild(sensorsRow);

  // actuators
  main.appendChild(el('h5','mt-4','Actuators'));
  const actuatorsRow = el('div','row g-3 mt-3');
  data.actuators.forEach(a => {
    const col = el('div','col-md-4');
    const card = el('div','card p-2');
    card.dataset.simType = 'actuator-card';
    card.dataset.piKey = data.pi_key || `PI${data.pi}`;
    card.dataset.compId = a.id;
    const body = el('div','card-body p-2');
    body.appendChild(el('h6','card-title mb-2', `${a.name} (${a.code})`));
    const stateEl = el('div','mb-2', `State: `);
    const stateSpan = el('span','fw-bold', a.state ? a.state : 'unknown');
    stateSpan.id = `actstate-${a.id}`;
    stateEl.appendChild(stateSpan);

    // running badge for actuator
    const statusId = safeDomId(data.pi_key || `PI${data.pi}`, a.id);
    const runBadge = el('span','badge bg-success ms-2', 'running');
    runBadge.id = statusId;
    runBadge.style.display = 'none';
    stateEl.appendChild(runBadge);

    body.appendChild(stateEl);

    const controls = el('div','d-flex gap-2');
    if (a.kind === 'binary') {
      const onBtn = el('button','btn btn-sm btn-success','ON');
      const offBtn = el('button','btn btn-sm btn-danger','OFF');
      onBtn.onclick = () => sendActuatorCommand(a.id, {command:'set', value:'on'});
      offBtn.onclick = () => sendActuatorCommand(a.id, {command:'set', value:'off'});
      controls.appendChild(onBtn); controls.appendChild(offBtn);
    } else if (a.kind === 'rgb') {
      const color = el('input'); color.type = 'color'; color.value = a.state || '#ffffff';
      color.onchange = () => sendActuatorCommand(a.id, {command:'set', value: color.value});
      controls.appendChild(color);
    } else if (a.kind === 'text') {
      const inp = el('input','form-control form-control-sm'); inp.placeholder='text';
      const btn = el('button','btn btn-sm btn-primary','Send');
      btn.onclick = ()=> sendActuatorCommand(a.id, {command:'set', value: inp.value});
      controls.appendChild(inp); controls.appendChild(btn);
    } else {
      controls.appendChild(el('div','text-muted','No controls'));
    }
    body.appendChild(controls);
    card.appendChild(body);
    col.appendChild(card);
    actuatorsRow.appendChild(col);
  });
  main.appendChild(actuatorsRow);
}

/* Chart helpers */
function getYBoundsFromData(values) {
  if (!values || values.length === 0) return { min: 0, max: 100 };
  const nums = values.map(v => Number(v)).filter(v => Number.isFinite(v));
  if (nums.length === 0) return { min: 0, max: 100 };
  let min = Math.min(...nums), max = Math.max(...nums);
  if (max <= 1 && min >= 0) return { min: 0, max: 1 };
  let span = Math.max(max - min, 1);
  const pad = span * 0.2;
  min = min - pad; max = max + pad;
  span = max - min;
  if (span < 2) {
    const extra = (2 - span) / 2;
  }
  if (min < 0) min = 0;
  return { min: Math.floor(min), max: Math.ceil(max) };
}

function renderSparkline(sensorId) {
  const canvas = document.getElementById(`chart-${sensorId}`);
  if (!canvas) return;
  const dataVals = (sensorHist[sensorId] || []).slice(-25).map(p => p.value);
  const bounds = getYBoundsFromData(dataVals);
  if (charts[sensorId]) {
    try { charts[sensorId].destroy(); } catch(e) {}
  }
  charts[sensorId] = new Chart(canvas, {
    type: 'line',
    data: { labels: dataVals.map((_,i)=>i), datasets: [{ data: dataVals, borderColor: getComputedStyle(document.documentElement).getPropertyValue('--accent-blue') || '#00d2ff', borderWidth:1, pointRadius:0, tension:0.35 }]},
    options: {
      animation: false, responsive: true, maintainAspectRatio: false,
      scales: { x:{ display:false }, y:{ display:true, min: bounds.min, max: bounds.max, ticks:{ maxTicksLimit:3, color:'rgba(255,255,255,0.6)'} } },
      plugins: { legend:{ display:false }, tooltip:{ enabled:false } }
    }
  });
}

function updateSensorValue(sensorId, value, simulated=false) {
  const vEl = document.getElementById(`value-${sensorId}`);
  let display = value;
  if (value && typeof value === 'object') {
    const parts = [];
    if (value.temperature !== undefined) parts.push(`${value.temperature}°C`);
    if (value.humidity !== undefined) parts.push(`${value.humidity}%`);
    display = parts.join(' / ');
  } else if (!isNaN(Number(value))) {
    display = Number(value);
  }
  if (vEl) vEl.innerText = display + (simulated ? ' Ⓢ' : '');

  sensorHist[sensorId] = sensorHist[sensorId] || [];
  const histValue = (typeof value === 'object') ? (value.temperature !== undefined ? Number(value.temperature) : (value.humidity !== undefined ? Number(value.humidity) : 0)) : Number(value);
  sensorHist[sensorId].push({ ts: Date.now(), value: (Number.isFinite(histValue) ? histValue : 0), meta: value, simulated });

  if (sensorHist[sensorId].length > 200) sensorHist[sensorId].shift();

  const chart = charts[sensorId];
  const numericLastN = sensorHist[sensorId].slice(-25).map(p => p.value);
  if (chart) {
    chart.data.labels = numericLastN.map((_,i)=>i);
    chart.data.datasets[0].data = numericLastN;
    const bounds = getYBoundsFromData(numericLastN);
    chart.options.scales.y.min = bounds.min;
    chart.options.scales.y.max = bounds.max;
    chart.update('none');
  } else {
    renderSparkline(sensorId);
  }
}

// send actuator command
async function sendActuatorCommand(actuatorId, body) {
  try {
    const res = await fetch(`/api/actuators/${actuatorId}/command`, {
      method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify(body)
    });
    if (!res.ok) { log(`Actuator ${actuatorId} command failed`); return; }
    const json = await res.json();
    log(`Actuator ${actuatorId} command: ${JSON.stringify(body)} => ${JSON.stringify(json)}`);
    if (json.state) {
      const stEl = document.getElementById(`actstate-${actuatorId}`);
      if (stEl) stEl.innerText = json.state;
    }
    // refresh sim badges (command might have started an instance in some flows)
    const running = await fetchSimStatusSet();
    refreshSimBadgesForCurrentDevice(running);
  } catch (err) {
    log('Error sending actuator command: ' + err.message);
    console.error(err);
  }
}

async function sendSensorCommand(sensorId, body) {
  try {
    const res = await fetch(`/api/sensors/${sensorId}/command`, {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(body)
    });
    if (!res.ok) {
      const txt = await res.text().catch(()=>null);
      log(`Sensor ${sensorId} command failed: ${res.status} ${txt || ''}`);
      return;
    }
    const json = await res.json();
    log(`Sensor ${sensorId} command: ${JSON.stringify(body)} -> ${JSON.stringify(json.payload)}`);
    // refresh sim badges in case command caused instance creation
    const running = await fetchSimStatusSet();
    refreshSimBadgesForCurrentDevice(running);
  } catch (err) {
    console.error(err);
    log(`Error sending sensor command: ${err.message}`);
  }
}

/* Socket.IO events */
socket.on('connect', ()=> { log('Socket connected'); });
socket.on('sensor_update', payload => {
  if (!payload || !payload.sensor_id) return;
  updateSensorValue(payload.sensor_id, payload.value, payload.simulated);
  log(`Sensor ${payload.sensor_id} = ${JSON.stringify(payload.value)}${payload.simulated ? ' (sim)' : ''}`);
});
socket.on('actuator_update', payload => {
  if (!payload || !payload.actuator_id) return;
  const stEl = document.getElementById(`actstate-${payload.actuator_id}`);
  if (stEl) stEl.innerText = payload.state;
  log(`Actuator ${payload.actuator_id} -> ${payload.state}`);
});

// init
fetchDevices();