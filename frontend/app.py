# import os
# import json
# import time
# import threading
# import signal
# import sys
# from flask import Flask, render_template, jsonify, request
# from flask_socketio import SocketIO
# from influxdb_client import InfluxDBClient

# # --- OSNOVNA PODEŠAVANJA ---
# app = Flask(__name__)
# socketio = SocketIO(app, cors_allowed_origins="*")

# # Putanje
# BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# SETTINGS_PATH = os.path.abspath(os.path.join(BASE_DIR, '..', 'settings.json'))

# # InfluxDB podešavanja
# influx_url = "http://localhost:8086" 
# influx_token = "iot-super-token"
# influx_org = "FTN"
# influx_bucket = "iot-sensor-report"
# client = InfluxDBClient(url=influx_url, token=influx_token, org=influx_org)

# # Globalno stanje
# LATEST = {}
# raw_settings = {}

# # --- INICIJALIZACIJA PODATAKA ---
# if os.path.exists(SETTINGS_PATH):
#     with open(SETTINGS_PATH, 'r', encoding='utf-8') as f:
#         raw_settings = json.load(f)
# else:
#     print(f"Greška: settings.json nije nađen na {SETTINGS_PATH}")

# def get_latest_sensor_data():
#     """Vuče poslednje podatke iz InfluxDB baze."""
#     query_api = client.query_api()
#     query = f'from(bucket: "{influx_bucket}") |> range(start: -1h) |> last()'
#     try:
#         tables = query_api.query(query, org=influx_org)
#         results = {}
#         for table in tables:
#             for record in table.records:
#                 device = record.values.get("device")
#                 val = record.get_value()
#                 if device:
#                     results[device] = val
#                     LATEST[device] = {"value": val, "ts": int(time.time()*1000)}
#         return results
#     except Exception as e:
#         print(f"InfluxDB error: {e}")
#         return {}

# # --- API RUTE ---

# @app.route('/')
# def index():
#     data = get_latest_sensor_data()
#     return render_template('index.html', data=data)

# @app.route('/api/devices')
# def api_devices():
#     devices_list = []
#     for pi_id, pi_data in raw_settings.items():
#         devices_list.append({
#             "id": pi_id,
#             "name": pi_id,
#             "pi": pi_id.replace('PI',''),
#             "description": pi_data.get('description', '')
#         })
#     return jsonify(devices_list)

# @app.route('/api/devices/<device_id>/details')
# def api_device_details(device_id):
#     pi_key = device_id.upper()
#     conf = raw_settings.get(pi_key)
#     if not conf:
#         return jsonify({"error": "Not found"}), 404

#     sensors = []
#     for s_id, s_data in conf.get('sensors', {}).items():
#         s_obj = s_data.copy()
#         s_obj['id'] = s_id
#         sensors.append(s_obj)

#     actuators = []
#     for a_id, a_data in conf.get('actuators', {}).items():
#         a_obj = a_data.copy()
#         a_obj['id'] = a_id
#         typ = a_obj.get('type', '').lower()
#         if typ in ('light','buzzer','binary','led'): a_obj['kind'] = 'binary'
#         elif typ in ('rgb','brgb'): a_obj['kind'] = 'rgb'
#         elif typ in ('display','4sd','lcd'): a_obj['kind'] = 'text'
#         else: a_obj['kind'] = 'binary'
#         actuators.append(a_obj) # ISPRAVLJENO: Ovde je bio actuators_list

#     return jsonify({
#         "id": pi_key,
#         "name": pi_key,
#         "pi": pi_key.replace('PI',''),
#         "description": conf.get('description', ''),
#         "sensors": sensors,
#         "actuators": actuators
#     })

# @app.route('/api/actuators/<actuator_id>/command', methods=['POST'])
# def actuator_command(actuator_id):
#     body = request.get_json() or {}
#     val = body.get('value')
#     socketio.emit('actuator_update', {'actuator_id': actuator_id, 'state': val})
#     return jsonify({"ok": True, "state": val})

# @app.route('/api/sensors/<sensor_id>/command', methods=['POST'])
# def sensor_command(sensor_id):
#     body = request.get_json() or {}
#     val = body.get('value')
#     payload = {
#         'sensor_id': sensor_id,
#         'value': val,
#         'simulated': True,
#         'ts': int(time.time()*1000)
#     }
#     LATEST[sensor_id] = payload
#     socketio.emit('sensor_update', payload)
#     return jsonify({"ok": True, "payload": payload})

# @app.route('/api/data')
# def api_data():
#     return jsonify(LATEST)

# # --- POZADINSKI POSLOVI ---

# @socketio.on('connect')
# def on_connect():
#     for sid, data in LATEST.items():
#         socketio.emit('sensor_update', {'sensor_id': sid, 'value': data.get('value'), 'simulated': True})

# def emitter():
#     while True:
#         socketio.sleep(5)
#         pass

# def _shutdown(signum, frame):
#     sys.exit(0)

# signal.signal(signal.SIGINT, _shutdown)

