import threading
import time

from messaging.event_queue import event_queue
from simulation.sensors.sensor_event import SensorEvent
from simulation.state.global_state import global_state


def run_btn(settings, threads, stop_event):
    device_name = settings["device"]
    pi_id = settings["pi"]
    simulated = settings.get("simulated", True)
    pin = settings.get("pin", 26)

    def process_btn(val):
        global_state[f"{device_name.lower()}_pressed"] = (int(val) == 1)

        if int(val) == 1:
            print(f"[{device_name}] pressed!")

        ev_type = str(settings.get("type") or "button").lower()

        event = SensorEvent(
            pi_id=str(pi_id),
            device=str(device_name).upper(),
            kind="sensor",
            type=ev_type,
            sensor_type=ev_type,
            value=int(val),
            simulated=bool(simulated),
            timestamp=time.time(),
        )
        event_queue.put(event)

    def btn_sim_loop():
        from simulation.simulators.btn import run_btn_simulator
        run_btn_simulator(10, process_btn, stop_event)

    def btn_real_loop():
        try:
            import RPi.GPIO as GPIO
        except ImportError:
            import fake_rpi
            fake_rpi.toggle_print(False)
            GPIO = fake_rpi.RPi.GPIO

        GPIO.setmode(GPIO.BCM)
        GPIO.setup(pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)

        last_state = GPIO.input(pin)
        while not stop_event.is_set():
            current_state = GPIO.input(pin)
            if current_state != last_state:
                is_pressed = 1 if current_state == GPIO.LOW else 0
                process_btn(is_pressed)
                last_state = current_state
            time.sleep(0.1)

    print(f"Starting {device_name} {'simulator' if simulated else 'real loop'} on PI{pi_id}")
    t = threading.Thread(target=(btn_sim_loop if simulated else btn_real_loop), daemon=True)
    t.start()
    threads.append(t)