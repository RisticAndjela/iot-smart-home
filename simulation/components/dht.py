import threading
import time
import random
from messaging.event_queue import event_queue
from simulation.sensors.sensor_event import SensorEvent

def run_dht(settings, threads, stop_event):
    device_name = settings['device']
    pi_id = settings['pi']
    simulated = settings['simulated']
    
    def dht_loop():
        while not stop_event.is_set():
            # SIMULACIJA OCITAVANJA
            temp = round(random.uniform(20.0, 30.0), 1)
            hum = round(random.uniform(40.0, 60.0), 1)
            
            # 1. Ispis u konzolu
            print(f"[SIM] {device_name} Temp: {temp}°C, Hum: {hum}%")
            
            # 2. Slanje u Event Queue (za MQTT)
            # Saljemo dva eventa (jedan za temp, jedan za hum) ili jedan zajednicki
            # Ovde saljemo TEMPERATURU
            event_temp = SensorEvent(
                pi_id=pi_id,
                device=device_name,
                sensor_type="temperature",
                value=temp,
                simulated=simulated,
                timestamp=time.time()
            )
            event_queue.put(event_temp)

            # Ovde saljemo VLAZNOST
            event_hum = SensorEvent(
                pi_id=pi_id,
                device=device_name,
                sensor_type="humidity",
                value=hum,
                simulated=simulated,
                timestamp=time.time()
            )
            event_queue.put(event_hum)
            
            time.sleep(5) # Ocitavanje svakih 5 sekundi

    if simulated:
        t = threading.Thread(target=dht_loop)
        t.start()
        threads.append(t)