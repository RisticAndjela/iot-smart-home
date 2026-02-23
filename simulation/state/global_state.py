# Dopuni svoj global_state.py ovim ključevima
global_state = {
    "door_open": False,
    "motion": False,
    "dms_pressed": False,
    "people_count": 0,
    "alarm_active": False,
    "system_armed": False,
    "system_arming": False,
    "last_dpir1_time": 0,
    "ds1_open_time": 0,
    "ds2_open_time": 0,
    "dus1_dist": 0,
    "dus1_prev_dist": 0,
    "significant_motion_gsg": False,
    "pin_entered": "" # Ovdje ćemo spremati cifre sa DMS-a
}