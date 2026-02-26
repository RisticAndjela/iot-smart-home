import queue
import threading
import time
from typing import Optional

from messaging.event_queue import event_queue
from simulation.actuators.brgb import RGB_LED
from simulation.actuators.db1 import DoorBuzzer
from simulation.actuators.dl1 import DoorLight
from simulation.sensors.sensor_event import SensorEvent
from simulation.state.global_state import global_state

_cmd_queue: "queue.Queue[str]" = queue.Queue()


def get_cmd_queue():
    return _cmd_queue

def _make_event(*, pi_id, device, type_name, value, simulated=True, timestamp=None, kind=None):
    if timestamp is None:
        timestamp = time.time()

    return SensorEvent(
        pi_id=str(pi_id),
        device=str(device).upper(),
        value=value,
        simulated=bool(simulated),
        timestamp=float(timestamp),
        kind=str(kind or "system"),
        type=str(type_name or "unknown").lower(),
        sensor_type=str(type_name or "unknown").lower(),  # keep legacy alias populated for now
    )


def send_actuator_event(*, device, state, type_name, pi_id, simulated: bool):
    """
    For simple on/off actuators (DL, DB): value is 1/0.
    """
    value = 1 if state else 0
    event_queue.put(
        _make_event(
            pi_id=pi_id,
            device=device,
            type_name=type_name,
            kind="actuator",
            value=value,
            simulated=simulated,
        )
    )


def send_actuator_message(*, device, value, type_name, pi_id, simulated: bool):
    """
    For actuators whose state is textual (LCD message, RGB color).
    """
    event_queue.put(
        _make_event(
            pi_id=pi_id,
            device=device,
            type_name=type_name,
            kind="actuator",
            value=value,
            simulated=simulated,
        )
    )


def send_system_event(*, device, value, type_name, pi_id, simulated: bool = True):
    """
    Logical/system events: people count, alarm transitions, arming, etc.
    """
    event_queue.put(
        _make_event(
            pi_id=pi_id,
            device=device,
            type_name=type_name,
            kind="system",
            value=value,
            simulated=simulated,
        )
    )

