try:
    import RPi.GPIO as GPIO
except ModuleNotFoundError:
    import fake_rpi
    GPIO = fake_rpi.RPi.GPIO

import time

def run_dms_loop(delay, callback, stop_event, settings):

    R = settings.get('R', [25, 8, 7, 1])  # Default pinovi za redove
    C = settings.get('C', [12, 16, 20, 21]) # Default pinovi za kolone
    
    keypad = [
        ["1","2","3","A"],
        ["4","5","6","B"],
        ["7","8","9","C"],
        ["*","0","#","D"]
    ]

    GPIO.setmode(GPIO.BCM)
    
    for pin in R:
        GPIO.setup(pin, GPIO.OUT)
    
    for pin in C:
        GPIO.setup(pin, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)

    def read_line(line, characters):
        GPIO.output(line, GPIO.HIGH)
        for i in range(4):
            if GPIO.input(C[i]) == 1:
                callback(characters[i])
                time.sleep(0.3) # "Debounce" da ne očita isti taster 5 puta
        GPIO.output(line, GPIO.LOW)

    while not stop_event.is_set():
        for i in range(4):
            read_line(R[i], keypad[i])
        time.sleep(delay)