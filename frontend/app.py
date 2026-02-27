import os
import sys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))          # .../root/frontend
PROJECT_ROOT = os.path.abspath(os.path.join(BASE_DIR, ".."))   # .../root
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import json
import time
import threading

from flask import Flask, render_template, jsonify, request
from flask_socketio import SocketIO

import paho.mqtt.client as mqtt

from settings import load_settings
from simulation.state.global_state import global_state
from simulation.console.command_bus import enqueue_command

# --- SIMULACIJA GPIO (kao u main.py) ---
os.environ["FAKE_RPI_DISABLE_PRINT"] = "1"
try:
    import RPi.GPIO as GPIO  # type: ignore
except ImportError:
    import fake_rpi  # type: ignore

    fake_rpi.toggle_print(False)
    print("fake_rpi module path:", getattr(fake_rpi, "__file__", "NOFILE"))
    print("fake_rpi print enabled?", getattr(fake_rpi, "print_enabled", "UNKNOWN"))
    sys.modules["RPi"] = fake_rpi.RPi
    sys.modules["RPi.GPIO"] = fake_rpi.RPi.GPIO
    import RPi.GPIO as GPIO  # type: ignore

try:
    GPIO.setmode(GPIO.BCM)
except Exception:
    pass

# --- Import komponenti (kao u main.py) ---
from simulation.components.ds import run_ds
from simulation.components.uds import run_uds
from simulation.components.pir import run_pir
from simulation.components.dms import run_dms
from simulation.components.dht import run_dht
from simulation.components.gyro import run_gyro
from simulation.components.btn import run_btn
from simulation.components.ir import run_ir

from simulation.actuators.display import run_4sd
from simulation.actuators.dl1 import DoorLight
from simulation.actuators.db1 import DoorBuzzer
from simulation.actuators.lcd import run_lcd
from simulation.actuators.brgb import RGB_LED
from simulation.actuators.controller import run_controller

from simulation.console.console import console_loop

# --- Publisher pipeline (kao u main.py) ---
from messaging.batch_publisher import batch_publisher

# --- Influx (opciono) ---
try:
    from influxdb_client import InfluxDBClient
    from influxdb_client.client.write_api import SYNCHRONOUS
    from database.sensor_service import write_event_to_influx
except Exception:
    InfluxDBClient = None  # type: ignore
    SYNCHRONOUS = None  # type: ignore
    write_event_to_influx = None  # type: ignore


app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*")

SETTINGS_PATH = os.path.abspath(os.path.join(BASE_DIR, "..", "settings.json"))

raw_settings = {}
if os.path.exists(SETTINGS_PATH):
    with open(SETTINGS_PATH, "r", encoding="utf-8") as f:
        raw_settings = json.load(f)

MQTT_HOST = os.getenv("MQTT_HOST", os.getenv("MQTT_BROKER", "localhost"))
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))

# Influx config (opciono)
INFLUX_URL = os.getenv("INFLUX_URL", "http://localhost:8086")
INFLUX_TOKEN = os.getenv("INFLUX_TOKEN", "iot-super-token")
INFLUX_ORG = os.getenv("INFLUX_ORG", "FTN")
INFLUX_BUCKET = os.getenv("INFLUX_BUCKET", "iot-sensor-report")
ENABLE_INFLUX = os.getenv("ENABLE_INFLUX", "1").strip().lower() in ("1", "true", "yes", "on")

# UI views (Grafana + webcam)
GRAFANA_URL = os.getenv("GRAFANA_URL", "http://localhost:3000")
WEBCAM_URL = os.getenv("WEBCAM_URL", "")  # npr: http://localhost:8081/stream ili http://pi3:8081/stream

mqtt_client = mqtt.Client(
    client_id=f"dashboard-main-{os.getpid()}",
    callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
)
mqtt_connected = False
mqtt_lock = threading.Lock()

# Latest event cache (for snapshots)
LATEST = {}  # key -> event dict

# Threads / stop control
threads = []
stop_event = threading.Event()
controller_thread = None
publisher_thread = None
console_thread = None

# Actuators (controller owns them)
dl = None
db = None
brgb = None


