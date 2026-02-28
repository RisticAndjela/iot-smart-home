import threading
import time

from simulation.simulators.pir import run_pir_simulator
from simulation.sensors.pir import run_pir_loop
from messaging.event_queue import event_queue
from simulation.sensors.sensor_event import SensorEvent
from simulation.state.global_state import global_state


def make_pir_callback(settings, write_callback=None):
    def pir_callback(motion_detected):
        key = f"motion_{settings['device'].lower()}"
        global_state[key] = bool(motion_detected)

        print(f"[SIM] {settings['device']} motion detected: {motion_detected}")

        ev_type = str(settings.get("type") or "motion").lower()

        event = SensorEvent(
            pi_id=str(settings["pi"]),
            device=str(settings["device"]).upper(),
            kind="sensor",
            type=ev_type,
            sensor_type=ev_type,
            value=int(bool(motion_detected)),
            simulated=bool(settings.get("simulated", True)),
            timestamp=time.time(),
        )
        event_queue.put(event)

        if write_callback:
            write_callback(event)

    return pir_callback


def run_pir(settings, threads, stop_event, write_callback=None):
    callback = make_pir_callback(settings, write_callback)

    if settings.get("simulated", True):
        print(f"Starting {settings['device']} simulator on {settings['pi']}")
        pir_thread = threading.Thread(
            target=run_pir_simulator,
            args=(3, callback, stop_event),
            daemon=True,
        )
    else:
        print(f"Starting {settings['device']} real loop on {settings['pi']}")
        pir_thread = threading.Thread(
            target=run_pir_loop,
            args=(1, callback, stop_event, settings),
            daemon=True,
        )

    pir_thread.start()
    threads.append(pir_thread)