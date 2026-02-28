import threading
import time

from messaging.event_queue import event_queue
from simulation.sensors.sensor_event import SensorEvent
from simulation.actuators.controller import get_cmd_queue


def run_ir(settings, threads, stop_event):
    device_name = settings["device"]
    pi_id = settings["pi"]
    simulated = settings.get("simulated", True)
    pin = settings.get("pin", 6)

    remote_map = {
        "0x300f6897": "brgb_red",
        "0xf6897": "brgb_red",
        "0x300f9867": "brgb_green",
        "0xf9867": "brgb_green",
        "0x300fb04f": "brgb_blue",
        "0xfb04f": "brgb_blue",
        "0x300f4ab5": "brgb_off",
        "0xf4ab5": "brgb_off",
    }

    def process_ir(code):
        code_n = _norm(code)
        print(f"[{device_name}] Očitan IR kod: {code_n}")

        if code_n in remote_map:
            cmd = remote_map[code_n]
            print(f"[{device_name}] Prepoznata komanda -> {cmd}")
            get_cmd_queue().put(cmd)
        else:
            print(f"[{device_name}] Nepoznat kod: {code_n}")

        ev_type = str(settings.get("type") or "ir_receiver").lower()
        event = SensorEvent(
            pi_id=str(pi_id),
            device=str(device_name).upper(),
            kind="sensor",
            type=ev_type,
            sensor_type=ev_type,
            value=str(code_n),
            simulated=bool(simulated),
            timestamp=time.time(),
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
    
def _norm(code) -> str:
    s = str(code).strip().lower()
    if not s.startswith("0x"):
        if all(c in "0123456789abcdef" for c in s):
            s = "0x" + s
    return s