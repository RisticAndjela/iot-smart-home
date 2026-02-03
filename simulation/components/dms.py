import threading
import time
from simulation.sensors.dms import run_dms_loop
from simulation.simulators.dms import run_dms_simulator
from messaging.event_queue import event_queue
from simulation.sensors.sensor_event import SensorEvent
from simulation.state.global_state import global_state


def make_dms_callback(settings, write_callback=None):
    def dms_callback(val):
        global_state["dms_pressed"] = bool(val) # important for acctuators
        print(f"[SIM] {settings['device']} value: {val}")
        event = SensorEvent(pi_id=settings["pi"],device=settings["device"],sensor_type=settings["type"],  value=val,simulated=settings["simulated"],timestamp=time.time())
        event_queue.put(event)
        if write_callback:
                write_callback(event) 
    return dms_callback


def run_dms(settings, threads, stop_event, write_callback=None):
    callback = make_dms_callback(settings, write_callback)

    if settings.get("simulated", True):
        print(f"Starting {settings['device']} simulator on {settings['pi']}")
        dms_thread = threading.Thread(
            target=run_dms_simulator,
            args=(5, callback, stop_event),
            daemon=True
        )
    else:
        print(f"Starting {settings['device']} real loop on {settings['pi']}")
        dms_thread = threading.Thread(
            target=run_dms_loop,
            args=(0.2, callback, stop_event, settings),
            daemon=True
        )

    dms_thread.start()
    threads.append(dms_thread)