# if __name__ == '__main__':
#     print("--- Dashboard pokrenut na http://localhost:5000 ---")
#     socketio.start_background_task(emitter)
#     socketio.run(app, host='0.0.0.0', port=5000, debug=True)


import os
import json
import time
import threading
import signal
import sys
from flask import Flask, render_template, jsonify, request
from flask_socketio import SocketIO
from influxdb_client import InfluxDBClient

# --- PODEŠAVANJA ---
app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*")

# Putanje
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SETTINGS_PATH = os.path.abspath(os.path.join(BASE_DIR, '..', 'settings.json'))

# InfluxDB
influx_url = "http://localhost:8086" 
influx_token = "iot-super-token"
influx_org = "FTN"
influx_bucket = "iot-sensor-report"
client = InfluxDBClient(url=influx_url, token=influx_token, org=influx_org)

LATEST = {}
raw_settings = {}

if os.path.exists(SETTINGS_PATH):
    with open(SETTINGS_PATH, 'r', encoding='utf-8') as f:
        raw_settings = json.load(f)

def get_latest_sensor_data():
    query_api = client.query_api()
    query = f'from(bucket: "{influx_bucket}") |> range(start: -1h) |> last()'
    try:
        tables = query_api.query(query, org=influx_org)
        results = {}
        for table in tables:
            for record in table.records:
                device = record.values.get("device")
                val = record.get_value()
                if device:
                    results[device] = val
                    LATEST[device] = {"value": val, "ts": int(time.time()*1000)}
        return results
    except Exception as e:
        print(f"InfluxDB error: {e}")
        return {}

# --- API RUTE ---

@app.route('/')
def index():
    # Inicijalno punjenje LATEST podataka iz baze pre renderovanja
    get_latest_sensor_data()
    return render_template('index.html', data=LATEST)

@app.route('/api/devices')
def api_devices():
    devices_list = []
    for pi_id, pi_data in raw_settings.items():
        devices_list.append({
            "id": pi_id,
            "name": pi_id,
            "pi": pi_id.replace('PI',''),
            "description": pi_data.get('description', '')
        })
    return jsonify(devices_list)

@app.route('/api/devices/<device_id>/details')
def api_device_details(device_id):
    pi_key = device_id.upper()
    conf = raw_settings.get(pi_key)
    if not conf:
        return jsonify({"error": "Not found"}), 404

    # Mapiranje senzora: Rešava "undefined" na frontu
    sensors = []
    for s_id, s_data in conf.get('sensors', {}).items():
        s_obj = s_data.copy()
        s_obj['id'] = s_id
        # JS očekuje 'name' i 'code', uzimamo ih iz 'device' ključa u settings.json
        s_obj['name'] = s_data.get('device', s_id)
        s_obj['code'] = s_data.get('device', s_id)
        sensors.append(s_obj)

    # Mapiranje aktuatora
    actuators = []
    for a_id, a_data in conf.get('actuators', {}).items():
        a_obj = a_data.copy()
        a_obj['id'] = a_id
        a_obj['name'] = a_data.get('device', a_id)
        a_obj['code'] = a_data.get('device', a_id)
        
        typ = a_obj.get('type', '').lower()
        if typ in ('light','buzzer','binary','led'): a_obj['kind'] = 'binary'
        elif typ in ('rgb','brgb'): a_obj['kind'] = 'rgb'
        elif typ in ('display','4sd','lcd'): a_obj['kind'] = 'text'
        else: a_obj['kind'] = 'binary'
        actuators.append(a_obj)

    return jsonify({
        "id": pi_key,
        "name": pi_key,
        "pi": pi_key.replace('PI',''),
        "description": conf.get('description', ''),
        "sensors": sensors,
        "actuators": actuators
    })

@app.route('/api/actuators/<actuator_id>/command', methods=['POST'])
def actuator_command(actuator_id):
    body = request.get_json() or {}
    val = body.get('value')
    # Ovdje bi išao tvoj MQTT publish kod ako želiš da kontrolišeš pravi uređaj
    socketio.emit('actuator_update', {'actuator_id': actuator_id, 'state': val})
    return jsonify({"ok": True, "state": val})

@app.route('/api/sensors/<sensor_id>/command', methods=['POST'])
def sensor_command(sensor_id):
    body = request.get_json() or {}
    cmd = body.get('command')
    val = body.get('value')
    
    # Ako je trigger/toggle, simuliramo novu vrednost
    payload_val = val if val is not None else 1
    
    payload = {
        'sensor_id': sensor_id,
        'value': payload_val,
        'simulated': True,
        'ts': int(time.time()*1000)
    }
    LATEST[sensor_id] = payload
    socketio.emit('sensor_update', payload)
    return jsonify({"ok": True, "payload": payload})

@app.route('/api/data')
def api_data():
    return jsonify(LATEST)

# --- SOCKET.IO ---

@socketio.on('connect')
def on_connect():
    for sid, data in LATEST.items():
        socketio.emit('sensor_update', {
            'sensor_id': sid, 
            'value': data.get('value'), 
            'simulated': True
        })

def _shutdown(signum, frame):
    sys.exit(0)

signal.signal(signal.SIGINT, _shutdown)

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5000, debug=True)