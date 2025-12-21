import RPi.GPIO as GPIO
import time

def run_dms_loop(delay, callback, stop_event, settings):
    port = settings['pin']
    GPIO.setup(port, GPIO.IN, pull_up_down=GPIO.PUD_UP)
    
    prev_val = None 
    
    while True:
        val = GPIO.input(port)
        if val != prev_val:
            callback(val)
            prev_val = val
        
        if stop_event.is_set():
            break
        time.sleep(delay)