def _normalize_pi_topic(pi) -> str:
    if pi is None:
        return "piunknown"
    s = str(pi).strip().lower()
    if s.startswith("pi"):
        return s
    return f"pi{s}"


def latest_key(ev: dict) -> str:
    pi = str(ev.get("pi") or ev.get("pi_id") or "").strip()
    device = str(ev.get("device") or "").upper().strip()
    kind = str(ev.get("kind") or "sensor").lower().strip()
    typ = str(ev.get("type") or ev.get("sensor_type") or "unknown").lower().strip()
    return f"{kind}:{pi}:{device}:{typ}"


def update_latest(ev: dict):
    pi = str(ev.get("pi") or ev.get("pi_id") or "").strip()
    device = str(ev.get("device") or "").upper().strip()
    kind = str(ev.get("kind") or "sensor").lower().strip()
    typ = str(ev.get("type") or ev.get("sensor_type") or "unknown").lower().strip()

    LATEST[latest_key(ev)] = {
        "pi": pi,
        "device": device,
        "kind": kind,
        "type": typ,
        "value": ev.get("value"),
        "timestamp": ev.get("timestamp", time.time()),
        "simulated": bool(ev.get("simulated", True)),
    }


def build_snapshot():
    return {
        "ts": int(time.time() * 1000),
        "mqtt_connected": mqtt_connected,
        "people_count": int(global_state.get("people_count", 0)),
        "alarm_active": bool(global_state.get("alarm_active", False)),
        "items": list(LATEST.values()),
    }


def snapshot_emitter():
    while not stop_event.is_set():
        socketio.sleep(1.0)
        try:
            socketio.emit("snapshot", build_snapshot())
        except Exception as e:
            print("[DASH] snapshot_emitter error:", e)


def handle_command_message(topic: str, payload: dict):
    parts = [p for p in (topic or "").strip("/").split("/") if p]
    base = parts[0].lower() if len(parts) > 0 else ""
    topic_device = parts[2].lower() if len(parts) > 2 else ""

    device = str(payload.get("device") or topic_device or "").upper()
    value = payload.get("value")
    command = payload.get("command")

    if base != "commands":
        return

    cmd_text = (value or command or "")
    cmd_text = str(cmd_text).strip().lower()

    if not cmd_text:
        return

    if device == "DB" or topic_device == "db":
        if cmd_text == "on":
            enqueue_command("b")
        elif cmd_text == "off":
            enqueue_command("boff")
        else:
            enqueue_command(cmd_text)

    elif device == "DL" or topic_device == "dl":
        if cmd_text in ("toggle", ""):
            enqueue_command("l")
        elif cmd_text == "on":
            enqueue_command("dl_on")
        elif cmd_text == "off":
            enqueue_command("dl_off")
        else:
            enqueue_command(cmd_text)

    elif device == "BRGB" or topic_device == "brgb":
        enqueue_command(f"brgb_{cmd_text}")

    else:
        enqueue_command(cmd_text)

