import time
import random

def run_ir_simulator(callback, stop_event, remote_map):
    keys = list(remote_map.keys())
    keys.append("0xUNKNOWN_CODE") 
    
    print("Started IR simulator...")
        
    while not stop_event.is_set():
        if random.random() < 0.2:
            code = random.choice(keys)
            callback(code)
        time.sleep(2)              
        time.sleep(2)              