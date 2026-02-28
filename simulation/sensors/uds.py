try:
    import RPi.GPIO as GPIO
except ModuleNotFoundError:
    import fake_rpi
    fake_rpi.toggle_print(False)
    GPIO = fake_rpi.RPi.GPIO

import time


def get_distance(trig, echo):
    GPIO.output(trig, False)
    time.sleep(0.2)
    GPIO.output(trig, True)
    time.sleep(0.00001)
    GPIO.output(trig, False)

    pulse_start = time.time()
    pulse_end = time.time()

    timeout = time.time() + 0.1
    while GPIO.input(echo) == 0:
        pulse_start = time.time()
        if pulse_start > timeout:
            return None

    while GPIO.input(echo) == 1:
        pulse_end = time.time()
        if pulse_end > timeout:
            return None

    pulse_duration = pulse_end - pulse_start
    distance = pulse_duration * 17150
    return round(distance, 2)


def run_uds_loop(delay, callback, stop_event, settings):
    trig = settings["pin_trig"]
    echo = settings["pin_echo"]

    try:
        GPIO.setmode(GPIO.BCM)
    except Exception:
        pass

    GPIO.setup(trig, GPIO.OUT)
    GPIO.setup(echo, GPIO.IN)

    while not stop_event.is_set():
        dist = get_distance(trig, echo)
        if dist is not None:
            callback(dist)
        time.sleep(delay)