def handle_sensor_aggregation(topic: str, payload: dict):
    parts = [p for p in (topic or "").strip("/").split("/") if p]
    base = parts[0].lower() if len(parts) > 0 else ""

    topic_device = parts[2].lower() if len(parts) > 2 else ""
    device = str(payload.get("device") or topic_device or "").upper()
    ev_type = str(payload.get("type") or payload.get("sensor_type") or "").lower()
    value = payload.get("value")

    if base != "sensors":
        return

    # -----------------------------
    # DHT -> global_state (vec imas)
    # -----------------------------
    if "DHT" in device:
        d_id = device.lower()

        if ev_type in ("temperature", "humidity"):
            if ev_type == "temperature":
                global_state[f"{d_id}_temp"] = value
            else:
                global_state[f"{d_id}_hum"] = value

        elif ev_type == "dht" and isinstance(value, dict):
            if "temperature" in value:
                global_state[f"{d_id}_temp"] = value["temperature"]
            if "humidity" in value:
                global_state[f"{d_id}_hum"] = value["humidity"]

        return  # DHT handled

    # -----------------------------
    # DPIR (motion) -> motion_dpirX
    # -----------------------------
    if device in ("DPIR1", "DPIR2", "DPIR3") and ev_type == "motion":
        motion = bool(value) and str(value) != "0"
        if device == "DPIR1":
            global_state["motion_dpir1"] = motion
        elif device == "DPIR2":
            global_state["motion_dpir2"] = motion
        elif device == "DPIR3":
            global_state["motion_dpir3"] = motion
        return

    # -----------------------------
    # DUS (ultrasonic) -> dusX_dist + dusX_prev_dist
    # -----------------------------
    if device in ("DUS1", "DUS2") and ev_type in ("ultrasonic", "distance"):
        try:
            dist = float(value)
        except (TypeError, ValueError):
            return

        if device == "DUS1":
            prev = global_state.get("dus1_dist", 0.0)
            global_state["dus1_prev_dist"] = prev
            global_state["dus1_dist"] = dist
        else:
            prev = global_state.get("dus2_dist", 0.0)
            global_state["dus2_prev_dist"] = prev
            global_state["dus2_dist"] = dist
        return

    # -----------------------------
    # DS (door) -> door_open
    # -----------------------------
    if device in ("DS1", "DS2") and ev_type in ("door", "reed", "contact"):
        door_is_open = bool(value) and str(value) != "0"

        # cuvaj i pojedinacno, korisno za debug/spec
        if device == "DS1":
            global_state["ds1_open"] = door_is_open
        else:
            global_state["ds2_open"] = door_is_open

        # agregat koji controller vec koristi
        global_state["door_open"] = bool(global_state.get("ds1_open")) or bool(global_state.get("ds2_open"))
        return

    # -----------------------------
    # GSG (gyro) -> significant_motion_gsg
    # -----------------------------
    if device == "GSG" and ev_type in ("gyro", "accelerometer"):
        try:
            v = float(value)
        except (TypeError, ValueError):
            return
        # prag: ako je daleko od "mirnog" ~9.81
        global_state["significant_motion_gsg"] = abs(v - 9.81) > 1.5
        return

    # -----------------------------
    # DMS (membrane)
    # -----------------------------
    if device == "DMS1" and ev_type in ("membrane", "keypad"):
        global_state["last_dms_key"] = value

def mqtt_on_connect(client, userdata, flags, rc, properties=None):
    global mqtt_connected
    mqtt_connected = True
    print(f"[DASH MQTT] Connected rc={rc}")

    client.subscribe("sensors/#")
    client.subscribe("actuators/#")
    client.subscribe("commands/#")
    client.subscribe("events/#")
    print("[DASH MQTT] Subscribed: sensors/#, actuators/#, commands/#, events/#")

def mqtt_on_disconnect(client, userdata, rc, properties=None):
    global mqtt_connected
    mqtt_connected = False
    print(f"[DASH MQTT] Disconnected rc={rc}")


def mqtt_on_log(client, userdata, level, buf):
    print("[DASH MQTT LOG]", buf)


def mqtt_on_message(client, userdata, msg):
    try:
        payload = json.loads(msg.payload.decode(errors="replace"))
        topic = msg.topic or ""

        update_latest(payload)
        handle_sensor_aggregation(topic, payload)
        handle_command_message(topic, payload)

        socketio.emit("event", {"topic": topic, "event": payload})
    except Exception as e:
        print(f"[DASH MQTT] message error topic={msg.topic}: {e}")


def mqtt_start():
    mqtt_client.on_connect = mqtt_on_connect
    mqtt_client.on_disconnect = mqtt_on_disconnect
    mqtt_client.on_message = mqtt_on_message
    mqtt_client.on_log = mqtt_on_log
    mqtt_client.reconnect_delay_set(min_delay=1, max_delay=10)

    print(f"[DASH MQTT] connect_async to {MQTT_HOST}:{MQTT_PORT} ...")
    mqtt_client.connect_async(MQTT_HOST, MQTT_PORT, keepalive=60)
    mqtt_client.loop_start()


