import threading
import time
import queue
from actuators.db1 import DoorBuzzer
from actuators.dl1 import DoorLight
from state.global_state import global_state

"""
    Controller thread that monitors global state and command queue to control actuators
    Buzzer: sounds when door is open, triggered once per open door event or by command, only have on method for fixed duration
    Light: turns on/off based on door open or motion detected, can be manually toggled via command for 5 seconds override 
            or by automatic conditions otherwise
    Quit command 'q' stops the controller loop
"""
_cmd_queue = queue.Queue()  # global queue from bus

def get_cmd_queue():
    return _cmd_queue

def run_controller(light:DoorLight, buzzer:DoorBuzzer, stop_event):
    def control_loop():
        buzzer_triggered = False # just once per alarm event
        light_triggered = False # if i manually turned on
        light_override_end = 0 # timestamp WHEN override ends

        while not stop_event.is_set(): # if i entered 'q' command finish
            current_time = time.time() # get current time for override checks

            # --- commands ---
            try:
                cmd = _cmd_queue.get_nowait()
            except queue.Empty:
                cmd = None

            if cmd:
                if cmd == "l" and light: # toggle light override PLUS it will stop automatics for 5 sec
                    light.on() if not light.is_on else light.off()
                    light_triggered = True
                    light_override_end = current_time + 5 # end time 5 sec from now
                elif cmd == "b" and buzzer: # trigger buzzer once
                    buzzer.on()
                elif cmd == "q": # quit application
                    stop_event.set()

            # --- light logic ---
            """
                if i trigger the ligth in console, it will be manual for 5 seconds no metter if i turned it on or off by handle numerous times
                after 5 seconds, automatic conditions will take over again
            """
            if light:
                if light_triggered and current_time >= light_override_end:
                    light_triggered = False  # manual override expired, automatic can take over

                if not light_triggered:  # automatic control
                    if global_state["door_open"] or global_state["motion"]:
                        light.on()
                    else:
                        light.off()

                        
            # --- automatic buzzer ---
            if buzzer:
                if global_state["door_open"]:
                    if not buzzer_triggered:
                        buzzer.on()
                        buzzer_triggered = True
                else:
                    buzzer_triggered = False

            time.sleep(0.2)

    t = threading.Thread(target=control_loop, daemon=True)
    t.start()
    return t
