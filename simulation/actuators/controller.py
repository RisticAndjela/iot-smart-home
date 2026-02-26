import threading
import time
import queue
from simulation.actuators.db1 import DoorBuzzer
from simulation.actuators.dl1 import DoorLight
from simulation.actuators.brgb import RGB_LED
from simulation.state.global_state import global_state
from messaging.event_queue import event_queue
from simulation.sensors.sensor_event import SensorEvent

_cmd_queue = queue.Queue()

def get_cmd_queue():
    return _cmd_queue

def send_actuator_event(device, state, type_name, pi_id="1"):
    try:
        event = SensorEvent(
            pi_id=pi_id,
            device=device,
            sensor_type=type_name,
            value=1 if state else 0,
            simulated=True,
            timestamp=time.time()
        )
        event_queue.put(event)
    except Exception as e:
        print(f"Error sending actuator event: {e}")

def send_system_event(device, value, type_name, pi_id="1"):
    try:
        event = SensorEvent(
            pi_id=pi_id,
            device=device,
            sensor_type=type_name,
            value=value,
            simulated=True,
            timestamp=time.time()
        )
        event_queue.put(event)
    except Exception as e:
        print(f"Error sending system event: {e}")

def run_controller(light: DoorLight, buzzer: DoorBuzzer, rgb: RGB_LED, stop_event):
    def control_loop():
        # Lokalni tajmeri i pomoćne varijable
        last_light_state = False
        arming_start_time = 0
        correct_pin = "1234" 
        dpir1_counted = False

        last_lcd_rotation_time = 0
        dht_index = 0 # 0=DHT1, 1=DHT2, 2=DHT3
        dht_list = ["1", "2", "3"]

        while not stop_event.is_set():
            current_time = time.time()

            # --- OBRADA KOMANDI (Sa tastature ili Weba) ---
            try:
                cmd = _cmd_queue.get_nowait()
            except queue.Empty:
                cmd = None

            if cmd:
                if cmd == "pin_correct":
                    is_active = global_state.get("system_armed") or global_state.get("alarm_active") or global_state.get("system_arming")
                    
                    if is_active:
                        # 1. SLUČAJ: Gasi sve (DEACTIVATION)
                        global_state["alarm_active"] = False
                        global_state["system_armed"] = False
                        global_state["system_arming"] = False
                        buzzer.off()
                        send_actuator_event("DB", 0, "buzzer")
                        print("[CONTROLLER] System Deactivated & Alarm OFF")
                    else:
                        # 2. SLUČAJ: Pali sistem (ARMING - Tačka 4.a specifikacije)
                        global_state["system_arming"] = True
                        arming_start_time = 0 # Resetujemo tajmer
                        print("[CONTROLLER] PIN ACCEPTED. You have 10 seconds to leave the house!")
                
                # logiku za ručno paljenje na 'l' i 'b'
                elif cmd == "l":
                    new_state = not last_light_state
                    if new_state: light.on()
                    else: light.off()
                    send_actuator_event("DL", new_state, "light")
                    last_light_state = new_state

                elif cmd == "b" and buzzer: 
                    buzzer.on()
                    send_actuator_event("DB", 1, "buzzer")

            # --- TAČKA 1: DPIR1 i DL1 na 10 sekundi ---
            if global_state.get("motion_dpir1", False):
                global_state["last_dpir1_time"] = current_time
                if not last_light_state:
                    light.on()
                    send_actuator_event("DL", 1, "light")
                    last_light_state = True

            if last_light_state and (current_time - global_state["last_dpir1_time"] > 10):
                light.off()
                send_actuator_event("DL", 0, "light")
                last_light_state = False

            # --- TAČKA 2: Brojanje osoba (DPIR1 + DUS1 na PI1) ---
            motion_d1 = global_state.get("motion_dpir1", False)
            if motion_d1:
                dist1 = global_state.get("dus1_dist", 0)
                prev1 = global_state.get("dus1_prev_dist", 0)
                
                # Proveravamo da distance nisu 0 (početno stanje) i dodajemo mali buffer od 2cm
                if not dpir1_counted and dist1 > 0 and prev1 > 0:
                    if dist1 < (prev1 - 2): # Ulazak
                        global_state["people_count"] += 1
                        dpir1_counted = True
                        send_system_event("SYSTEM", global_state["people_count"], "PeopleCount")
                        print(f"[LOG] PI1 Entry: People count: {global_state['people_count']}")
                    elif dist1 > (prev1 + 2): # Izlazak
                        global_state["people_count"] = max(0, global_state["people_count"] - 1)
                        dpir1_counted = True
                        send_system_event("SYSTEM", global_state["people_count"], "PeopleCount")
                        print(f"[LOG] PI1 Exit: People count: {global_state['people_count']}")
            else:
                dpir1_counted = False

            # --- TAČKA 2a: Brojanje osoba (DPIR2 + DUS2 na PI2) ---
            motion_d2 = global_state.get("motion_dpir2", False)
            if motion_d2:
                dist2 = global_state.get("dus2_dist", 0)
                prev2 = global_state.get("dus2_prev_dist", 0)
                
                if not dpir2_counted and dist2 > 0 and prev2 > 0:
                    if dist2 < (prev2 - 2): # Ulazak
                        global_state["people_count"] += 1
                        dpir2_counted = True
                        send_system_event("SYSTEM", global_state["people_count"], "PeopleCount")
                        print(f"[LOG] PI2 Entry: People count: {global_state['people_count']}")
                    elif dist2 > (prev2 + 2): # Izlazak
                        global_state["people_count"] = max(0, global_state["people_count"] - 1)
                        dpir2_counted = True
                        send_system_event("SYSTEM", global_state["people_count"], "PeopleCount")
                        print(f"[LOG] PI2 Exit: People count: {global_state['people_count']}")
            else:
                dpir2_counted = False

            # --- TAČKA 3: Zaboravljena vrata (5 sekundi) ---
            if global_state["door_open"]:
                if global_state["ds1_open_time"] == 0:
                    global_state["ds1_open_time"] = current_time
                elif current_time - global_state["ds1_open_time"] > 5:
                    trigger_alarm()
            else:
                global_state["ds1_open_time"] = 0

            # --- TAČKA 4: Sigurnosni Alarm (DMS PIN) ---
            if global_state["system_arming"]:
                if arming_start_time == 0:
                    arming_start_time = current_time
                elif current_time - arming_start_time > 10:
                    global_state["system_armed"] = True
                    global_state["system_arming"] = False
                    arming_start_time = 0
                    print("[CONTROLLER] System ARMED")

            # Ako je sistem aktivan i vrata se otvore (4.b)
            if global_state["system_armed"] and global_state["door_open"]:
                trigger_alarm()

            # --- TAČKA 5: Prazna kuća (People Count == 0) ---
            if global_state["people_count"] == 0 and global_state["motion"]:
                trigger_alarm()

            # --- TAČKA 6: GSG Pomeraj ikone ---
            if global_state.get("significant_motion_gsg", False):
                trigger_alarm()

            # --- FINALNA AKTIVACIJA BUZZERA ---
            if global_state["alarm_active"]:
                buzzer.on()
                # Ovdje bi mogla dodati slanje eventa u bazu samo jednom pri promjeni
            
            # --- LOGIKA ZA LCD ROTACIJU (Tačka: DHT 1-3 Smenjivanje) ---
            if current_time - last_lcd_rotation_time > 5: # Menjaj na svakih 5 sekundi
                current_dht = dht_list[dht_index]
                
                temp = global_state.get(f"dht{current_dht}_temp", 0)
                hum = global_state.get(f"dht{current_dht}_hum", 0)
                
                # Formatiranje poruke za LCD (16 karaktera po redu max)
                lcd_message = f"DHT{current_dht}: T:{temp}C H:{hum}%"
                
                global_state["lcd_message"] = lcd_message
                
                # Slanje na LCD (PI3)
                send_system_event("LCD", lcd_message, "LCD", pi_id="3")
                print(f"[LCD ROTATION] Displaying: {lcd_message}")
                
                # Pomeri indeks na sledeći DHT
                dht_index = (dht_index + 1) % len(dht_list)
                last_lcd_rotation_time = current_time

            # controller.py - unutar while petlje
            if cmd and cmd.startswith("brgb_"):
                color = cmd.split("_")[1].upper()
                
                try:
                    # Koristi 'rgb' jer je tako nazvan argument u run_controller
                    if color == "RED": rgb.set_color(1, 0, 0)
                    elif color == "GREEN": rgb.set_color(0, 1, 0)
                    elif color == "BLUE": rgb.set_color(0, 0, 1)
                    elif color == "OFF": rgb.turn_off()
                    
                    # OVO JE JEDINO MESTO GDE SE PIŠE U BAZU
                    send_system_event("BRGB", color, "ColorChange", pi_id="3")
                    print(f"[CONTROLLER] Hardver osvežen i baza upisana: {color}")
                except Exception as e:
                    print(f"[ERROR] Problem u kontroleru sa BRGB: {e}")


            time.sleep(0.2)

    def trigger_alarm():
        if not global_state["alarm_active"]:
            global_state["alarm_active"] = True
            send_actuator_event("DB", 1, "buzzer")
            print("!!! ALARM TRIGGERED !!!")

    t = threading.Thread(target=control_loop, daemon=True)
    t.start()
    return t