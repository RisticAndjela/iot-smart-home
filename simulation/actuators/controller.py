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
        # --- 1. INICIJALIZACIJA STANJA ---
        # Sve varijable koje menjamo unutar petlje moraju biti u ovom rečniku
        state = {
            "timer_active": False,
            "timer_value": 0,
            "last_timer_update": 0,
            "last_light_state": False,
            "last_lcd_rotation_time": 0,
            "dht_index": 0,
            "dht_list": ["1", "2", "3"],
            "arming_start_time": 0,
            "dpir1_counted": False,
            "dpir2_counted": False
        }

        print("[CONTROLLER] Control loop started successfully with state management.")

        

        while not stop_event.is_set():
            current_time = time.time()

            # --- OBRADA KOMANDI IZ QUEUE ---
            try:
                cmd = _cmd_queue.get_nowait()
                
                # Provera za 4SD komandu (npr. "4sd_start_10")
                if cmd and cmd.startswith("4sd_start_"):
                    parts = cmd.split("_")
                    if len(parts) > 2:
                        state["timer_value"] = int(parts[2])
                        state["timer_active"] = True
                        state["last_timer_update"] = current_time
                        print(f"[CONTROLLER] Timer started at: {state['timer_value']}")
                
                # Podrška za direktan unos broja sa Dashboarda (isdigit)
                elif cmd and cmd.isdigit():
                    state["timer_value"] = int(cmd)
                    state["timer_active"] = True
                    state["last_timer_update"] = current_time
                    print(f"[CONTROLLER] Dashboard Timer started: {state['timer_value']}")

            except queue.Empty:
                cmd = None
            except Exception as e:
                print(f"[CONTROLLER] Command parse error: {e}")
                cmd = None

            # --- LOGIKA ODBROJAVANJA (4SD) ---
            if state["timer_active"]:
                if current_time - state["last_timer_update"] >= 1.0:
                    state["timer_value"] -= 1
                    state["last_timer_update"] = current_time
                    
                    # PROMENA: Treći argument (type_name) mora biti Kitchen_Timer
                    send_system_event("4SD", state["timer_value"], "Kitchen_Timer", pi_id="2")
                    
                    global_state["4sd_value"] = state["timer_value"]
                    
                    if state["timer_value"] <= 0:
                        state["timer_active"] = False
                        print("[CONTROLLER] Timer reached zero!")

            # --- OBRADA OSTALIH KOMANDI (PIN, Svetlo, RGB) ---
            if cmd:
                if cmd == "pin_correct":
                    is_active = global_state.get("system_armed") or global_state.get("alarm_active") or global_state.get("system_arming")
                    
                    if is_active:
                        global_state["alarm_active"] = False
                        global_state["system_armed"] = False
                        global_state["system_arming"] = False
                        buzzer.off()
                        send_actuator_event("DB", False, "buzzer")
                        print("[CONTROLLER] System Deactivated & Alarm OFF")
                    else:
                        global_state["system_arming"] = True
                        state["arming_start_time"] = 0 
                        print("[CONTROLLER] PIN ACCEPTED. Arming in 10s...")
                
                elif cmd == "l":
                    state["last_light_state"] = not state["last_light_state"]
                    if state["last_light_state"]:
                        light.on()
                    else:
                        light.off()
                    send_actuator_event("DL", state["last_light_state"], "light")

                elif cmd == "b":
                    buzzer.on()
                    send_actuator_event("DB", True, "buzzer")

                elif cmd.startswith("brgb_"):
                    color = cmd.split("_")[1].upper()
                    try:
                        if color == "RED": rgb.set_color(1, 0, 0)
                        elif color == "GREEN": rgb.set_color(0, 1, 0)
                        elif color == "BLUE": rgb.set_color(0, 0, 1)
                        elif color == "OFF": rgb.turn_off()
                        send_system_event("BRGB", color, "ColorChange", pi_id="3")
                    except Exception as e:
                        print(f"[BRGB ERROR] {e}")

            # --- TAČKA 1: DPIR1 i DL1 Automatika (10 sekundi) ---
            if global_state.get("motion_dpir1", False):
                global_state["last_dpir1_time"] = current_time
                if not state["last_light_state"]:
                    light.on()
                    send_actuator_event("DL", True, "light")
                    state["last_light_state"] = True

            if state["last_light_state"] and (current_time - global_state.get("last_dpir1_time", 0) > 10):
                light.off()
                send_actuator_event("DL", False, "light")
                state["last_light_state"] = False

            # --- TAČKA 2: Brojanje osoba (DPIR + DUS) ---
            # PI1
            if global_state.get("motion_dpir1", False):
                dist1 = global_state.get("dus1_dist", 0)
                prev1 = global_state.get("dus1_prev_dist", 0)
                if not state["dpir1_counted"] and dist1 > 0 and prev1 > 0:
                    if dist1 < (prev1 - 2):
                        global_state["people_count"] += 1
                        state["dpir1_counted"] = True
                        send_system_event("SYSTEM", global_state["people_count"], "PeopleCount")
                    elif dist1 > (prev1 + 2):
                        global_state["people_count"] = max(0, global_state["people_count"] - 1)
                        state["dpir1_counted"] = True
                        send_system_event("SYSTEM", global_state["people_count"], "PeopleCount")
            else:
                state["dpir1_counted"] = False

            # PI2
            if global_state.get("motion_dpir2", False):
                dist2 = global_state.get("dus2_dist", 0)
                prev2 = global_state.get("dus2_prev_dist", 0)
                if not state["dpir2_counted"] and dist2 > 0 and prev2 > 0:
                    if dist2 < (prev2 - 2):
                        global_state["people_count"] += 1
                        state["dpir2_counted"] = True
                        send_system_event("SYSTEM", global_state["people_count"], "PeopleCount")
                    elif dist2 > (prev2 + 2):
                        global_state["people_count"] = max(0, global_state["people_count"] - 1)
                        state["dpir2_counted"] = True
                        send_system_event("SYSTEM", global_state["people_count"], "PeopleCount")
            else:
                state["dpir2_counted"] = False

            # --- TAČKA 3: Zaboravljena vrata (5 sekundi) ---
            if global_state.get("door_open", False):
                if global_state.get("ds1_open_time", 0) == 0:
                    global_state["ds1_open_time"] = current_time
                elif current_time - global_state["ds1_open_time"] > 5:
                    trigger_alarm()
            else:
                global_state["ds1_open_time"] = 0

            # --- TAČKA 4: Sigurnosni Alarm (Arming) ---
            if global_state.get("system_arming", False):
                if state["arming_start_time"] == 0:
                    state["arming_start_time"] = current_time
                elif current_time - state["arming_start_time"] > 10:
                    global_state["system_armed"] = True
                    global_state["system_arming"] = False
                    state["arming_start_time"] = 0
                    print("[CONTROLLER] System ARMED")

            if global_state.get("system_armed") and global_state.get("door_open"):
                trigger_alarm()

            # --- TAČKA 5 & 6: Prazna kuća i GSG ---
            if global_state.get("people_count") == 0 and global_state.get("motion"):
                trigger_alarm()
            if global_state.get("significant_motion_gsg"):
                trigger_alarm()

            # --- FINALNA AKTIVACIJA BUZZERA ---
            if global_state.get("alarm_active"):
                buzzer.on()

            # --- LOGIKA ZA LCD ROTACIJU (Smenjivanje DHT) ---
            if current_time - state["last_lcd_rotation_time"] > 5:
                curr_dht = state["dht_list"][state["dht_index"]]
                temp = global_state.get(f"dht{curr_dht}_temp", 0)
                hum = global_state.get(f"dht{curr_dht}_hum", 0)
                
                lcd_msg = f"DHT{curr_dht}: T:{temp}C H:{hum}%"
                global_state["lcd_message"] = lcd_msg
                send_system_event("LCD", lcd_msg, "LCD", pi_id="3")
                
                state["dht_index"] = (state["dht_index"] + 1) % len(state["dht_list"])
                state["last_lcd_rotation_time"] = current_time

            time.sleep(0.2)
    def trigger_alarm():
        if not global_state["alarm_active"]:
            global_state["alarm_active"] = True
            send_actuator_event("DB", 1, "buzzer")
            print("!!! ALARM TRIGGERED !!!")

    t = threading.Thread(target=control_loop, daemon=True)
    t.start()
    return t