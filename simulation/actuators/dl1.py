try:
    import RPi.GPIO as GPIO
except ModuleNotFoundError:
    import fake_rpi
    GPIO = fake_rpi.RPi.GPIO

GPIO.setmode(GPIO.BCM)

class DoorLight:
    def __init__(self, pin):
        self.pin = pin
        self.is_on = False
        GPIO.setup(pin, GPIO.OUT)
        try:
            GPIO.output(pin, 0)
        except Exception:
            pass

    def on(self): # turn light on
        if not self.is_on:
            self.is_on = True
            print(f"Light ON (pin {self.pin})")
            try:
                GPIO.output(self.pin, 1)
            except Exception:
                pass

    def off(self): # turn light off
        if self.is_on:
            self.is_on = False
            print(f"Light OFF (pin {self.pin})")
            try:
                GPIO.output(self.pin, 0)
            except Exception:
                pass
