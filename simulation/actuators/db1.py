import threading
import time
try:
    import RPi.GPIO as GPIO
except ModuleNotFoundError:
    import fake_rpi
    GPIO = fake_rpi.RPi.GPIO

GPIO.setmode(GPIO.BCM)

class DoorBuzzer:
    def __init__(self, pin):
        self.pin = pin
        GPIO.setup(pin, GPIO.OUT)
        # Osiguravamo da je ugašen na početku
        try:
            GPIO.output(self.pin, 0)
        except Exception:
            pass
        
    def on(self):
        """Uključuje zujalicu kontinuirano"""
        try:
            GPIO.output(self.pin, 1)
        except Exception:
            pass
        print(f"Buzzer ON (pin {self.pin})")

    def off(self):
        """Isključuje zujalicu"""
        try:
            GPIO.output(self.pin, 0)
        except Exception:
            pass
        print(f"Buzzer OFF (pin {self.pin})")