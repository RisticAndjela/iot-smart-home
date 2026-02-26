import threading
import time
import random
from messaging.event_queue import event_queue
from simulation.sensors.sensor_event import SensorEvent
from simulation.state.global_state import global_state

def run_dht(settings, threads, stop_event):
    device_name = settings['device'] 
    pi_id = settings['pi']
    simulated = settings['simulated']
    pin = settings.get('pin', 17) 
    d_id = device_name.lower()

    def process_data(temp, hum):
        global_state[f"{d_id}_temp"] = temp
        global_state[f"{d_id}_hum"] = hum

        print(f"[{device_name}] Temp: {temp}°C, Hum: {hum}%")

        # Slanje temperature u Influx/MQTT
        event_queue.put(SensorEvent(pi_id, device_name, "temperature", temp, simulated, time.time()))
        # Slanje vlažnosti u Influx/MQTT
        event_queue.put(SensorEvent(pi_id, device_name, "humidity", hum, simulated, time.time()))

    # --- SIMULACIJA ---
    def dht_sim_loop():
        while not stop_event.is_set():
            temp = round(random.uniform(20.0, 30.0), 1)
            hum = round(random.uniform(40.0, 60.0), 1)
            process_data(temp, hum)
            time.sleep(5)

    def dht_real_loop():
        from simulation.sensors.LA_DHT import DHT 
        dht_sensor = DHT(pin)
        
        while not stop_event.is_set():
            chk = dht_sensor.readDHT11()
            
            if chk == dht_sensor.DHTLIB_OK:
                process_data(dht_sensor.temperature, dht_sensor.humidity)
            else:
                print(f"[ERROR] {device_name} Error code: {chk}")
                
            time.sleep(5) 

    if simulated:
        t = threading.Thread(target=dht_sim_loop, name=f"Thread-{device_name}-Sim")
    else:
        t = threading.Thread(target=dht_real_loop, name=f"Thread-{device_name}-Real")
    
    t.start()
    threads.append(t)