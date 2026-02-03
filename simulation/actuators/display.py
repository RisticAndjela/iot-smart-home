import threading
import time
from datetime import datetime
from messaging.event_queue import event_queue
from simulation.sensors.sensor_event import SensorEvent

def run_4sd(settings, threads, stop_event):
    device_name = settings['device']
    pi_id = settings['pi']
    simulated = settings['simulated']
    
    # --- HARDVER DEO ---
    display = None
    # Pokusavamo da uvezemo biblioteku SAMO ako nismo u simulaciji
    # Ali stavljamo u try-except blok da Windows ne bi prijavio gresku pri pokretanju
    try:
        if not simulated:
            import tm1637
            clk = settings['pins']['clk']
            dio = settings['pins']['dio']
            display = tm1637.TM1637(clk=clk, dio=dio)
            display.brightness(1)
    except ImportError:
        print(f"[{device_name}] UPOZORENJE: tm1637 biblioteka nije pronadjena. (Ocekivano na Windows-u)")
    except Exception as e:
        print(f"[{device_name}] Greska pri inicijalizaciji: {e}")


    def display_loop():
        print(f"Starting {device_name} loop...")
        
        while not stop_event.is_set():
            if simulated:
                # SIMULACIJA: Odbrojavanje (Kitchen Timer)
                time.sleep(15) # Cekamo 15 sekundi pre aktivacije
                
                # Odbrojavanje: 5, 4, 3...
                for i in range(5, -1, -1):
                    if stop_event.is_set(): break
                    
                    display_text = f"00:0{i}"
                    print(f"[ACTUATOR] {device_name} Display: {display_text}")

                    # Slanje na MQTT
                    event = SensorEvent(
                        pi_id=pi_id,
                        device=device_name,
                        sensor_type="actuator", 
                        value=i, 
                        simulated=simulated,
                        timestamp=time.time()
                    )
                    event_queue.put(event)
                    time.sleep(1)
                
                print(f"[ACTUATOR] {device_name} FINISHED!")

            else:
                # REALNI HARDVER (samo na Raspberry Pi)
                if display:
                    now = datetime.now()
                    try:
                        # Prikazujemo sate i minute
                        display.show(now.hour * 100 + now.minute)
                    except:
                        pass
                time.sleep(1)

    t = threading.Thread(target=display_loop)
    t.start()
    threads.append(t)