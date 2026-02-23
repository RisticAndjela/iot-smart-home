import threading
import time
import random
from messaging.event_queue import event_queue
from simulation.sensors.sensor_event import SensorEvent
from simulation.state.global_state import global_state # OBAVEZNO DODAJ

def run_dht(settings, threads, stop_event):
    device_name = settings['device'] # npr. "DHT1"
    pi_id = settings['pi']
    simulated = settings['simulated']
    
    def dht_loop():
        while not stop_event.is_set():
            temp = round(random.uniform(20.0, 30.0), 1)
            hum = round(random.uniform(40.0, 60.0), 1)
            
            # --- DODAJ OVO ZA GLOBAL STATE ---
            # Koristimo lowercase da se poklopi sa kontrolerom
            d_id = device_name.lower() 
            global_state[f"{d_id}_temp"] = temp
            global_state[f"{d_id}_hum"] = hum
            # ---------------------------------

            print(f"[SIM] {device_name} Temp: {temp}°C, Hum: {hum}%")
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