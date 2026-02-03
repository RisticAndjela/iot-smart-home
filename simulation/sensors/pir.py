try:
    import RPi.GPIO as GPIO
except ModuleNotFoundError:
    import fake_rpi
    GPIO = fake_rpi.RPi.GPIO

GPIO.setmode(GPIO.BCM)
import time

def run_pir_loop(delay, callback, stop_event, settings):
    port = settings['pin']
    GPIO.setup(port, GPIO.IN)
    
    # PIR nekad ima delay, ovde samo citamo stanje
    while True:
        if GPIO.input(port):
            callback(1) # Detektovan pokret
        else:
            callback(0) # Nema pokreta
            
        if stop_event.is_set():
            break
        time.sleep(delay)