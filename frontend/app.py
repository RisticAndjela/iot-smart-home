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
from influxdb_client.client.write_api import SYNCHRONOUS
from influxdb_client import Point


# Dodajemo root folder projekta u putanju da bi Python video 'simulation'
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
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
ACTUATOR_STATES = {}

if os.path.exists(SETTINGS_PATH):
    with open(SETTINGS_PATH, 'r', encoding='utf-8') as f:
        raw_settings = json.load(f)

def get_latest_sensor_data():
    query_api = client.query_api()
    query = f'from(bucket: "{influx_bucket}") |> range(start: -15m) |> last()'
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

write_api = client.write_api(write_options=SYNCHRONOUS)

def write_actuator_to_influx(actuator_id, value):
    """Pomoćna funkcija koja upisuje stanje aktuatora u InfluxDB"""
    try:
        try:
            val_to_save = float(value)
        except:
            val_to_save = value

        point = Point("Kitchen_Timer") \
            .tag("device", actuator_id) \
            .field("value", val_to_save)
        
        write_api.write(bucket=influx_bucket, org=influx_org, record=point)
        print(f" Saved to InfluxDB: {actuator_id} = {val_to_save}")
    except Exception as e:
        print(f" InfluxDB Write Error: {e}")

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


def get_sensor_history(sensor_id, sensor_type):
    """Vuče poslednjih 20 zapisa. Filtrira polje zavisno od tipa senzora."""
    query_api = client.query_api()
    
    # Ako je DHT, uzimamo temperaturu kao primarnu vrednost za mali grafik
    field_filter = 'temperature' if sensor_type.lower() in ['dht', 't/h'] else 'value'
    
    query = f'''
    from(bucket: "{influx_bucket}") 
    |> range(start: -30m) 
    |> filter(fn: (r) => r["device"] == "{sensor_id}")
    |> filter(fn: (r) => r["_field"] == "{field_filter}")
    |> tail(n: 20)
    '''
    try:
        tables = query_api.query(query, org=influx_org)
        history = []
        for table in tables:
            for record in table.records:
                val = record.get_value()
                if val is not None:
                    history.append(float(val))
        return history
    except Exception as e:
        print(f"History error for {sensor_id}: {e}")
        return []

@app.route('/api/devices/<device_id>/details')
def api_device_details(device_id):
    conf = raw_settings.get(device_id.upper())
    if not conf: return jsonify({"error": "Not found"}), 404

    sensors = []
    for s_id, s_data in conf.get('sensors', {}).items():
        s_obj = s_data.copy()
        s_obj.update({'id': s_id, 'name': s_data.get('device', s_id), 'code': s_data.get('device', s_id)})
        s_obj['history'] = get_sensor_history(s_id, s_data.get('type', 'sensor'))
        sensors.append(s_obj)

    actuators = []
    for a_id, a_data in conf.get('actuators', {}).items():
        a_obj = a_data.copy()
        a_obj.update({'id': a_id, 'name': a_data.get('device', a_id), 'code': a_data.get('device', a_id)})
        # POVLAČENJE STANJA IZ MEMORIJE
        a_obj['state'] = ACTUATOR_STATES.get(a_id, 'OFF')
        typ = a_obj.get('type', '').lower()
        a_obj['kind'] = 'rgb' if typ in ('rgb','brgb') else ('text' if typ in ('display','4sd','lcd') else 'binary')
        actuators.append(a_obj)

    return jsonify({"id": device_id, "name": device_id, "pi": device_id.replace('PI',''), "sensors": sensors, "actuators": actuators})

@app.route('/api/data')
def api_data():
    return jsonify(LATEST)

# Dodaj threading u import na vrhu ako već nisi
import threading

# Globalni rečnik za praćenje aktivnih tajmera
active_countdowns = {}

def start_countdown(actuator_id, start_value):
    def countdown():
        current_val = start_value
        while current_val >= 0:
            # Provera da li je u međuvremenu pokrenut novi tajmer
            if active_countdowns.get(actuator_id) != start_value: 
                break 
            
            ACTUATOR_STATES[actuator_id] = str(current_val)
            
            # 1. UPIS U BAZU (svake sekunde ili po želji)
            write_actuator_to_influx(actuator_id, current_val)
            
            # 2. SLANJE NA FRONTEND
            socketio.emit('actuator_update', {'actuator_id': actuator_id, 'state': str(current_val)})
            
            time.sleep(1)
            current_val -= 1
            
    active_countdowns[actuator_id] = start_value
    thread = threading.Thread(target=countdown)
    thread.daemon = True
    thread.start()

@app.route('/api/actuators/<actuator_id>/command', methods=['POST'])
def actuator_command(actuator_id):
    body = request.get_json() or {}
    val = body.get('value')
    
    # 1. ODMAH UPIŠI U INFLUX (Početna vrednost)
    # Ovo osigurava da baza zna da je odbrojavanje krenulo od npr. 60
    write_actuator_to_influx(actuator_id, val)
    
    # 2. LOGIKA ZA 4SD TAJMER
    if "4SD" in actuator_id.upper():
        try:
            # Proveri putanju! Ako je u 'controllers' folderu, koristi tu putanju
            from simulation.actuators.controller import get_cmd_queue
            
            # Šaljemo samo čist broj u queue, lakše je za obradu u run_4sd
            get_cmd_queue().put(val) 
            print(f"[API] Poslat startni broj {val} za {actuator_id}")
            
        except ImportError as e:
            print(f"[ERROR] Ne mogu da nađem kontroler: {e}")
        except Exception as e:
            print(f"[ERROR] Neočekivana greška: {e}")

    # 3. SOCKET.IO EMIT (Da dashboard odmah promeni cifru)
    ACTUATOR_STATES[actuator_id] = val
    socketio.emit('actuator_update', {'actuator_id': actuator_id, 'state': val})
    
    return jsonify({"ok": True, "state": val})

@app.route('/api/sensors/<sensor_id>/command', methods=['POST'])
def sensor_command(sensor_id):
    val = request.get_json().get('value', 1)
    payload = {'sensor_id': sensor_id, 'value': val, 'simulated': True, 'ts': int(time.time()*1000)}
    socketio.emit('sensor_update', payload)
    return jsonify({"ok": True, "payload": payload})
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