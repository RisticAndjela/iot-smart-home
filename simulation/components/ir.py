import threading
import time
from messaging.event_queue import event_queue
from simulation.sensors.sensor_event import SensorEvent
from simulation.actuators.controller import get_cmd_queue

def run_ir(settings, threads, stop_event):
    device_name = settings['device']
    pi_id = settings['pi']
    simulated = settings.get('simulated', True)
    pin = settings.get('pin', 17) # Povlači pin iz JSON-a (npr. 17)

    # Mapa dugmića - OSIGURAJ DA SU MALA SLOVA (0x... umesto 0X...)
    remote_map = {
        "0x300ff6897": "brgb_red",   # Dugme 1
        "0x300ff9867": "brgb_green", # Dugme 2
        "0x300ffb04f": "brgb_blue",  # Dugme 3
        "0x300ff4ab5": "brgb_off"    # Dugme 0
    }

    def process_ir(code):
        # Normalizacija koda (mala slova) radi poređenja
        code = code.lower()
        print(f"[{device_name}] Primljen kod: {code}")
        
        # 1. Provera da li je kod u mapi i slanje komande sijalici
        if code in remote_map:
            cmd = remote_map[code]
            print(f"[{device_name}] KOMANDA PRONAĐENA: {cmd}")
            # Šaljemo komandu u red čekanja koji sijalica (BRGB) sluša
            get_cmd_queue().put(cmd)
        else:
            print(f"[{device_name}] Nepoznat kod: {code}. Proveri remote_map.")

        # 2. Slanje u Event Queue (za InfluxDB/Prikaz)
        event = SensorEvent(
            pi_id=pi_id,
            device=device_name,
            sensor_type="ir_receiver",
            value=code, # Ovo ide u bazu kao string
            simulated=simulated,
            timestamp=time.time()
        )
        event_queue.put(event)

    # Pokretanje niti
    if simulated:
        from simulation.simulators.ir import run_ir_simulator
        # Simulatoru prosleđujemo mapu da bi znao koje kodove da "izmišlja"
        t = threading.Thread(target=run_ir_simulator, args=(process_ir, stop_event, remote_map), daemon=True)
    else:
        from simulation.sensors.ir_receiver import run_ir_real_loop
        t = threading.Thread(target=run_ir_real_loop, args=(pin, process_ir, stop_event), daemon=True)

    t.start()
    threads.append(t)
    print(f"[{device_name}] IR Receiver nit pokrenuta (Simulated: {simulated}, Pin: {pin})")