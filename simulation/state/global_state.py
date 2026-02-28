from threading import RLock

global_state_lock = RLock()

global_state = {
    # --- Security / alarm system ---
    "alarm_active": False,
    "system_armed": False,
    "system_arming": False,
    # --- Door sensors ---
    "door_open": False,     # generic door state (used in controller rules)
    "ds1_open": False,
    "ds2_open": False,
    "ds1_open_time": 0.0,
    "ds2_open_time": 0.0,
    # --- Motion sensors ---
    "motion": False,        # generic motion (if you use it)
    "motion_dpir1": False,
    "motion_dpir2": False,
    "motion_dpir3": False,
    "last_dpir1_time": 0.0,
    # --- Ultrasonic sensors ---
    "dus1_dist": 0.0,
    "dus1_prev_dist": 0.0,
    "dus2_dist": 0.0,
    "dus2_prev_dist": 0.0,
    # --- Gyro (GSG) ---
    "significant_motion_gsg": False,
    # --- People counting ---
    "people_count": 0,
    # --- Keypad ---
    "pin_buffer": "",
    # --- Button ---
    "btn_pressed": False,
    # --- DHT sensors (ensure keys exist so LCD rotation doesn't show 0 forever due to missing keys) ---
    "dht1_temp": 0.0,
    "dht1_hum": 0.0,
    "dht2_temp": 0.0,
    "dht2_hum": 0.0,
    "dht3_temp": 0.0,
    "dht3_hum": 0.0,
    "lcd_message": "Waiting...",
}