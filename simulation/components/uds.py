import threading
import time

from simulation.simulators.uds import run_uds_simulator
from simulation.sensors.uds import run_uds_loop
from messaging.event_queue import event_queue
from simulation.sensors.sensor_event import SensorEvent
from simulation.state.global_state import global_state


def make_uds_callback(settings, write_callback=None):
    def uds_callback(distance):
        device_id = settings["device"].lower()
        print(f"[SIM] {settings['device']} distance: {distance}")

        global_state[f"{device_id}_prev_dist"] = global_state.get(f"{device_id}_dist", distance)
        global_state[f"{device_id}_dist"] = distance

        ev_type = str(settings.get("type") or "ultrasonic").lower()

        event = SensorEvent(
            pi_id=str(settings["pi"]),
            device=str(settings["device"]).upper(),
            kind="sensor",
            type=ev_type,
            sensor_type=ev_type,
            value=float(distance),
            simulated=bool(settings.get("simulated", True)),
            timestamp=time.time(),
        )
        event_queue.put(event)

        if write_callback:
            write_callback(event)

    return uds_callback


def run_uds(settings, threads, stop_event, write_callback=None):
    callback = make_uds_callback(settings, write_callback)

    if settings.get("simulated", True):
        print(f"Starting {settings['device']} simulator on {settings['pi']}")
        uds_thread = threading.Thread(
            target=run_uds_simulator,
            args=(2, callback, stop_event),
            daemon=True,
        )
    else:
        print(f"Starting {settings['device']} real loop on {settings['pi']}")
        uds_thread = threading.Thread(
            target=run_uds_loop,
            args=(2, callback, stop_event, settings),
            daemon=True,
        )

    uds_thread.start()
    threads.append(uds_thread)