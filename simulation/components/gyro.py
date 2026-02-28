import threading
import time
import random

from messaging.event_queue import event_queue
from simulation.sensors.sensor_event import SensorEvent
from simulation.state.global_state import global_state


def run_gyro(settings, threads, stop_event):
    device_name = settings["device"]
    pi_id = settings["pi"]
    simulated = settings.get("simulated", True)

    def process_gyro(accel_z, is_shaking):
        global_state["significant_motion_gsg"] = bool(is_shaking)

        if is_shaking:
            print(f"[GSG] WARNING! Motion detected: Accel_Z={accel_z}")
        else:
            print(f"[SIM] {device_name} Accel Z: {accel_z}")

        ev_type = str(settings.get("type") or "gyro").lower()

        event = SensorEvent(
            pi_id=str(pi_id),
            device=str(device_name).upper(),
            kind="sensor",
            type=ev_type,
            sensor_type=ev_type,
            value=float(accel_z),
            simulated=bool(simulated),
            timestamp=time.time(),
        )
        event_queue.put(event)

    def gyro_sim_loop():
        while not stop_event.is_set():
            is_shaking = random.random() > 0.9
            accel_z = round(random.uniform(15.0, 20.0), 2) if is_shaking else round(random.uniform(9.5, 10.0), 2)
            process_gyro(accel_z, is_shaking)
            time.sleep(3)

    def gyro_real_loop():
        from simulation.sensors.gyro import run_gyro_real_loop
        run_gyro_real_loop(process_gyro, stop_event, 3)

    t = threading.Thread(target=(gyro_sim_loop if simulated else gyro_real_loop), daemon=True)
    t.start()
    threads.append(t)