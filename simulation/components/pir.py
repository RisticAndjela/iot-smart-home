import threading
import time
from simulators.pir import run_pir_simulator
from sensors.pir import run_pir_loop
from messaging.event_queue import event_queue
from simulation.sensors.sensor_event import SensorEvent

def make_pir_callback(settings):
    def pir_callback(motion_detected):
        # deleted global_state 
        print(f"[SIM] {settings['device']} motion detected: {motion_detected}")
        event = SensorEvent(pi_id=settings["pi"],device=settings["device"],sensor_type=settings["type"],value=int(motion_detected),simulated=settings["simulated"],timestamp=time.time())
        event_queue.put(event)
    return pir_callback


def run_pir(settings, threads, stop_event):
    callback = make_pir_callback(settings)

    if settings["simulated"]:
        print(f"Starting {settings['device']} simulator on {settings['pi']}")
        pir_thread = threading.Thread(
            target=run_pir_simulator,
            args=(3, callback, stop_event),
            daemon=True
        )
    else:
        print(f"Starting {settings['device']} real loop on {settings['pi']}")
        pir_thread = threading.Thread(
            target=run_pir_loop,
            args=(1, callback, stop_event, settings),
            daemon=True
        )

    pir_thread.start()
    threads.append(pir_thread)
