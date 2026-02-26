import threading
import time
try:
    import RPi.GPIO as GPIO
except ModuleNotFoundError:
    import fake_rpi
    import sys
    sys.modules['RPi'] = fake_rpi.RPi
    sys.modules['RPi.GPIO'] = fake_rpi.RPi.GPIO
    import RPi.GPIO as GPIO

GPIO.setmode(GPIO.BCM)

class DoorBuzzer:
    def __init__(self, pin):
        self.pin = pin
        self.is_on = False
        GPIO.setup(pin, GPIO.OUT)
        try:
            GPIO.output(self.pin, 0)
        except Exception:
            pass
        
    def on(self):
        if not self.is_on:
            try:
                GPIO.output(self.pin, 1)
            except Exception:
                pass
            self.is_on = True
            print(f"Buzzer ON (pin {self.pin})")

    def off(self):
        if self.is_on:
            try:
                GPIO.output(self.pin, 0)
            except Exception:
                pass
            self.is_on = False
            print(f"Buzzer OFF (pin {self.pin})")