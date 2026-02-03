import threading
import time
import random
from messaging.event_queue import event_queue
from simulation.sensors.sensor_event import SensorEvent

def run_gyro(settings, threads, stop_event):
    device_name = settings['device']
    pi_id = settings['pi']
    simulated = settings['simulated']

    def gyro_loop():
        while not stop_event.is_set():
            # SIMULACIJA PODATAKA
            # MPU6050 daje 6 osa (3 accel, 3 gyro)
            # Za jednostavnost slanja, ovde cemo poslati samo po jednu vrednost kao primer,
            # ili mozes spakovati sve u string/json ako tvoj SensorEvent podržava string za value.
            
            # Simuliramo samo jednu osu radi testa
            accel_z = round(random.uniform(9.0, 10.0), 2)
            
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
            
            time.sleep(3)

    if simulated:
        t = threading.Thread(target=gyro_loop)
        t.start()
        threads.append(t)