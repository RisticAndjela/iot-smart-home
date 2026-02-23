// tabs.js — improved debug + robust fetch logging
// Replace your existing tabs.js with this to get detailed logs when pressing buttons.

(function () {
  const tabsEl = document.getElementById('piTabs');
  const contentEl = document.getElementById('piTabContent');
  const infoEl = document.getElementById('info');
  const logsEl = document.getElementById('logs');

  function el(tag, cls = '', txt = '') {
    const e = document.createElement(tag);
    if (cls) e.className = cls;
    if (txt !== undefined && txt !== null && txt !== '') e.innerText = txt;
    return e;
  }
  function now() { return new Date().toLocaleTimeString(); }
  function log(msg) {
    console.log(msg);
    if (!logsEl) return;
    const row = document.createElement('div');
    row.innerText = `[${now()}] ${msg}`;
    logsEl.prepend(row);
  }

  function makeTabId(piKey) { return 'tab-' + piKey.replace(/[^a-zA-Z0-9]/g, '').toLowerCase(); }
  function safeDomId(piKey, id) {
    const a = (piKey || '').replace(/[^a-zA-Z0-9]/g, '');
    const b = (id || '').replace(/[^a-zA-Z0-9]/g, '');
    return `status-${a}-${b}`;
  }
  function simKey(piKey, id) { return `${piKey}:${id}`; }

  async function fetchWithLog(url, opts = {}) {
    log(`-> ${opts.method || 'GET'} ${url}`);
    try {
      const res = await fetch(url, opts);
      const text = await res.text().catch(()=>null);
      let body = null;
      try { body = text ? JSON.parse(text) : null; } catch(e) { body = text; }
      log(`<-- ${res.status} ${res.statusText}  ${url}  body=${typeof body === 'string' ? body : JSON.stringify(body)}`);
      // return parsed body when possible, plus status
      return { ok: res.ok, status: res.status, statusText: res.statusText, body, rawText: text };
    } catch (err) {
      log(`!!! Network error ${url}: ${err.message}`);
      return { ok: false, error: err };
    }
  }

  async function fetchSimStatusSet() {
    const r = await fetchWithLog('/api/sim/status', { cache: 'no-store' });
    if (!r.ok) return new Set();
    const arr = (r.body && r.body.running) || [];
    const s = new Set();
    arr.forEach(item => { if (item && item.key) s.add(item.key); });
    return s;
  }

  async function startSim(params) {
    const r = await fetchWithLog('/api/sim/start', {
      method: 'POST',
      headers: {'Content-Type':'application/json'},
      body: JSON.stringify(params)
    });
    if (!r.ok) {
      alert(`Failed to start sim: ${r.status} ${r.statusText}`);
      return false;
    }
    return true;
  }

  async function stopSim(params) {
    const r = await fetchWithLog('/api/sim/stop', {
      method: 'POST',
      headers: {'Content-Type':'application/json'},
      body: JSON.stringify(params)
    });
    if (!r.ok) {
      alert(`Failed to stop sim: ${r.status} ${r.statusText}`);
      return false;
    }
    return true;
  }

  async function sendSensorCommand(sensorId, body) {
    const r = await fetchWithLog(`/api/sensors/${sensorId}/command`, {
      method: 'POST',
      headers: {'Content-Type':'application/json'},
      body: JSON.stringify(body)
    });
    if (!r.ok) {
      alert(`Sensor command failed: ${r.status} ${r.statusText}`);
      return null;
    }
    return r.body;
  }

  function renderSensorCard(s, piKey) {
    const col = el('div','col-md-4');
    const card = el('div','card p-3');
    card.dataset.piKey = piKey;
    card.dataset.compId = s.id;

    card.appendChild(el('h6','mb-2', `${s.device || s.id} (${s.id})`));

    const meta = el('div','mb-2 sensor-meta');
    meta.appendChild(el('span','badge bg-secondary sensor-tag', s.type || 'sensor'));
    if (s.simulated) meta.appendChild(el('span','badge bg-warning ms-1 sensor-tag','simulated'));
    const statusId = safeDomId(piKey, s.id);
    const runBadge = el('span','badge bg-success ms-2','running');
    runBadge.id = statusId;
    runBadge.style.display = 'none';
    meta.appendChild(runBadge);
    card.appendChild(meta);

    const valueEl = el('div','fs-4 fw-bold mb-2','—');
    valueEl.id = `value-${s.id}`;
    card.appendChild(valueEl);

    const ctrl = el('div','d-flex flex-column gap-2');

    const simRow = el('div','d-flex gap-2');
    const startBtn = el('button','btn btn-sm btn-outline-success','Start sim');
    startBtn.onclick = async () => {
      const ok = await startSim({ pi: piKey, id: s.id });
      if (ok) {
        log(`Started sim for ${s.id}`);
        await refreshSimBadges();
      }
    };
    const stopBtn = el('button','btn btn-sm btn-outline-danger','Stop sim');
    stopBtn.onclick = async () => {
      const ok = await stopSim({ pi: piKey, id: s.id });
      if (ok) {
        log(`Stopped sim for ${s.id}`);
        await refreshSimBadges();
      }
    };
    simRow.appendChild(startBtn); simRow.appendChild(stopBtn);
    ctrl.appendChild(simRow);

    const stype = (s.type || '').toLowerCase();

    if (['binary','door','button','membrane','ir','infrared','motion'].includes(stype)) {
      const rowBtns = el('div','d-flex gap-2');
      const onBtn = el('button','btn btn-sm btn-success','ON');
      onBtn.onclick = async () => {
        const res = await sendSensorCommand(s.id, { command:'set', value:'on' });
        log(`Set on -> ${JSON.stringify(res)}`);
      };
      const offBtn = el('button','btn btn-sm btn-danger','OFF');
      offBtn.onclick = async () => {
        const res = await sendSensorCommand(s.id, { command:'set', value:'off' });
        log(`Set off -> ${JSON.stringify(res)}`);
      };
      const trigger = el('button','btn btn-sm btn-primary','Trigger');
      trigger.onclick = async () => {
        const res = await sendSensorCommand(s.id, { command:'trigger' });
        log(`Trigger -> ${JSON.stringify(res)}`);
      };
      const toggle = el('button','btn btn-sm btn-secondary','Toggle');
      toggle.onclick = async () => {
        const res = await sendSensorCommand(s.id, { command:'toggle' });
        log(`Toggle -> ${JSON.stringify(res)}`);
      };
      rowBtns.appendChild(onBtn); rowBtns.appendChild(offBtn); rowBtns.appendChild(trigger); rowBtns.appendChild(toggle);
      ctrl.appendChild(rowBtns);
    } else {
      // generic set/read UI
      const row = el('div','d-flex gap-2 align-items-center');
      const input = el('input','form-control form-control-sm'); input.placeholder='value';
      input.style.width='140px';
      const setBtn = el('button','btn btn-sm btn-primary','Set');
      setBtn.onclick = async () => {
        if (!input.value) { alert('Unesi vrednost'); return; }
        let val = input.value;
        const n = Number(val);
        if (!isNaN(n) && val.trim() !== '') val = n;
        const res = await sendSensorCommand(s.id, { command:'set', value: val });
        log(`Set ${s.id} -> ${JSON.stringify(res)}`);
      };
      const readBtn = el('button','btn btn-sm btn-outline-secondary','Read');
      readBtn.onclick = async () => {
        const res = await sendSensorCommand(s.id, {});
        log(`Read ${s.id} -> ${JSON.stringify(res)}`);
      };
      row.appendChild(input); row.appendChild(setBtn); row.appendChild(readBtn);
      ctrl.appendChild(row);
    }

    card.appendChild(ctrl);
    col.appendChild(card);
    return col;
  }

  async function renderTabsWithSensors(settings) {
    tabsEl.innerHTML = '';
    contentEl.innerHTML = '';
    const keys = Object.keys(settings || {});
    for (let i=0;i<keys.length;i++) {
      const k = keys[i];
      const tabId = makeTabId(k);
      const btn = el('button','tab-btn');
      if (i===0) btn.classList.add('active');
      btn.id = `${tabId}-btn`; btn.setAttribute('data-tab-id', tabId); btn.innerText = k;
      btn.onclick = () => activateTabById(tabId);
      tabsEl.appendChild(btn);

      const pane = el('div','tab-pane fade'); if (i===0) pane.classList.add('show','active');
      pane.id = tabId;

      const header = el('div','d-flex align-items-center mb-3');
      header.appendChild(el('h4','me-3', k));
      const ctrl = el('div','ms-auto d-flex gap-2');
      const startAll = el('button','btn btn-sm btn-outline-success','Start all sims');
      startAll.onclick = async () => {
        const sensorsObj = settings[k].sensors || {};
        for (const sid of Object.keys(sensorsObj)) {
          await startSim({ pi: k, id: sid });
        }
        await refreshSimBadges();
      };
      const stopAll = el('button','btn btn-sm btn-outline-danger','Stop all sims');
      stopAll.onclick = async () => {
        const sensorsObj = settings[k].sensors || {};
        for (const sid of Object.keys(sensorsObj)) {
          await stopSim({ pi: k, id: sid });
        }
        await refreshSimBadges();
      };
      ctrl.appendChild(startAll); ctrl.appendChild(stopAll);
      header.appendChild(ctrl);
      pane.appendChild(header);

      const grid = el('div','row g-3');
      const sensorsObj = settings[k].sensors || {};
      Object.keys(sensorsObj).forEach(id => {
        const sconf = Object.assign({}, sensorsObj[id], { id: id, device: sensorsObj[id].device || id });
        const col = renderSensorCard(sconf, k);
        grid.appendChild(col);
      });

      pane.appendChild(grid);
      contentEl.appendChild(pane);
    }
    infoEl.innerText = `Loaded ${keys.length} PI(s) from settings`;
    await refreshSimBadges();
  }

  function activateTabById(tabId) {
    tabsEl.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
    contentEl.querySelectorAll('.tab-pane').forEach(p => p.classList.remove('show','active'));
    const btn = document.getElementById(`${tabId}-btn`); if (btn) btn.classList.add('active');
    const pane = document.getElementById(tabId); if (pane) pane.classList.add('show','active');
  }

  async function refreshSimBadges() {
    const running = await fetchWithLog('/api/sim/status', { cache:'no-store' });
    const set = new Set();
    if (running.ok && running.body && Array.isArray(running.body.running)) {
      running.body.running.forEach(r => { if (r && r.key) set.add(r.key); });
    }
    document.querySelectorAll('.card').forEach(card => {
      const pk = card.dataset.piKey;
      const id = card.dataset.compId;
      const sid = safeDomId(pk, id);
      const badge = document.getElementById(sid);
      if (!badge) return;
      const key = simKey(pk, id);
      if (set.has(key)) { badge.style.display='inline-block'; badge.innerText='running'; }
      else { badge.style.display='none'; }
    });
  }

  // socket live updates
  const socket = window.io ? io() : null;
  if (socket) {
    socket.on('connect', () => log('Socket connected'));
    socket.on('sensor_update', payload => {
      if (!payload || !payload.sensor_id) return;
      const id = payload.sensor_id;
      const v = payload.value;
      const simulated = payload.simulated;
      const elv = document.getElementById(`value-${id}`);
      if (!elv) return;
      let display = v;
      if (v && typeof v === 'object') {
        const parts = [];
        if (v.temperature !== undefined) parts.push(`${v.temperature}°C`);
        if (v.humidity !== undefined) parts.push(`${v.humidity}%`);
        display = parts.join(' / ');
      } else if (!isNaN(Number(v))) display = Number(v);
      elv.innerText = display + (simulated ? ' Ⓢ' : '');
    });
  } else {
    log('Socket.IO not available on this page');
  }

  // init
  document.addEventListener('DOMContentLoaded', async () => {
    try {
      const r = await fetchWithLog('/api/settings', { cache:'no-store' });
      if (!r.ok) { infoEl.innerText = `Failed to fetch settings: ${r.status}`; return; }
      const raw = r.body || {};
      // uppercase keys
      const settings = {};
      Object.keys(raw || {}).forEach(k => settings[String(k).toUpperCase()] = raw[k]);
      await renderTabsWithSensors(settings);
    } catch (e) {
      log('Init error: ' + (e && e.message ? e.message : e));
      infoEl.innerText = 'Error loading settings (see console)';
    }
  });
})();