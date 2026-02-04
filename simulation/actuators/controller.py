import threading
import time
import queue
from simulation.actuators.db1 import DoorBuzzer
from simulation.actuators.dl1 import DoorLight
from simulation.state.global_state import global_state
from messaging.event_queue import event_queue
from simulation.sensors.sensor_event import SensorEvent

"""
    Controller thread that monitors global state and command queue to control actuators
"""
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
        # print(f"DEBUG: Sent {device} = {state}") 
    except Exception as e:
        print(f"Error sending actuator event: {e}")

def run_controller(light:DoorLight, buzzer:DoorBuzzer, stop_event):
    def control_loop():
        buzzer_triggered = False 
        light_triggered = False 
        light_override_end = 0 
        
        last_light_state = False 

        while not stop_event.is_set():
            current_time = time.time()

            # --- COMMANDS ---
            try:
                cmd = _cmd_queue.get_nowait()
            except queue.Empty:
                cmd = None

            if cmd:
                if cmd == "l" and light: # Light toggle
                    new_state = not last_light_state
                    if new_state:
                        light.on()
                    else:
                        light.off()
                    send_actuator_event("DL", new_state, "light")
                    last_light_state = new_state
                    light_triggered = True
                    light_override_end = current_time + 5
                
                elif cmd == "b" and buzzer: # Buzzer trigger
                    buzzer.on()
                    send_actuator_event("DB", 1, "buzzer")
                    
                    time.sleep(3) 
                    send_actuator_event("DB", 0, "buzzer")
                
                elif cmd == "q": 
                    stop_event.set()

            # --- LIGHT LOGIC (Automatic) ---
            if light:
                if light_triggered and current_time >= light_override_end:
                    light_triggered = False 

                if not light_triggered:
                    should_be_on = global_state["door_open"] or global_state["motion"]
                    if should_be_on != last_light_state:
                        if should_be_on:
                            light.on()
                        else:
                            light.off()
                        send_actuator_event("DL", should_be_on, "light")
                        last_light_state = should_be_on
                        
            # --- BUZZER LOGIC (Automatic) ---
            if buzzer:
                if global_state["door_open"]:
                    if not buzzer_triggered:
                        buzzer.on()
                        send_actuator_event("DB", 1, "buzzer")
                        buzzer_triggered = True
                else:
                    if buzzer_triggered:
                        # when the door close, sending OFF
                        send_actuator_event("DB", 0, "buzzer")
                        buzzer_triggered = False

            time.sleep(0.2)

    t = threading.Thread(target=control_loop, daemon=True)
    t.start()
    return t