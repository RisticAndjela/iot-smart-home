import os
import sys
import json
import random
import time
import threading
import signal
from types import SimpleNamespace
from typing import Optional
from types import SimpleNamespace
import time

from flask import Flask, jsonify, request, send_file, send_from_directory
from flask_socketio import SocketIO

import logging, sys
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s %(name)s: %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)
logger.info("App start")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(BASE_DIR, ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

try:
    import RPi.GPIO as GPIO
except Exception:
    try:
        import fake_rpi
        if hasattr(fake_rpi, "RPi"): sys.modules['RPi'] = fake_rpi.RPi
        if hasattr(fake_rpi, "RPi") and hasattr(fake_rpi.RPi, "GPIO"): sys.modules['RPi.GPIO'] = fake_rpi.RPi.GPIO
        import RPi.GPIO as GPIO  # type: ignore
    except Exception:
        import types
        class _GPIOShim:
            BCM = 11
            OUT = 1
            IN = 0
            PUD_UP = 2
            PUD_DOWN = 3

            def __init__(self):
                self._pin_states = {}
            def setmode(self, mode):
                pass
            def setup(self, pin, mode, pull_up_down=None):
                self._pin_states[pin] = 0
            def output(self, pin, value):
                self._pin_states[pin] = value
            def input(self, pin):
                return self._pin_states.get(pin, 0)
            def setwarnings(self, flag):
                pass
            def cleanup(self):
                self._pin_states.clear()
        fake_rpi_mod = types.ModuleType('fake_rpi')
        fake_rpi_mod.RPi = types.SimpleNamespace(GPIO=_GPIOShim())
        sys.modules['fake_rpi'] = fake_rpi_mod
        rpimod = types.ModuleType('RPi')
        rpimod.GPIO = _GPIOShim()
        sys.modules['RPi'] = rpimod
        gpmod = types.ModuleType('RPi.GPIO')
        gpio_shim = _GPIOShim()
        gpmod.setmode = gpio_shim.setmode
        gpmod.setup = gpio_shim.setup
        gpmod.output = gpio_shim.output
        gpmod.input = gpio_shim.input
        gpmod.cleanup = gpio_shim.cleanup
        gpmod.setwarnings = gpio_shim.setwarnings
        gpmod.BCM = gpio_shim.BCM
        gpmod.OUT = gpio_shim.OUT
        gpmod.IN = gpio_shim.IN
        gpmod.PUD_UP = gpio_shim.PUD_UP
        gpmod.PUD_DOWN = gpio_shim.PUD_DOWN
        sys.modules['RPi.GPIO'] = gpmod
        import RPi.GPIO as GPIO 
try:
    GPIO.setmode(GPIO.BCM)
except Exception:
    pass

from messaging.client import create_mqtt_client
from messaging import event_queue
from messaging.batch_publisher import batch_publisher
from simulation.components.ds import run_ds
from simulation.components.uds import run_uds
from simulation.components.pir import run_pir
from simulation.components.dms import run_dms
from simulation.components.dht import run_dht
from simulation.components.gyro import run_gyro
from simulation.components.btn import run_btn
from simulation.actuators.display import run_4sd
from simulation.actuators.dl1 import DoorLight
from simulation.actuators.db1 import DoorBuzzer
from simulation.actuators.controller import run_controller

SETTINGS_PATH = os.path.abspath(os.path.join(BASE_DIR, '..', 'settings.json'))
FRONTEND_DIR = BASE_DIR
TEMPLATES_INDEX = os.path.join(FRONTEND_DIR, 'templates', 'index.html')
STATIC_DIR = os.path.join(FRONTEND_DIR, 'static')

app = Flask(__name__, static_folder=STATIC_DIR, static_url_path='/static')
socketio = SocketIO(app, cors_allowed_origins="*")

print("BASE_DIR:", BASE_DIR)
print("SETTINGS_PATH:", SETTINGS_PATH)
print("FRONTEND_DIR:", FRONTEND_DIR)
print("STATIC_DIR:", STATIC_DIR)
print("index exists?:", os.path.exists(TEMPLATES_INDEX))
print("settings exists?:", os.path.exists(SETTINGS_PATH))

raw_settings = {}
if os.path.exists(SETTINGS_PATH):
    try:
        with open(SETTINGS_PATH, 'r', encoding='utf-8') as f:
            raw_settings = json.load(f)
            print("Loaded settings.json keys:", list(raw_settings.keys()))
    except Exception as e:
        print("Failed to load settings.json:", e)
else:
    print("Warning: settings.json not found at", SETTINGS_PATH)

DEVICES = []
SENSORS = {}
ACTUATORS = {}

for pi_key, pi_val in raw_settings.items():
    dev_id = pi_key.lower()
    DEVICES.append({
        "id": dev_id,
        "name": f"{pi_key}",
        "pi": pi_key.replace('PI',''),
        "pi_key": pi_key,
        "description": pi_val.get('description', '')
    })
    SENSORS[dev_id] = []
    for s_key, s_conf in pi_val.get('sensors', {}).items():
        sensor_obj = {
            "id": s_key,
            "code": s_conf.get('device', s_key),
            "name": s_conf.get('device', s_key),
            "type": s_conf.get('type', 'unknown'),
            "simulated": bool(s_conf.get('simulated', False)),
            "mqtt_topic": s_conf.get('mqtt_topic'),
        }
        for k in ('pin','pin_trig','pin_echo','pins'):
            if k in s_conf:
                sensor_obj[k] = s_conf[k]
        SENSORS[dev_id].append(sensor_obj)
    ACTUATORS[dev_id] = []
    for a_key, a_conf in pi_val.get('actuators', {}).items():
        typ = a_conf.get('type', '').lower()
        if typ in ('light','buzzer','binary','led'):
            kind = 'binary'
        elif typ in ('rgb','led-rgb','brgb'):
            kind = 'rgb'
        elif typ in ('display','4sd','lcd','text'):
            kind = 'text'
        else:
            kind = 'binary' if a_conf.get('pin') else 'text'
        actuator_obj = {
            "id": a_key,
            "code": a_conf.get('device', a_key),
            "name": a_conf.get('device', a_key),
            "type": typ,
            "kind": kind,
            "simulated": bool(a_conf.get('simulated', False)),
            "mqtt_topic": a_conf.get('mqtt_topic'),
            "state": a_conf.get('state', None)
        }
        if 'pin' in a_conf: actuator_obj['pin'] = a_conf['pin']
        if 'pins' in a_conf: actuator_obj['pins'] = a_conf['pins']
        ACTUATORS[dev_id].append(actuator_obj)

LATEST = {}

def _random_value_for(sensor_type):
    st = (sensor_type or '').lower()
    if st in ('t/h','dht','dht3','dht1','temperature','humidity'):
        return round(18 + random.random()*10, 1)
    if st in ('distance','ultrasonic'):
        return round(5 + random.random()*295, 1)
    if st in ('binary','door','button','membrane','ir'):
        return random.choice([0, 1])
    if st in ('motion','pir'):
        return random.choice([0, 1])
    if st in ('gyro','gsg'):
        return round(random.uniform(-180, 180), 2)
    if st in ('display','text'):
        return f"{random.randint(0,59):02d}:{random.randint(0,59):02d}"
    if st in ('rgb','color'):
        return random.choice(['#ff0000','#00ff00','#0000ff','#ffffff'])
    return round(random.random()*100, 2)

mqtt_client = None
_mqtt_stop_event = threading.Event()
_mqtt_thread = None

def start_mqtt_background(client_id="WEBAPP", batch_size=10, interval=5):
    global mqtt_client, _mqtt_thread
    try:
        mqtt_client = create_mqtt_client(client_id=client_id)
        _mqtt_stop_event.clear()
        _mqtt_thread = threading.Thread(
            target=batch_publisher,
            args=(mqtt_client, _mqtt_stop_event, batch_size, interval, None),
            daemon=True
        )
        _mqtt_thread.start()
        print("Started MQTT client and batch_publisher thread")
    except Exception as e:
        print("Failed to start MQTT background:", e)

def stop_mqtt_background():
    global mqtt_client
    try:
        _mqtt_stop_event.set()
        if mqtt_client:
            try:
                mqtt_client.loop_stop()
            except Exception:
                pass
            try:
                mqtt_client.disconnect()
            except Exception:
                pass
        print("Stopped MQTT background")
    except Exception as e:
        print("Error while stopping MQTT:", e)

app_threads = []            # will be passed to run_* functions (they append threads here)
sim_registry = {}          # key -> { 'pi','id','stop_event','threads' }
sim_lock = threading.Lock()

def _key(pi, ident):
    return f"{pi or ''}:{ident or ''}"

def _get_conf(pi, ident):
    if pi not in raw_settings:
        return None
    return raw_settings[pi].get('sensors', {}).get(ident) or raw_settings[pi].get('actuators', {}).get(ident)

@app.route('/')
def index():
    if os.path.exists(TEMPLATES_INDEX):
        return send_file(TEMPLATES_INDEX)
    alt = os.path.join(FRONTEND_DIR, 'index.html')
    if os.path.exists(alt):
        return send_file(alt)
    return "index.html not found. Checked: {} and {}".format(TEMPLATES_INDEX, alt), 404

@app.route('/static/<path:filename>')
def static_files(filename):
    return send_from_directory(STATIC_DIR, filename)

@app.route('/api/settings')
def api_settings():
    return jsonify(raw_settings)

@app.route('/api/devices')
def api_devices():
    return jsonify(DEVICES)

@app.route('/api/devices/<device_id>/details')
def api_device_details(device_id):
    dev = next((d for d in DEVICES if d['id'] == device_id), None)
    if not dev:
        return jsonify({'error': 'not found'}), 404
    sensors = SENSORS.get(device_id, [])
    actuators = ACTUATORS.get(device_id, [])
    return jsonify({**dev, "sensors": sensors, "actuators": actuators})

@app.route('/api/sim/start', methods=['POST'])
def api_sim_start():
    """
    Body examples:
      {"pi":"PI2","id":"DS2"}  -> starts that sensor using its run_* function
      {"component":"controller"} -> starts controller (finds DL/DB in settings)
    """
    body = request.get_json() or {}
    component = (body.get('component') or '').lower() if body.get('component') else None
    pi = body.get('pi')
    ident = body.get('id')
    if component == 'controller':
        key = 'controller'
    else:
        if not pi or not ident:
            return jsonify({"error":"pi and id required"}), 400
        key = _key(pi, ident)

    with sim_lock:
        if key in sim_registry:
            return jsonify({"ok": False, "reason": "already running", "key": key}), 409

        stop_event = threading.Event()
        sim_registry[key] = {"pi": pi, "id": ident, "stop_event": stop_event, "threads": []}

        try:
            # controller special case
            if component == 'controller':
                # try to construct dl and db from settings (like in main.py)
                dl_obj = None
                db_obj = None
                for pi_k, pi_conf in raw_settings.items():
                    for a_k, a_c in pi_conf.get('actuators', {}).items():
                        t = a_c.get('type','').lower()
                        if not dl_obj and t in ('brgb','rgb','led-rgb','light'):
                            dl_obj = DoorLight(pins=a_c.get('pins') or {'r': a_c.get('pin'), 'g':0, 'b':0})
                        if not db_obj and t in ('buzzer','db','led','binary'):
                            db_obj = DoorBuzzer(pin=a_c.get('pin'))
                        if dl_obj and db_obj:
                            break
                    if dl_obj and db_obj:
                        break
                if not dl_obj or not db_obj:
                    del sim_registry[key]
                    return jsonify({"error":"dl/db not found for controller"}), 404
                thr = run_controller(dl_obj, db_obj, stop_event)
                sim_registry[key]["threads"].append(thr)
                sim_registry[key]["instance"] = {"dl": dl_obj, "db": db_obj}
                return jsonify({"ok": True, "key": key})

            # normal sensor/actuator start
            conf = _get_conf(pi, ident)
            if conf is None:
                del sim_registry[key]
                return jsonify({"error":"config not found"}), 404

            # choose runner by id prefix or by type
            prefix = ''.join([c for c in ident if not c.isdigit()]).upper()
            stype = (conf.get('type') or '').lower()

            # map to runner
            if prefix.startswith('DS'):
                run_ds(conf, app_threads, stop_event)
            elif prefix.startswith('DUS') or stype in ('ultrasonic','distance','ir'):
                run_uds(conf, app_threads, stop_event)
            elif prefix.startswith('DPIR') or stype in ('pir','motion'):
                run_pir(conf, app_threads, stop_event)
            elif prefix.startswith('DMS'):
                run_dms(conf, app_threads, stop_event)
            elif prefix.startswith('DHT') or stype.startswith('dht') or stype in ('t/h','temperature','humidity'):
                run_dht(conf, app_threads, stop_event)
            elif prefix.startswith('GSG') or stype in ('gyro','gsg'):
                run_gyro(conf, app_threads, stop_event)
            elif prefix in ('BTN',):
                run_btn(conf, app_threads, stop_event)
            elif prefix == '4SD' or stype in ('4sd','display','lcd','text'):
                run_4sd(conf, app_threads, stop_event)
            elif prefix in ('DL',):
                # create DoorLight instance and store it
                dl_obj = DoorLight(pins=conf.get('pins') or {'r': conf.get('pin'), 'g':0, 'b':0})
                sim_registry[key]["instance"] = dl_obj
            elif prefix in ('DB',):
                db_obj = DoorBuzzer(pin=conf.get('pin'))
                sim_registry[key]["instance"] = db_obj
            else:
                # fallback: if type indicates binary actuator, create DoorBuzzer-like or just store config
                sim_registry[key]["info"] = {"started": False, "note": "unknown component, no runner called"}
                del sim_registry[key]
                return jsonify({"error":"unknown component type/prefix"}), 400

            # run_* functions append threads into app_threads; store snapshot of new threads
            sim_registry[key]["threads"] = list(app_threads)
            return jsonify({"ok": True, "key": key})
        except Exception as e:
            # cleanup on error
            sim_registry.pop(key, None)
            return jsonify({"ok": False, "error": str(e)}), 500

@app.route('/api/sim/stop', methods=['POST'])
def api_sim_stop():
    body = request.get_json() or {}
    component = (body.get('component') or '').lower() if body.get('component') else None
    pi = body.get('pi')
    ident = body.get('id')
    if component == 'controller':
        key = 'controller'
    else:
        if not pi or not ident:
            return jsonify({"error":"pi and id required"}), 400
        key = _key(pi, ident)

    with sim_lock:
        entry = sim_registry.get(key)
        if not entry:
            return jsonify({"ok": False, "reason": "not running", "key": key}), 404
        try:
            entry['stop_event'].set()
            # try to call off() on instances if present
            inst = entry.get('instance')
            if inst:
                if hasattr(inst, 'off'):
                    try: inst.off()
                    except Exception: pass
                if isinstance(inst, dict):
                    for v in inst.values():
                        if hasattr(v, 'off'):
                            try: v.off()
                            except Exception: pass
            # join threads if possible (short timeout)
            for t in entry.get('threads', []):
                try:
                    if isinstance(t, threading.Thread):
                        t.join(timeout=1.0)
                except Exception:
                    pass
            del sim_registry[key]
            return jsonify({"ok": True, "key": key})
        except Exception as e:
            return jsonify({"ok": False, "error": str(e)}), 500

@app.route('/api/sim/status', methods=['GET'])
def api_sim_status():
    with sim_lock:
        out = []
        for k, v in sim_registry.items():
            out.append({
                "key": k,
                "pi": v.get('pi'),
                "id": v.get('id'),
                "running": not bool(v.get('stop_event') and v.get('stop_event').is_set())
            })
    return jsonify({"running": out})

@app.route('/api/actuators/<actuator_id>/command', methods=['POST'])
def api_actuator_command(actuator_id):
    body = request.get_json() or {}
    with sim_lock:
        entry = next((v for v in sim_registry.values() if v.get('id') == actuator_id), None)
    if not entry:
        return jsonify({"ok": False, "error": "not running", "code": "not_running"}), 404
    inst = entry.get('instance')
    if not inst:
        return jsonify({"ok": False, "error": "no instance available for actuator"}), 400

    cmd = body.get('command')
    val = body.get('value')
    state = None
    try:
        # common on/off
        if val == 'on' or cmd == 'on':
            if hasattr(inst, 'on'):
                try:
                    inst.on() if callable(inst.on) else None
                except TypeError:
                    # some implementations accept params
                    try: inst.on(val)
                    except Exception: pass
            state = 'on'
        elif val == 'off' or cmd == 'off':
            if hasattr(inst, 'off'):
                inst.off()
            state = 'off'
        else:
            # if value looks like a color string, try to pass as color for lights
            if isinstance(val, str) and val.startswith('#') and hasattr(inst, 'on'):
                try:
                    inst.on(color=val)
                    state = val
                except TypeError:
                    try:
                        inst.on(val)
                        state = val
                    except Exception:
                        pass
            else:
                # generic set if available
                if hasattr(inst, 'set'):
                    try:
                        inst.set(val)
                        state = 'set'
                    except Exception:
                        pass
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

    return jsonify({"ok": True, "state": state})

@app.route('/api/sensors/<sensor_id>/command', methods=['POST'])
def api_sensor_command(sensor_id):
    body = request.get_json() or {}
    with sim_lock:
        entry = next((v for v in sim_registry.values() if v.get('id') == sensor_id), None)
    if not entry:
        # fallback: try to find conf and enqueue a synthetic event so UI sees something
        conf = None
        for pk, pv in raw_settings.items():
            if sensor_id in pv.get('sensors', {}):
                conf = pv['sensors'][sensor_id]
                pi_key = pk
                break
        # enqueue a simple event as fallback
        try:
            evt = SimpleNamespace(
                pi_id=pi_key if conf else None,
                device=sensor_id,
                sensor_type=conf.get('type') if conf else None,
                value=body.get('value') if body.get('value') is not None else _random_value_for(conf.get('type') if conf else None),
                simulated=True,
                timestamp=int(time.time()*1000)
            )
            event_queue.put(evt)
        except Exception:
            pass
        return jsonify({"ok": True, "payload": {"note": "enqueued fallback event"}}), 200

    inst = entry.get('instance')
    resp_payload = {"note": "ok"}
    try:
        cmd = body.get('command')
        val = body.get('value')
        if inst:
            # try known ops
            if cmd == 'trigger' and hasattr(inst, 'trigger'):
                inst.trigger()
            elif cmd == 'toggle' and hasattr(inst, 'toggle'):
                inst.toggle()
            elif cmd == 'set' and hasattr(inst, 'set'):
                inst.set(val)
            else:
                # if instance has a generic method to accept data -> try
                if hasattr(inst, 'set_value'):
                    try:
                        inst.set_value(val)
                    except Exception:
                        pass
        else:
            # enqueue an event that matches shape used elsewhere
            evt = SimpleNamespace(
                pi_id=entry.get('pi'),
                device=sensor_id,
                sensor_type=_get_conf(entry.get('pi'), sensor_id).get('type') if _get_conf(entry.get('pi'), sensor_id) else None,
                value=val if val is not None else _random_value_for(None),
                simulated=True,
                timestamp=int(time.time()*1000)
            )
            event_queue.put(evt)
            resp_payload['enqueued'] = True
        resp_payload['value'] = val
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

    return jsonify({"ok": True, "payload": resp_payload}), 200

def emitter():
    while True:
        for dev_id, sensors in SENSORS.items():
            for s in sensors:
                val = _random_value_for(s.get('type'))
                payload = {
                    'device_id': dev_id,
                    'sensor_id': s['id'],
                    'value': val,
                    'simulated': bool(s.get('simulated', True)),
                    'ts': int(time.time()*1000)
                }
                LATEST[s['id']] = payload
                socketio.emit('sensor_update', payload)

                try:
                    evt = SimpleNamespace(
                        pi_id=dev_id,
                        device=s['id'],
                        sensor_type=s.get('type'),
                        value=val,
                        simulated=payload['simulated'],
                        timestamp=payload['ts']
                    )
                    event_queue.put(evt)
                except Exception as e:
                    print("Failed to enqueue emitter event:", e)

                socketio.sleep(0.01)
        socketio.sleep(5)

@socketio.on('connect')
def on_connect():
    for v in LATEST.values():
        socketio.emit('sensor_update', v)

def _shutdown_handler(signum, frame):
    print("Received shutdown signal:", signum)
    stop_mqtt_background()
    with sim_lock:
        for entry in list(sim_registry.values()):
            ev = entry.get('stop_event')
            if ev:
                ev.set()
    time.sleep(0.5)
    try:
        sys.exit(0)
    except SystemExit:
        os._exit(0)

signal.signal(signal.SIGINT, _shutdown_handler)
signal.signal(signal.SIGTERM, _shutdown_handler)

if __name__ == "__main__":
    for dev_id, sensors in SENSORS.items():
        for s in sensors:
            LATEST[s['id']] = {
                'device_id': dev_id,
                'sensor_id': s['id'],
                'value': _random_value_for(s.get('type')),
                'simulated': bool(s.get('simulated', True)),
                'ts': int(time.time()*1000)
            }

    start_mqtt_background(client_id="WEBAPP", batch_size=10, interval=5)
    socketio.start_background_task(emitter)
    socketio.run(app, host='0.0.0.0', port=5000)