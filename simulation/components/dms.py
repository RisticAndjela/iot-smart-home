import threading
import time

from simulation.sensors.dms import run_dms_loop
from simulation.simulators.dms import run_dms_simulator
from simulation.actuators.controller import get_cmd_queue
from messaging.event_queue import event_queue
from simulation.sensors.sensor_event import SensorEvent
from simulation.state.global_state import global_state


def make_dms_callback(settings, write_callback=None):
    def dms_callback(key):
        if not key:
            return

        if "pin_buffer" not in global_state:
            global_state["pin_buffer"] = ""

        global_state["pin_buffer"] += str(key)
        print(f"[DMS] Uneta cifra: {key} | Trenutni niz: {global_state['pin_buffer']}")

        ev_type = str(settings.get("type") or "membrane").lower()

        event = SensorEvent(
            pi_id=str(settings["pi"]),
            device=str(settings["device"]).upper(),
            kind="sensor",
            type=ev_type,
            sensor_type=ev_type,
            value=str(key),
            simulated=bool(settings.get("simulated", True)),
            timestamp=time.time(),
        )
        event_queue.put(event)

        # PIN check on 4 digits
        if len(global_state["pin_buffer"]) == 4:
            if global_state["pin_buffer"] == "1234":
                # Spec:
                # - if system inactive -> activate (arming then armed after 10s)
                # - if system active or alarm active -> disarm & stop alarm
                system_is_active = (
                    bool(global_state.get("system_armed"))
                    or bool(global_state.get("system_arming"))
                    or bool(global_state.get("alarm_active"))
                )

                if system_is_active:
                    print("[DMS] PIN ISPRAVAN - DISARM (pin_correct)")
                    get_cmd_queue().put("pin_correct")
                else:
                    print("[DMS] PIN ISPRAVAN - ARM")
                    get_cmd_queue().put("arm")
            else:
                print("[DMS] POGREŠAN PIN!")

            global_state["pin_buffer"] = ""

    return dms_callback


def run_dms(settings, threads, stop_event, write_callback=None):
    callback = make_dms_callback(settings, write_callback)

    if settings.get("simulated", True):
        print(f"Starting {settings['device']} simulator on {settings['pi']}")
        dms_thread = threading.Thread(
            target=run_dms_simulator,
            args=(5, callback, stop_event),
            daemon=True,
        )
    else:
        print(f"Starting {settings['device']} real loop on {settings['pi']}")
        dms_thread = threading.Thread(
            target=run_dms_loop,
            args=(0.2, callback, stop_event, settings),
            daemon=True,
        )

    dms_thread.start()
    threads.append(dms_thread)