import threading
import time
from messaging.event_queue import event_queue
from simulation.sensors.sensor_event import SensorEvent
from simulation.actuators.controller import get_cmd_queue

def run_ir(settings, threads, stop_event):
    device_name = settings['device']
    pi_id = settings['pi']
    simulated = settings.get('simulated', True)
    pin = settings.get('pin', 17) 

    remote_map = {
        "0x300ff6897": "brgb_red",   # Dugme 1
        "0x300ff9867": "brgb_green", # Dugme 2
        "0x300ffb04f": "brgb_blue",  # Dugme 3
        "0x300ff4ab5": "brgb_off"    # Dugme 0
    }

    def process_ir(code):
        print(f"[{device_name}] Očitan IR kod: {code}")
        
        if code in remote_map:
            cmd = remote_map[code]
            print(f"[{device_name}] Prepoznata komanda -> {cmd}")
            get_cmd_queue().put(cmd)
        else:
            print(f"[{device_name}] Nepoznat kod: {code}")

        event = SensorEvent(
            pi_id=pi_id,
            device=device_name,
            sensor_type="ir_receiver",
            value=code,
            simulated=simulated,
            timestamp=time.time()
        )
        event_queue.put(event)

    if simulated:
        from simulation.simulators.ir import run_ir_simulator
        t = threading.Thread(target=run_ir_simulator, args=(process_ir, stop_event, remote_map), daemon=True)
    else:
        from simulation.sensors.ir_receiver import run_ir_real_loop
        t = threading.Thread(target=run_ir_real_loop, args=(pin, process_ir, stop_event), daemon=True)

    t.start()
    threads.append(t)