try:
    import RPi.GPIO as GPIO
except ModuleNotFoundError:
    import fake_rpi
    fake_rpi.toggle_print(False)
    GPIO = fake_rpi.RPi.GPIO

import time


def run_pir_loop(delay, callback, stop_event, settings):
    port = settings["pin"]

    try:
        GPIO.setmode(GPIO.BCM)
    except Exception:
        pass

    GPIO.setup(port, GPIO.IN)

    while not stop_event.is_set():
        callback(1 if GPIO.input(port) else 0)
        time.sleep(delay)