def mqtt_publish_command(cmd: str, device_id: str | None):
    """
    Publish a controller command to selected PI topic:
      commands/piX/controller
    """
    cmd = str(cmd).strip()
    if not cmd:
        raise ValueError("Empty cmd")

    pi = "pi1"
    if device_id:
        s = str(device_id).strip().lower()
        if s.startswith("pi"):
            pi = s
        else:
            pi = f"pi{s}"

    topic = f"commands/{_normalize_pi_topic(pi)}/controller"
    payload = json.dumps({"value": cmd})

    with mqtt_lock:
        if not mqtt_connected:
            raise RuntimeError("MQTT not connected")
        mqtt_client.publish(topic, payload)


def start_simulation_from_settings(settings: dict):
    global dl, db, brgb, controller_thread

    for pi_id in settings:
        pi_settings = settings[pi_id]
        sensors = pi_settings.get("sensors", {})
        actuators = pi_settings.get("actuators", {})

        if pi_id == "PI1":
            if "DS1" in sensors:
                run_ds(sensors["DS1"], threads, stop_event)
            if "DUS1" in sensors:
                run_uds(sensors["DUS1"], threads, stop_event)
            if "DPIR1" in sensors:
                run_pir(sensors["DPIR1"], threads, stop_event)
            if "DMS1" in sensors:
                run_dms(sensors["DMS1"], threads, stop_event)

        if pi_id == "PI2":
            if "DS2" in sensors:
                run_ds(sensors["DS2"], threads, stop_event)
            if "DUS2" in sensors:
                run_uds(sensors["DUS2"], threads, stop_event)
            if "DPIR2" in sensors:
                run_pir(sensors["DPIR2"], threads, stop_event)
            if "BTN" in sensors:
                run_btn(sensors["BTN"], threads, stop_event)
            if "DHT3" in sensors:
                run_dht(sensors["DHT3"], threads, stop_event)
            if "GSG" in sensors:
                run_gyro(sensors["GSG"], threads, stop_event)

        if pi_id == "PI3":
            if "DHT1" in sensors:
                run_dht(sensors["DHT1"], threads, stop_event)
            if "DHT2" in sensors:
                run_dht(sensors["DHT2"], threads, stop_event)
            if "IR" in sensors:
                run_ir(sensors["IR"], threads, stop_event)
            if "DPIR3" in sensors:
                run_pir(sensors["DPIR3"], threads, stop_event)

        if "DL" in actuators and dl is None:
            pins_config = actuators["DL"].get("pins")
            if pins_config:
                dl = DoorLight(pins=pins_config)
            else:
                dl = DoorLight(pins={"r": actuators["DL"]["pin"], "g": 0, "b": 0})

        if "DB" in actuators and db is None:
            db = DoorBuzzer(pin=actuators["DB"]["pin"])

        if pi_id == "PI3" and "BRGB" in actuators and brgb is None:
            brgb = RGB_LED(actuators["BRGB"])
            print("[DASH] RGB LED initialized on PI3")

        if pi_id == "PI3" and "LCD" in actuators:
            run_lcd(actuators["LCD"], threads, stop_event)
            print("[DASH] LCD initialized on PI3")

        if pi_id == "PI2" and "4SD" in actuators:
            run_4sd(actuators["4SD"], threads, stop_event)
            print("[DASH] 4SD initialized on PI2")

    if dl or db or brgb:
        controller_thread = run_controller(dl, db, brgb, stop_event)
        print("[DASH] Controller started.")
    else:
        print("[DASH] No actuators found in settings; controller not started.")


def closing_main():
    print("Stopping all threads... ")
    stop_event.set()

    try:
        if controller_thread:
            controller_thread.join(timeout=3)
    except Exception:
        pass

    for t in list(threads):
        try:
            t.join(timeout=3)
        except Exception:
            pass

    try:
        if publisher_thread:
            publisher_thread.join(timeout=3)
    except Exception:
        pass

    print("App stopped cleanly.")


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/ui_config")
def api_ui_config():
    # frontend koristi da popuni iframe/img url-ove
    return jsonify(
        {
            "grafana_url": GRAFANA_URL,
            "webcam_url": WEBCAM_URL,
        }
    )


@app.route("/api/settings")
def api_settings():
    return jsonify(raw_settings)


