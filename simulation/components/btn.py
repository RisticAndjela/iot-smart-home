import threading
from simulation.simulators.btn import run_btn_simulator
from messaging.event_queue import event_queue
from simulation.sensors.sensor_event import SensorEvent
import time

def run_btn(settings, threads, stop_event):
    def callback(val):

        if val == 1:
            print(f"[SIM] {settings['device']} pressed!")
        
        event = SensorEvent(
            pi_id=settings["pi"],
            device=settings["device"],
            sensor_type=settings["type"],
            value=val,
            simulated=settings["simulated"],
            timestamp=time.time()
        )
        event_queue.put(event)

    if settings.get("simulated", True):
        t = threading.Thread(target=run_btn_simulator, args=(10, callback, stop_event), daemon=True)
        t.start()
        threads.append(t)