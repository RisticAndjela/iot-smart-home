# import threading
# import time
# from simulation.simulators.ds import run_ds_simulator
# from simulation.sensors.ds import run_ds_loop
# from messaging.event_queue import event_queue
# from simulation.sensors.sensor_event import SensorEvent

# def make_ds_callback(settings, write_callback=None):
#     def ds_callback(val):
#         # deleted global_state
#         print(f"[SIM] {settings['device']} state: {val}")
#         event = SensorEvent(pi_id=settings["pi"],device=settings["device"],sensor_type=settings["type"],value=int(val),simulated=settings["simulated"],timestamp=time.time())
#         event_queue.put(event)
#         if write_callback:
#             write_callback(event)
#     return ds_callback

# def run_ds(settings, threads, stop_event, write_callback=None):
#     callback = make_ds_callback(settings, write_callback)

#     if settings["simulated"]:
#         print(f"Starting {settings['device']} simulator on {settings['pi']}")
#         ds_thread = threading.Thread(
#             target=run_ds_simulator,
#             args=(2, callback, stop_event),
#             daemon=True
#         )
#     else:
#         print(f"Starting {settings['device']} real loop on {settings['pi']}")
#         ds_thread = threading.Thread(
#             target=run_ds_loop,
#             args=(0.5, callback, stop_event, settings),
#             daemon=True
#         )

#     ds_thread.start()
#     threads.append(ds_thread)


import threading
import time
from simulation.simulators.ds import run_ds_simulator
from simulation.sensors.ds import run_ds_loop
from messaging.event_queue import event_queue
from simulation.sensors.sensor_event import SensorEvent
from simulation.state.global_state import global_state

def make_ds_callback(settings, write_callback=None):
    def ds_callback(val):
        is_open = bool(val)
        global_state["door_open"] = is_open
        
        device_id = settings['device'].lower()
        global_state[f"{device_id}_open"] = is_open

        state_str = "OPEN" if is_open else "CLOSED"
        print(f"[{settings['device']}] state: {state_str}")
        
        event = SensorEvent(
            pi_id=settings["pi"],
            device=settings["device"],
            sensor_type=settings["type"],
            value=int(val),
            simulated=settings["simulated"],
            timestamp=time.time()
        )
        event_queue.put(event)
        
        if write_callback:
            write_callback(event)
            
    return ds_callback

def run_ds(settings, threads, stop_event, write_callback=None):
    callback = make_ds_callback(settings, write_callback)

    if settings["simulated"]:
        print(f"Starting {settings['device']} simulator on {settings['pi']}")
        ds_thread = threading.Thread(
            target=run_ds_simulator,
            args=(2, callback, stop_event),
            daemon=True
        )
    else:
        print(f"Starting {settings['device']} real loop on {settings['pi']}")
        ds_thread = threading.Thread(
            target=run_ds_loop,
            args=(0.5, callback, stop_event, settings),
            daemon=True
        )

    ds_thread.start()
    threads.append(ds_thread)