@app.route("/api/devices")
def api_devices():
    devices_list = []
    for pi_id, pi_data in raw_settings.items():
        devices_list.append(
            {
                "id": pi_id,
                "name": pi_id,
                "pi": pi_id.replace("PI", ""),
                "description": pi_data.get("description", ""),
            }
        )
    return jsonify(devices_list)


@app.route("/api/devices/<device_id>/details")
def api_device_details(device_id):
    pi_key = device_id.upper()
    conf = raw_settings.get(pi_key)
    if not conf:
        return jsonify({"error": "Not found"}), 404

    sensors = []
    for s_id, s_data in conf.get("sensors", {}).items():
        s_obj = s_data.copy()
        s_obj["id"] = s_id
        s_obj["name"] = s_data.get("device", s_id)
        s_obj["code"] = s_data.get("device", s_id)
        sensors.append(s_obj)

    actuators = []
    for a_id, a_data in conf.get("actuators", {}).items():
        a_obj = a_data.copy()
        a_obj["id"] = a_id
        a_obj["name"] = a_data.get("device", a_id)
        a_obj["code"] = a_data.get("device", a_id)

        typ = a_obj.get("type", "").lower()
        if typ in ("light", "buzzer", "binary", "led"):
            a_obj["kind"] = "binary"
        elif typ in ("rgb", "brgb"):
            a_obj["kind"] = "rgb"
        elif typ in ("display", "4sd", "lcd"):
            a_obj["kind"] = "text"
        else:
            a_obj["kind"] = "binary"

        actuators.append(a_obj)

    return jsonify(
        {
            "id": pi_key,
            "name": pi_key,
            "pi": pi_key.replace("PI", ""),
            "description": conf.get("description", ""),
            "sensors": sensors,
            "actuators": actuators,
        }
    )


@app.route("/api/commands", methods=["POST"])
def api_commands():
    body = request.get_json() or {}
    cmd = body.get("cmd")
    device_id = body.get("deviceId")  # e.g. "PI1", "PI2", ...

    if cmd is None or not str(cmd).strip():
        return jsonify({"ok": False, "error": "Missing cmd"}), 400

    try:
        mqtt_publish_command(str(cmd), device_id)
        return jsonify({"ok": True, "cmd": str(cmd), "deviceId": device_id})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@socketio.on("connect")
def on_connect():
    socketio.emit("snapshot", build_snapshot())


if __name__ == "__main__":
    print("[DASH] Starting full system (replaces main.py)")

    settings = load_settings()

    influx_client = None
    influx_write_callback = None

    if ENABLE_INFLUX and InfluxDBClient and write_event_to_influx:
        try:
            influx_client = InfluxDBClient(url=INFLUX_URL, token=INFLUX_TOKEN, org=INFLUX_ORG)
            write_api = influx_client.write_api(write_options=SYNCHRONOUS)

            def influx_write_callback(event):
                write_event_to_influx(write_api, INFLUX_BUCKET, event)

            print("[DASH] Influx enabled.")
        except Exception as e:
            influx_client = None
            influx_write_callback = None
            print("[DASH] Influx disabled (init failed):", e)
    else:
        print("[DASH] Influx disabled.")

    try:
        mqtt_start()

        publisher_thread = threading.Thread(
            target=batch_publisher,
            args=(mqtt_client, stop_event),
            kwargs={"write_callback": influx_write_callback},
            daemon=True,
        )
        publisher_thread.start()
        print("[DASH] batch_publisher started.")

        start_simulation_from_settings(settings)

        socketio.start_background_task(snapshot_emitter)

        console_thread = threading.Thread(target=console_loop, args=(stop_event,), daemon=True)
        console_thread.start()
        print("[DASH] console_loop started (daemon).")

        print("--- Dashboard running on http://localhost:5000 ---")
        socketio.run(app, host="0.0.0.0", port=5000, debug=True, use_reloader=False)

    except KeyboardInterrupt:
        print("KeyboardInterrupt detected.")

    finally:
        try:
            if influx_client:
                influx_client.close()
        except Exception:
            pass

        closing_main()