def run_controller(light: Optional[DoorLight], buzzer: Optional[DoorBuzzer], rgb: Optional[RGB_LED], stop_event):
    """
    Single owner of actuator control.

    Commands accepted (case-insensitive):
      - help
      - status
      - l | dl_toggle
      - dl_on | dl_off | dl_beep
      - b | db_on
      - boff | db_off
      - beep | b1.5 | db_beep
      - arm | disarm
      - alarm_on | alarm_off
      - people_set <n> | people_reset
      - lcd <text>
      - brgb_red|green|blue|white|off
      - brgb_cycle (toggles cycle on/off)
    """
    # Local derived "simulated" flags for clean tagging in events
    light_sim = bool(getattr(light, "simulated", True)) if light else True
    buzzer_sim = bool(getattr(buzzer, "simulated", True)) if buzzer else True
    rgb_sim = bool(getattr(rgb, "simulated", True)) if rgb else True

    # Timers for simulated auto-off (1.5s)
    buzzer_timer: Optional[threading.Timer] = None
    light_timer: Optional[threading.Timer] = None

    # RGB cycle
    rgb_cycle_enabled = False
    rgb_cycle_last = 0.0
    rgb_cycle_colors = ["RED", "GREEN", "BLUE", "WHITE", "OFF"]
    rgb_cycle_idx = 0

    def _cancel_timer(timer: Optional[threading.Timer]) -> Optional[threading.Timer]:
        if timer:
            try:
                timer.cancel()
            except Exception:
                pass
        return None

    def _buzzer_off_emit():
        nonlocal buzzer_timer
        if not buzzer:
            return
        buzzer_timer = None
        try:
            buzzer.off()
        finally:
            send_actuator_event(device="DB", state=False, type_name="buzzer", pi_id="1", simulated=buzzer_sim)

    def _buzzer_on_emit(auto_off_seconds: Optional[float] = None):
        nonlocal buzzer_timer
        if not buzzer:
            print("[CONTROLLER] Buzzer not initialized.")
            return

        buzzer.on()
        send_actuator_event(device="DB", state=True, type_name="buzzer", pi_id="1", simulated=buzzer_sim)

        if auto_off_seconds is not None:
            buzzer_timer = _cancel_timer(buzzer_timer)
            buzzer_timer = threading.Timer(auto_off_seconds, _buzzer_off_emit)
            buzzer_timer.daemon = True
            buzzer_timer.start()

    def _light_off_emit():
        nonlocal light_timer, last_light_state
        if not light:
            return
        light_timer = None
        try:
            light.off()
            last_light_state = False
        finally:
            send_actuator_event(device="DL", state=False, type_name="light", pi_id="1", simulated=light_sim)

    def _light_on_emit(auto_off_seconds: Optional[float] = None):
        nonlocal light_timer, last_light_state
        if not light:
            print("[CONTROLLER] DoorLight not initialized.")
            return

        light.on()
        last_light_state = True
        send_actuator_event(device="DL", state=True, type_name="light", pi_id="1", simulated=light_sim)

        if auto_off_seconds is not None:
            light_timer = _cancel_timer(light_timer)
            light_timer = threading.Timer(auto_off_seconds, _light_off_emit)
            light_timer.daemon = True
            light_timer.start()

    def _toggle_light():
        if not light:
            print("[CONTROLLER] DoorLight not initialized.")
            return
        if last_light_state:
            _light_off_emit()
        else:
            _light_on_emit()

    def _set_rgb(color: str):
        if not rgb:
            print("[CONTROLLER] RGB not initialized.")
            return
        c = (color or "").strip().upper()
        try:
            rgb.set_color_name(c)
            send_actuator_message(device="BRGB", value=c, type_name="rgb", pi_id="3", simulated=rgb_sim)
            print(f"[CONTROLLER] BRGB -> {c}")
        except Exception as e:
            print(f"[ERROR] BRGB controller error: {e}")

    def _print_help():
        print(
            "Commands:\n"
            "  help\n"
            "  status\n"
            "  l | dl_toggle\n"
            "  dl_on | dl_off | dl_beep\n"
            "  b | db_on\n"
            "  boff | db_off\n"
            "  beep | b1.5 | db_beep\n"
            "  arm | disarm\n"
            "  alarm_on | alarm_off\n"
            "  people_set <n> | people_reset\n"
            "  lcd <text>\n"
            "  brgb_red|green|blue|white|off\n"
            "  brgb_cycle (toggle)\n"
        )

    def _print_status():
        snapshot = {
            "armed": global_state.get("system_armed"),
            "arming": global_state.get("system_arming"),
            "alarm": global_state.get("alarm_active"),
            "people_count": global_state.get("people_count"),
            "door_open": global_state.get("door_open"),
            "motion_dpir1": global_state.get("motion_dpir1"),
            "motion_dpir2": global_state.get("motion_dpir2"),
            "motion_dpir3": global_state.get("motion_dpir3"),
            "dus1_dist": global_state.get("dus1_dist"),
            "dus2_dist": global_state.get("dus2_dist"),
            "gsg": global_state.get("significant_motion_gsg"),
            "dht1": {"t": global_state.get("dht1_temp"), "h": global_state.get("dht1_hum")},
            "dht2": {"t": global_state.get("dht2_temp"), "h": global_state.get("dht2_hum")},
            "dht3": {"t": global_state.get("dht3_temp"), "h": global_state.get("dht3_hum")},
            "lcd": global_state.get("lcd_message"),
        }
        print("[STATUS]", snapshot)

    def _trigger_alarm():
        # edge-triggered
        if not global_state.get("alarm_active"):
            global_state["alarm_active"] = True
            send_system_event(device="SYSTEM", value=True, type_name="alarm_on", pi_id="1")
            print("!!! ALARM TRIGGERED !!!")

        # Buzzer behavior: ON continuously when alarm is active (real or sim)
        if buzzer:
            buzzer_timer_local = buzzer_timer  # read current
            if buzzer_timer_local:
                # cancel any pending auto-off; alarm has priority
                pass
            _buzzer_on_emit(auto_off_seconds=None)

    def _alarm_off():
        global_state["alarm_active"] = False
        send_system_event(device="SYSTEM", value=False, type_name="alarm_off", pi_id="1")
        if buzzer:
            _buzzer_off_emit()
        print("[CONTROLLER] Alarm OFF")

    def _arm():
        if global_state.get("alarm_active") or global_state.get("system_armed") or global_state.get("system_arming"):
            print("[CONTROLLER] System already active (armed/arming/alarm).")
            return
        global_state["system_arming"] = True
        nonlocal_vars["arming_start_time"] = 0.0
        send_system_event(device="SYSTEM", value=True, type_name="arming_started", pi_id="1")
        print("[CONTROLLER] ARM requested. You have 10 seconds to leave the house!")

    def _disarm():
        global_state["alarm_active"] = False
        global_state["system_armed"] = False
        global_state["system_arming"] = False
        nonlocal_vars["arming_start_time"] = 0.0
        send_system_event(device="SYSTEM", value=True, type_name="disarmed", pi_id="1")

        if buzzer:
            _buzzer_off_emit()
        print("[CONTROLLER] System DISARMED")

    # Small trick to allow inner funcs to update some scalars cleanly
    nonlocal_vars = {"arming_start_time": 0.0}

    # Controller state
    last_light_state = False

    # People counting flags
    dpir1_counted = False
    dpir2_counted = False

    # LCD rotation
    last_lcd_rotation_time = 0.0
    dht_index = 0
    dht_list = ["1", "2", "3"]

    def _handle_command(raw: str):
        nonlocal rgb_cycle_enabled, rgb_cycle_idx, rgb_cycle_last, last_light_state
        nonlocal buzzer_timer, light_timer

        raw = (raw or "").strip()
        if not raw:
            return

        cmd = raw.lower()

        # Multi-word commands
        if cmd.startswith("people_set "):
            try:
                n = int(cmd.split(" ", 1)[1].strip())
                global_state["people_count"] = max(0, n)
                send_system_event(device="SYSTEM", value=global_state["people_count"], type_name="PeopleCount", pi_id="1")
                print(f"[CONTROLLER] people_count set to {global_state['people_count']}")
            except Exception:
                print("[CONTROLLER] Usage: people_set <number>")
            return

        if cmd.startswith("lcd "):
            text = raw.split(" ", 1)[1]
            global_state["lcd_message"] = text
            send_actuator_message(device="LCD", value=text, type_name="display", pi_id="3", simulated=True)
            print(f"[CONTROLLER] LCD message set: {text}")
            return

        # Help / debug
        if cmd == "help":
            _print_help()
            return
        if cmd == "status":
            _print_status()
            return

        # System commands
        if cmd == "arm":
            _arm()
            return
        if cmd == "disarm":
            _disarm()
            return
        if cmd == "alarm_on":
            _trigger_alarm()
            return
        if cmd == "alarm_off":
            _alarm_off()
            return
        if cmd in ("people_reset", "people0"):
            global_state["people_count"] = 0
            send_system_event(device="SYSTEM", value=0, type_name="PeopleCount", pi_id="1")
            print("[CONTROLLER] people_count reset to 0")
            return

        # Light commands
        if cmd in ("l", "dl_toggle"):
            _toggle_light()
            return
        if cmd == "dl_on":
            _light_on_emit(auto_off_seconds=(1.5 if light_sim else None))
            return
        if cmd == "dl_off":
            light_timer = _cancel_timer(light_timer)
            _light_off_emit()
            return
        if cmd in ("dl_beep", "dl1.5"):
            _light_on_emit(auto_off_seconds=1.5)
            return

        # Buzzer commands
        if cmd in ("b", "db_on"):
            # Auto-off only for simulation
            _buzzer_on_emit(auto_off_seconds=(1.5 if buzzer_sim else None))
            return
        if cmd in ("boff", "db_off"):
            buzzer_timer = _cancel_timer(buzzer_timer)
            _buzzer_off_emit()
            return
        if cmd in ("beep", "b1.5", "db_beep"):
            _buzzer_on_emit(auto_off_seconds=1.5)
            return

        # RGB commands
        if cmd == "brgb_cycle":
            rgb_cycle_enabled = not rgb_cycle_enabled
            print(f"[CONTROLLER] RGB cycle {'ENABLED' if rgb_cycle_enabled else 'DISABLED'}")
            return

        if cmd.startswith("brgb_"):
            color = cmd.split("_", 1)[1]
            _set_rgb(color)
            return

        print(f"[CONTROLLER] Unknown command: {raw} (try 'help')")

    def control_loop():
        nonlocal last_light_state, dpir1_counted, dpir2_counted
        nonlocal last_lcd_rotation_time, dht_index
        nonlocal rgb_cycle_enabled, rgb_cycle_last, rgb_cycle_idx

        while not stop_event.is_set():
            now = time.time()

            # --- COMMANDS ---
            while True:
                try:
                    raw_cmd = _cmd_queue.get_nowait()
                except queue.Empty:
                    break
                try:
                    # Special existing command from keypad logic
                    if raw_cmd == "pin_correct":
                        is_active = (
                            global_state.get("system_armed")
                            or global_state.get("alarm_active")
                            or global_state.get("system_arming")
                        )
                        if is_active:
                            _disarm()
                        else:
                            _arm()
                    else:
                        _handle_command(raw_cmd)
                except Exception as e:
                    print(f"[CONTROLLER] Error handling command '{raw_cmd}': {e}")

            # --- RULE 1: DPIR1 triggers DL for 10 seconds ---
            if global_state.get("motion_dpir1", False):
                global_state["last_dpir1_time"] = now
                if not last_light_state:
                    _light_on_emit()
                    # keep it ON for 10 seconds from last motion
                    # (auto-off timer is not used here)

            if last_light_state and (now - global_state.get("last_dpir1_time", 0.0) > 10.0):
                _light_off_emit()

            # --- RULE 2: People counting (DPIR1 + DUS1) ---
            if global_state.get("motion_dpir1", False):
                dist1 = global_state.get("dus1_dist", 0.0)
                prev1 = global_state.get("dus1_prev_dist", 0.0)

                if not dpir1_counted and dist1 > 0 and prev1 > 0:
                    if dist1 < (prev1 - 2):
                        global_state["people_count"] += 1
                        dpir1_counted = True
                        send_system_event(device="SYSTEM", value=global_state["people_count"], type_name="PeopleCount", pi_id="1")
                        print(f"[LOG] PI1 Entry: People count: {global_state['people_count']}")
                    elif dist1 > (prev1 + 2):
                        global_state["people_count"] = max(0, global_state["people_count"] - 1)
                        dpir1_counted = True
                        send_system_event(device="SYSTEM", value=global_state["people_count"], type_name="PeopleCount", pi_id="1")
                        print(f"[LOG] PI1 Exit: People count: {global_state['people_count']}")
            else:
                dpir1_counted = False

            # --- RULE 2a: People counting (DPIR2 + DUS2) ---
            if global_state.get("motion_dpir2", False):
                dist2 = global_state.get("dus2_dist", 0.0)
                prev2 = global_state.get("dus2_prev_dist", 0.0)

                if not dpir2_counted and dist2 > 0 and prev2 > 0:
                    if dist2 < (prev2 - 2):
                        global_state["people_count"] += 1
                        dpir2_counted = True
                        send_system_event(device="SYSTEM", value=global_state["people_count"], type_name="PeopleCount", pi_id="2")
                        print(f"[LOG] PI2 Entry: People count: {global_state['people_count']}")
                    elif dist2 > (prev2 + 2):
                        global_state["people_count"] = max(0, global_state["people_count"] - 1)
                        dpir2_counted = True
                        send_system_event(device="SYSTEM", value=global_state["people_count"], type_name="PeopleCount", pi_id="2")
                        print(f"[LOG] PI2 Exit: People count: {global_state['people_count']}")
            else:
                dpir2_counted = False

            # --- RULE 3: Door left open (5 seconds) triggers alarm ---
            if global_state.get("door_open"):
                if global_state.get("ds1_open_time", 0.0) == 0.0:
                    global_state["ds1_open_time"] = now
                elif now - global_state["ds1_open_time"] > 5.0:
                    _trigger_alarm()
            else:
                global_state["ds1_open_time"] = 0.0

            # --- RULE 4: Arming delay ---
            if global_state.get("system_arming"):
                if nonlocal_vars["arming_start_time"] == 0.0:
                    nonlocal_vars["arming_start_time"] = now
                elif now - nonlocal_vars["arming_start_time"] > 10.0:
                    global_state["system_armed"] = True
                    global_state["system_arming"] = False
                    nonlocal_vars["arming_start_time"] = 0.0
                    send_system_event(device="SYSTEM", value=True, type_name="armed", pi_id="1")
                    print("[CONTROLLER] System ARMED")

            if global_state.get("system_armed") and global_state.get("door_open"):
                _trigger_alarm()

            # --- RULE 5: Empty house + motion triggers alarm ---
            if global_state.get("people_count", 0) == 0 and global_state.get("motion"):
                _trigger_alarm()

            # --- RULE 6: GSG significant motion triggers alarm ---
            if global_state.get("significant_motion_gsg", False):
                _trigger_alarm()

            # --- Alarm behavior: ensure buzzer ON while active ---
            if global_state.get("alarm_active"):
                if buzzer:
                    buzzer.on()
                    # Note: we don't spam events; we emitted alarm_on + DB on transition
                # you could also flash DL or set BRGB red here if you want

            # --- LCD rotation (PI3) ---
            if now - last_lcd_rotation_time > 5.0:
                current_dht = dht_list[dht_index]
                temp = global_state.get(f"dht{current_dht}_temp", 0.0)
                hum = global_state.get(f"dht{current_dht}_hum", 0.0)

                lcd_message = f"DHT{current_dht}: T:{temp}C H:{hum}%"
                global_state["lcd_message"] = lcd_message

                send_actuator_message(device="LCD", value=lcd_message, type_name="display", pi_id="3", simulated=True)
                print(f"[LCD ROTATION] Displaying: {lcd_message}")

                dht_index = (dht_index + 1) % len(dht_list)
                last_lcd_rotation_time = now

            # --- BRGB cycle (PI3) ---
            if rgb_cycle_enabled and rgb and (now - rgb_cycle_last > 1.0):
                _set_rgb(rgb_cycle_colors[rgb_cycle_idx])
                rgb_cycle_idx = (rgb_cycle_idx + 1) % len(rgb_cycle_colors)
                rgb_cycle_last = now

            time.sleep(0.2)

        # Cleanup on stop
        try:
            _cancel_timer(buzzer_timer)
            _cancel_timer(light_timer)
        except Exception:
            pass

    t = threading.Thread(target=control_loop, daemon=True, name="controller")
    t.start()
    return t