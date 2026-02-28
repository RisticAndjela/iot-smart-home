try:
    import RPi.GPIO as GPIO
except ModuleNotFoundError:
    import fake_rpi
    fake_rpi.toggle_print(False)
    GPIO = fake_rpi.RPi.GPIO

import time


def run_ds_loop(delay, callback, stop_event, settings):
    port = settings["pin"]

    # Configure GPIO when the loop starts (not at import time)
    try:
        GPIO.setmode(GPIO.BCM)
    except Exception:
        pass

    GPIO.setup(port, GPIO.IN, pull_up_down=GPIO.PUD_UP)

    prev_val = None

    while not stop_event.is_set():
        val = GPIO.input(port)
        if val != prev_val:
            callback(val)
            prev_val = val

        time.sleep(delay)