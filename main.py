import os
os.environ["FAKE_RPI_DISABLE_PRINT"] = "1"
import threading
import sys
import json

from influxdb_client import InfluxDBClient
from influxdb_client.client.write_api import SYNCHRONOUS

from messaging.batch_publisher import batch_publisher
from messaging.client import create_mqtt_client
from settings import load_settings
from simulation.state.global_state import global_state
from simulation.console.command_bus import enqueue_command

# --- SIMULACIJA ---
try:
    import RPi.GPIO as GPIO
except ImportError:
    import fake_rpi
    fake_rpi.toggle_print(False)
    print("fake_rpi module path:", getattr(fake_rpi, "__file__", "NOFILE"))
    print("fake_rpi print enabled?", getattr(fake_rpi, "print_enabled", "UNKNOWN"))
    print("GPIO class:", type(GPIO))
    sys.modules["RPi"] = fake_rpi.RPi
    sys.modules["RPi.GPIO"] = fake_rpi.RPi.GPIO
    import RPi.GPIO as GPIO

# Don't do global GPIO setup at import time; do it defensively here.
try:
    GPIO.setmode(GPIO.BCM)
except Exception:
    pass

# --- Import komponenti ---
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

from database.sensor_service import write_event_to_influx

# --- InfluxDB config ---
influx_url = "http://localhost:8086"
influx_token = "iot-super-token"
influx_org = "FTN"
influx_bucket = "iot-sensor-report"


def closing_main(stop_event, controller_thread, threads):
    print("Stopping all threads... ")
    stop_event.set()

    if controller_thread:
        controller_thread.join()

    for t in threads:
        t.join()

    print("App stopped cleanly.")


def on_message_received(client, userdata, msg):
    """
    Handles inbound MQTT messages.

    We subscribe to:
      - commands/piX/#  (commands for this PI client)
      - sensors/# and actuators/# (for logging / optional aggregation)

    IMPORTANT:
      - Do not directly control actuators here.
      - Enqueue commands to the controller queue instead, so console + mqtt + frontend behave the same.
    """
    try:
        payload = json.loads(msg.payload.decode(errors="replace"))
        topic = msg.topic or ""

        parts = [p for p in topic.strip("/").split("/") if p]
        base = parts[0].lower() if len(parts) > 0 else ""
        topic_device = parts[2].lower() if len(parts) > 2 else ""

        device = str(payload.get("device") or topic_device or "").upper()
        ev_type = str(payload.get("type") or payload.get("sensor_type") or "").lower()
        value = payload.get("value")
        command = payload.get("command")

        # --- DHT state aggregation for LCD rotation (works with old and new formats) ---
        if base == "sensors" and "DHT" in device:
            d_id = device.lower()

            # Old/new style: event.type == "temperature"/"humidity" OR legacy sensor_type
            if ev_type in ("temperature", "humidity"):
                if ev_type == "temperature":
                    global_state[f"{d_id}_temp"] = value
                else:
                    global_state[f"{d_id}_hum"] = value

            # Optional: "type": "dht" and "value": {"temperature":..., "humidity":...}
            elif ev_type == "dht" and isinstance(value, dict):
                if "temperature" in value:
                    global_state[f"{d_id}_temp"] = value["temperature"]
                if "humidity" in value:
                    global_state[f"{d_id}_hum"] = value["humidity"]

        # --- Commands handling: forward to controller queue ---
        if base == "commands":
            # normalize command text
            cmd_text = (value or command or "").strip().lower()

            # Device-aware mapping (optional)
            if device == "DB" or topic_device == "db":
                if cmd_text == "on":
                    enqueue_command("b")
                elif cmd_text == "off":
                    enqueue_command("boff")
                else:
                    # allow raw commands too
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
                # expect cmd_text = "red"/"green"/"blue"/"white"/"off"
                if cmd_text:
                    enqueue_command(f"brgb_{cmd_text}")

            else:
                # Generic passthrough
                if cmd_text:
                    enqueue_command(cmd_text)

    except Exception as e:
        print(f"[MQTT] Error handling message topic={msg.topic}: {e}")


if __name__ == "__main__":
    print("Starting app")

    settings = load_settings()
    threads = []
    stop_event = threading.Event()

    # --- Influx client (single writer: event_queue -> batch_publisher -> write_callback) ---
    influx_client = InfluxDBClient(url=influx_url, token=influx_token, org=influx_org)
    write_api = influx_client.write_api(write_options=SYNCHRONOUS)

    def influx_write_callback(event):
        write_event_to_influx(write_api, influx_bucket, event)

    try:
        # --- MQTT client + publisher thread ---
        mqtt_client = create_mqtt_client(on_message_callback=on_message_received)

        publisher_thread = threading.Thread(
            target=batch_publisher,
            args=(mqtt_client, stop_event),
            kwargs={"write_callback": influx_write_callback},
            daemon=True,
        )
        publisher_thread.start()

    except Exception as e:
        print(f"MQTT Error: {e}")
        mqtt_client = None

    controller_thread = None
    dl = None
    db = None
    brgb = None

    try:
        for pi_id in settings:
            pi_settings = settings[pi_id]
            sensors = pi_settings.get("sensors", {})
            actuators = pi_settings.get("actuators", {})

            # --- SENSORS ---
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

            # --- ACTUATORS ---
            if "DL" in actuators:
                pins_config = actuators["DL"].get("pins")
                if pins_config:
                    dl = DoorLight(pins=pins_config)
                else:
                    dl = DoorLight(pins={"r": actuators["DL"]["pin"], "g": 0, "b": 0})

            if "DB" in actuators:
                db = DoorBuzzer(pin=actuators["DB"]["pin"])

            if pi_id == "PI3" and "BRGB" in actuators:
                brgb = RGB_LED(actuators["BRGB"])
                print("RGB LED initialized on PI3")

            if pi_id == "PI3" and "LCD" in actuators:
                run_lcd(actuators["LCD"], threads, stop_event)
                print("LCD initialized on PI3")

            if pi_id == "PI2" and "4SD" in actuators:
                run_4sd(actuators["4SD"], threads, stop_event)

        # Start controller ONCE (it owns actuator control + actuator event emission)
        if dl or db or brgb:
            controller_thread = run_controller(dl, db, brgb, stop_event)

        # Single interactive loop (no second input() loop)
        console_loop(stop_event)

    except KeyboardInterrupt:
        print("KeyboardInterrupt detected.")

    finally:
        try:
            influx_client.close()
        except Exception:
            pass

        closing_main(stop_event, controller_thread, threads)