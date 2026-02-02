import threading
import time
from simulators.ds import run_ds_simulator
from sensors.ds import run_ds_loop
from messaging.event_queue import event_queue
from simulation.sensors.sensor_event import SensorEvent

def make_ds_callback(settings):
    def ds_callback(val):
        # deleted global_state
        print(f"[SIM] {settings['device']} distance: {val}")
        event = SensorEvent(pi_id=settings["pi"],device=settings["device"],sensor_type=settings["type"],value=int(val),simulated=settings["simulated"],timestamp=time.time())
        event_queue.put(event)
    return ds_callback

def run_ds(settings, threads, stop_event):
    callback = make_ds_callback(settings)

    if settings["simulated"]:
        print(f"Starting {settings['device']} simulator on {settings['pi']}")
        ds_thread = threading.Thread(
            target=run_ds_simulator,
            args=(2, callback, stop_event),
            daemon=True
        )
    else:
        print(f"Starting {settings['device']} real loop on {settings['pi']}")
        ds_thread = threading.Thread(
            target=run_ds_loop,
            args=(0.5, callback, stop_event, settings),
            daemon=True
        )

    ds_thread.start()
    threads.append(ds_thread)
