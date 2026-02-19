import os
import json
import random
import time
import threading
import signal
import sys
from types import SimpleNamespace

from flask import Flask, jsonify, request, send_file, send_from_directory
from flask_socketio import SocketIO
import os, sys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(BASE_DIR, ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)
    
from messaging.client import create_mqtt_client
from messaging import event_queue
from messaging.batch_publisher import batch_publisher

# --- Paths
SETTINGS_PATH = os.path.abspath(os.path.join(BASE_DIR, '..', 'settings.json'))
FRONTEND_DIR = BASE_DIR                                      # index/templates are expected under frontend/
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

# --- Load settings.json
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

# --- MQTT setup: create client and background batch publisher thread
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

# graceful shutdown handlers
def _shutdown_handler(signum, frame):
    print("Received shutdown signal:", signum)
    stop_mqtt_background()
    # give some time to stop
    time.sleep(0.5)
    # let socketio/Flask handle exit
    try:
        sys.exit(0)
    except SystemExit:
        os._exit(0)

signal.signal(signal.SIGINT, _shutdown_handler)
signal.signal(signal.SIGTERM, _shutdown_handler)

# --- Routes

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

@app.route('/api/data')
def api_data():
    return jsonify({"devices": DEVICES, "latest": LATEST})

@app.route('/api/actuators/<actuator_id>/command', methods=['POST'])
def actuator_command(actuator_id):
    body = request.get_json() or {}
    for dev_id, acts in ACTUATORS.items():
        for a in acts:
            if a['id'] == actuator_id:
                cmd = body.get('command')
                val = body.get('value')
                if cmd == 'toggle' and a.get('kind') == 'binary':
                    a['state'] = 'on' if a.get('state') != 'on' else 'off'
                elif cmd == 'set':
                    a['state'] = val
                else:
                    a['state'] = val if val is not None else a.get('state')
                socketio.emit('actuator_update', {'actuator_id': actuator_id, 'state': a['state']})
                return jsonify({"ok": True, "state": a['state']})
    return jsonify({"error": "actuator not found"}), 404

@app.route('/api/sensors/<sensor_id>/command', methods=['POST'])
def sensor_command(sensor_id):
    body = request.get_json() or {}
    cmd = body.get('command')
    val = body.get('value', None)

    for dev_id, sensors in SENSORS.items():
        for s in sensors:
            if s['id'] == sensor_id:
                sensor_type = str(s.get('type','')).lower()
                if cmd == 'toggle' and sensor_type in ('binary','door','button','membrane','ir','motion'):
                    prev = LATEST.get(sensor_id, {}).get('value', 0)
                    newv = 0 if prev else 1
                    payload_val = newv
                elif cmd == 'set':
                    payload_val = val
                elif cmd == 'trigger':
                    payload_val = val if val is not None else 1
                else:
                    if val is None:
                        return jsonify({"error":"missing command or value"}), 400
                    payload_val = val

                payload = {
                    'device_id': dev_id,
                    'sensor_id': sensor_id,
                    'value': payload_val,
                    'simulated': True,
                    'ts': int(time.time()*1000)
                }
                LATEST[sensor_id] = payload
                socketio.emit('sensor_update', payload)

                try:
                    evt = SimpleNamespace(
                        pi_id=dev_id,
                        device=sensor_id,
                        sensor_type=sensor_type,
                        value=payload_val,
                        simulated=payload['simulated'],
                        timestamp=payload['ts']
                    )
                    event_queue.put(evt)
                except Exception as e:
                    print("Failed to enqueue sensor event:", e)

                return jsonify({"ok": True, "payload": payload})
    return jsonify({"error":"sensor not found"}), 404

# --- Background emitter
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

if __name__ == "__main__":
    # initialize LATEST
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