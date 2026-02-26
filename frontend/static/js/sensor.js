
function qs(name) {
  const params = new URLSearchParams(window.location.search);
  return params.get(name);
}
function el(tag, cls = '', txt = '') {
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
function safeDomId(piKey, id) {
  const a = (piKey || '').replace(/[^a-zA-Z0-9]/g, '');
  const b = (id || '').replace(/[^a-zA-Z0-9]/g, '');
  return `status-${a}-${b}`;
}
function simKey(piKey, id) {
  return `${piKey}:${id}`;
}

/* State */
const socket = io();
let DEVICE = null; // device details
let runningSet = new Set();

/* Fetch helpers */
async function fetchSimStatusSet() {
  try {
    const res = await fetch('/api/sim/status');
    if (!res.ok) return new Set();
    const data = await res.json();
    const s = new Set();
    (data.running || []).forEach(r => { if (r && r.key) s.add(r.key); });
    return s;
  } catch (e) {
    console.warn('fetchSimStatusSet error', e);
    return new Set();
  }
}

async function startSim(params) {
  try {
    const res = await fetch('/api/sim/start', {
      method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify(params)
    });
    const txt = await res.text().catch(()=>null);
    if (!res.ok) { log('Failed starting simulation: ' + (txt||res.status)); return false; }
    log('Started simulation: ' + (txt||'ok'));
    runningSet = await fetchSimStatusSet();
    refreshSimBadges();
    return true;
  } catch (e) { log('Error startSim: ' + e.message); return false; }
}

async function stopSim(params) {
  try {
    const res = await fetch('/api/sim/stop', {
      method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify(params)
    });
    const txt = await res.text().catch(()=>null);
    if (!res.ok) { log('Failed stopping simulation: ' + (txt||res.status)); return false; }
    log('Stopped simulation: ' + (txt||'ok'));
    runningSet = await fetchSimStatusSet();
    refreshSimBadges();
    return true;
  } catch (e) { log('Error stopSim: ' + e.message); return false; }
}

async function sendSensorCommand(sensorId, body) {
  try {
    const res = await fetch(`/api/sensors/${sensorId}/command`, {
      method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify(body)
    });
    if (!res.ok) {
      const txt = await res.text().catch(()=>null);
      log(`Sensor ${sensorId} command failed: ${res.status} ${txt||''}`);
      return;
    }
    const json = await res.json();
    log(`Sensor ${sensorId} command ${JSON.stringify(body)} -> ${JSON.stringify(json)}`);
    // refresh sim badges (in case command started instance)
    runningSet = await fetchSimStatusSet();
    refreshSimBadges();
  } catch (e) {
    log('Error sending sensor command: ' + e.message);
  }
}

/* Rendering */
function renderSensors(sensors, device) {
  const row = document.getElementById('sensorsRow');
  row.innerHTML = '';
  sensors.forEach(s => {
    const col = el('div','col-md-4');
    const card = el('div','card p-3');
    card.dataset.piKey = device.pi_key || `PI${device.pi}`;
    card.dataset.compId = s.id;

    const title = el('h6','mb-2', `${s.name} (${s.code})`);
    card.appendChild(title);

    const meta = el('div','mb-2 sensor-meta');
    meta.appendChild(el('span','badge bg-secondary sensor-tag', s.type || 'sensor'));
    if (s.simulated) meta.appendChild(el('span','badge bg-warning ms-1 sensor-tag','simulated'));
    const statusId = safeDomId(device.pi_key || `PI${device.pi}`, s.id);
    const runBadge = el('span','badge bg-success ms-2','running');
    runBadge.id = statusId;
    runBadge.style.display = 'none';
    meta.appendChild(runBadge);
    card.appendChild(meta);

    // value display
    const valueEl = el('div','fs-4 fw-bold mb-2','—');
    valueEl.id = `value-${s.id}`;
    card.appendChild(valueEl);

    // controls
    const ctrl = el('div','d-flex flex-column gap-2');

    // Row for start/stop sim
    const simRow = el('div','d-flex gap-2');
    const startBtn = el('button','btn btn-sm btn-outline-success','Start sim');
    startBtn.onclick = () => startSim({ pi: device.pi_key || `PI${device.pi}`, id: s.id });
    const stopBtn = el('button','btn btn-sm btn-outline-danger','Stop sim');
    stopBtn.onclick = () => stopSim({ pi: device.pi_key || `PI${device.pi}`, id: s.id });
    simRow.appendChild(startBtn); simRow.appendChild(stopBtn);
    ctrl.appendChild(simRow);

    const stype = (s.type || '').toLowerCase();

    // controls by type
    if (['binary','door','button','membrane','ir','infrared','motion'].includes(stype)) {
      const rowBtns = el('div','d-flex gap-2');
      const trigger = el('button','btn btn-sm btn-primary','Trigger');
      trigger.onclick = () => sendSensorCommand(s.id, { command: 'trigger' });
      const toggle = el('button','btn btn-sm btn-secondary','Toggle');
      toggle.onclick = () => sendSensorCommand(s.id, { command: 'toggle' });
      rowBtns.appendChild(trigger); rowBtns.appendChild(toggle);
      ctrl.appendChild(rowBtns);
    } else if (['distance','ultrasonic'].includes(stype)) {
      const rowSet = el('div','d-flex gap-2 align-items-center');
      const input = el('input','form-control form-control-sm');
      input.type = 'number'; input.placeholder = 'cm'; input.style.width = '110px';
      const setBtn = el('button','btn btn-sm btn-primary','Set');
      setBtn.onclick = () => {
        const v = parseFloat(input.value);
        if (isNaN(v)) { log('Unesi broj za distance'); return; }
        sendSensorCommand(s.id, { command: 'set', value: v });
      };
      const readNow = el('button','btn btn-sm btn-outline-secondary','Read');
      readNow.onclick = () => sendSensorCommand(s.id, {});
      rowSet.appendChild(input); rowSet.appendChild(setBtn); rowSet.appendChild(readNow);
      ctrl.appendChild(rowSet);
    } else if (stype === 't/h' || stype === 'dht' || stype === 'temperature' || stype === 'humidity') {
      const rowTH = el('div','d-flex gap-2 align-items-center');
      const tinput = el('input','form-control form-control-sm'); tinput.type='number'; tinput.placeholder='temp'; tinput.style.width='110px';
      const hinput = el('input','form-control form-control-sm'); hinput.type='number'; hinput.placeholder='hum'; hinput.style.width='110px';
      const setBtn = el('button','btn btn-sm btn-primary','Set T/H');
      setBtn.onclick = () => {
        const t = parseFloat(tinput.value);
        const h = parseFloat(hinput.value);
        const payload = {};
        if (!isNaN(t)) payload.temperature = t;
        if (!isNaN(h)) payload.humidity = h;
        if (Object.keys(payload).length === 0) { log('Unesi temp ili hum'); return; }
        sendSensorCommand(s.id, { command: 'set', value: payload });
      };
      const readNow = el('button','btn btn-sm btn-outline-secondary','Read');
      readNow.onclick = () => sendSensorCommand(s.id, {});
      rowTH.appendChild(tinput); rowTH.appendChild(hinput); rowTH.appendChild(setBtn); rowTH.appendChild(readNow);
      ctrl.appendChild(rowTH);
    } else if (['display','text'].includes(stype)) {
      const rowText = el('div','d-flex gap-2 align-items-center');
      const txt = el('input','form-control form-control-sm'); txt.type='text'; txt.placeholder='text';
      const sendBtn = el('button','btn btn-sm btn-primary','Send');
      sendBtn.onclick = () => {
        if (!txt.value) { log('Unesi tekst'); return; }
        sendSensorCommand(s.id, { command: 'set', value: String(txt.value) });
      };
      ctrl.appendChild(rowText);
      rowText.appendChild(txt); rowText.appendChild(sendBtn);
    } else {
      // generic: offer Read and Set (number/text)
      const rowGeneric = el('div','d-flex gap-2 align-items-center');
      const input = el('input','form-control form-control-sm'); input.type='text'; input.placeholder='value';
      input.style.width = '140px';
      const setBtn = el('button','btn btn-sm btn-primary','Set');
      setBtn.onclick = () => {
        if (!input.value) { log('Unesi vrednost'); return; }
        let v = input.value;
        // try parse number
        const n = Number(v);
        if (!isNaN(n) && v.trim() !== '') v = n;
        sendSensorCommand(s.id, { command: 'set', value: v });
      };
      const readNow = el('button','btn btn-sm btn-outline-secondary','Read');
      readNow.onclick = () => sendSensorCommand(s.id, {});
      rowGeneric.appendChild(input); rowGeneric.appendChild(setBtn); rowGeneric.appendChild(readNow);
      ctrl.appendChild(rowGeneric);
    }

    card.appendChild(ctrl);
    col.appendChild(card);
    document.getElementById('sensorsRow').appendChild(col);
  });

  // after render refresh badges
  refreshSimBadges();
}

/* Update UI on sensor update events */
function updateSensorValueUI(sensorId, value, simulated=false) {
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
}

/* Refresh sim badges based on runningSet */
function refreshSimBadges() {
  document.querySelectorAll('[data-comp-id]').forEach(()=>{}); // noop to avoid linter
  document.querySelectorAll('[data-comp-id]').forEach(()=>{}); // noop
  // simpler: find all cards and update the badge by card dataset
  document.querySelectorAll('.card').forEach(card => {
    const piKey = card.dataset.pikey || card.dataset.piKey || card.getAttribute('data-pi-key') || card.getAttribute('data-pi-key'.toLowerCase());
    const compId = card.dataset.compId || card.getAttribute('data-comp-id');
    // try fallback using earlier attributes
    const pk = card.dataset.piKey || card.getAttribute('data-pi-key') || card.getAttribute('data-pikey') || card.getAttribute('data-pi') || '';
    const id = card.dataset.compId || card.getAttribute('data-comp-id') || compId;
    if (!pk || !id) {
      // sometimes we attached values only in dataset when creating, but ensure we read properly
    }
    const key = simKey(pk || (DEVICE && DEVICE.pi_key) || `PI${DEVICE && DEVICE.pi}`, id || '');
    const sid = safeDomId((DEVICE && DEVICE.pi_key) || `PI${DEVICE && DEVICE.pi}`, id || '');
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

/* Init flow */
async function init() {
  // decide desired device id
  let piParam = qs('pi') || qs('device');
  if (!piParam) {
    document.getElementById('info')?.innerText = 'No device specified. Open /sensors?pi=PI1';
    return;
  }
  // normalize: accept PI1 or pi1 -> device id is lower-case (backend)
  const desiredKey = (piParam || '').toUpperCase();
  try {
    // get devices list
    const devicesRes = await fetch('/api/devices', { cache: 'no-store' });
    if (!devicesRes.ok) { log('Failed to fetch devices'); return; }
    const devices = await devicesRes.json();
    // find device by pi_key or id
    let dev = devices.find(d => d.pi_key === desiredKey || d.id === (desiredKey || '').toLowerCase() || d.name === desiredKey);
    if (!dev) {
      // try uppercase/lowercase variants
      dev = devices.find(d => d.id.toUpperCase() === desiredKey);
    }
    if (!dev) {
      log('Device not found: ' + desiredKey);
      document.getElementById('deviceTitle').innerText = `Device not found: ${desiredKey}`;
      return;
    }
    // fetch details
    const res = await fetch(`/api/devices/${dev.id}/details`, { cache: 'no-store' });
    if (!res.ok) { log('Failed to fetch device details'); return; }
    const data = await res.json();
    DEVICE = data;
    document.getElementById('deviceTitle').innerText = `${data.name} (PI${data.pi})`;
    renderSensors(data.sensors || [], data);

    // wire start/stop all
    document.getElementById('startAllBtn').onclick = async () => {
      const pk = data.pi_key || `PI${data.pi}`;
      for (const s of (data.sensors || [])) await startSim({ pi: pk, id: s.id });
    };
    document.getElementById('stopAllBtn').onclick = async () => {
      const pk = data.pi_key || `PI${data.pi}`;
      for (const s of (data.sensors || [])) await stopSim({ pi: pk, id: s.id });
    };

    // get running set once
    runningSet = await fetchSimStatusSet();
    refreshSimBadges();

    // socket handling
    socket.on('connect', () => log('Socket connected'));
    socket.on('sensor_update', payload => {
      if (!payload || !payload.sensor_id) return;
      updateSensorValueUI(payload.sensor_id, payload.value, payload.simulated);
      log(`Sensor ${payload.sensor_id} = ${JSON.stringify(payload.value)}${payload.simulated ? ' (sim)' : ''}`);
    });

  } catch (e) {
    console.error('Init error', e);
    log('Init error: ' + e.message);
  }
}

document.addEventListener('DOMContentLoaded', init);