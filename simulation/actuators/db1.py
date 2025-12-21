import threading
import time
import RPi.GPIO as GPIO

class DoorBuzzer:
    def __init__(self, pin, duration=1.0):
        self.pin = pin
        self.duration = duration  # duration in seconds
        GPIO.setup(pin, GPIO.OUT)
        
    def on(self): # trigger buzzer for duration
        def buzz():
            try:
                GPIO.output(self.pin, 1)
            except Exception:
                pass
            print(f"Buzzer ON (pin {self.pin})")
            time.sleep(self.duration)
            try:
                GPIO.output(self.pin, 0)
            except Exception:
                pass
            print(f"Buzzer finished (pin {self.pin})")
        
        threading.Thread(target=buzz, daemon=True).start()
