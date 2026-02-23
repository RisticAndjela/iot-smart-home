import time
import random

def run_ir(settings, threads, stop_event, cmd_queue):
    device_name = settings['device'] # "IR_RECEIVER"
    
    # Mapiranje IR kodova na komande koje kontroler razume
    remote_map = {
        "0xFF30CF": "brgb_red",
        "0xFF18E7": "brgb_green",
        "0xFF7A85": "brgb_blue",
        "0xFF10EF": "brgb_off"
    }

    def ir_loop():
        while not stop_event.is_set():
            # Simuliramo da je neko pritisnuo dugme svakih 15 sekundi
            if random.random() < 0.1: 
                code = random.choice(list(remote_map.keys()))
                cmd = remote_map[code]
                print(f"[{device_name}] Received IR code {code} -> Sending {cmd}")
                cmd_queue.put(cmd)
            time.sleep(10)

    # Standardno pokretanje niti
    import threading
    t = threading.Thread(target=ir_loop, daemon=True)
    t.start()
    threads.append(t)