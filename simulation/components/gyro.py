import threading
import time
import random
from messaging.event_queue import event_queue
from simulation.sensors.sensor_event import SensorEvent
from simulation.state.global_state import global_state

def run_gyro(settings, threads, stop_event):
    device_name = settings['device']
    pi_id = settings['pi']
    simulated = settings['simulated']

    def process_gyro(accel_z, is_shaking):
        global_state["significant_motion_gsg"] = is_shaking
        
        if is_shaking:
            print(f"[GSG] 🚨 UPOZORENJE! Detektovano pomeranje: Accel_Z={accel_z}")
        else:
            print(f"[SIM] {device_name} Accel Z: {accel_z}")

        event = SensorEvent(
            pi_id=pi_id,
            device=device_name,
            sensor_type="gyro",
            value=accel_z,
            simulated=simulated,
            timestamp=time.time()
        )
        event_queue.put(event)

    def gyro_sim_loop():
        while not stop_event.is_set():
            is_shaking = random.random() > 0.9 
            
            if is_shaking:
                accel_z = round(random.uniform(15.0, 20.0), 2)
            else:
                accel_z = round(random.uniform(9.5, 10.0), 2)
            
            process_gyro(accel_z, is_shaking)
            time.sleep(3)

    def gyro_real_loop():
        from simulation.sensors.gyro import run_gyro_real_loop 
        run_gyro_real_loop(process_gyro, stop_event, 3)

    if simulated:
        t = threading.Thread(target=gyro_sim_loop, daemon=True)
    else:
        t = threading.Thread(target=gyro_real_loop, daemon=True)
    
    t.start()
    threads.append(t)