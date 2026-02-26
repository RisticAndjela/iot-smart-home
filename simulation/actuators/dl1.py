try:
    import RPi.GPIO as GPIO
except (ImportError, ModuleNotFoundError):
    import fake_rpi
    GPIO = fake_rpi.RPi.GPIO

class DoorLight:
    def __init__(self, pin):
        self.pin = pin
        self.is_on = False
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(self.pin, GPIO.OUT)
        self.off() # Inicijalno ugasimo diodu

    def on(self):
        self.is_on = True
        print(f"[HW] Light ON (pin {self.pin})")
        try:
            GPIO.output(self.pin, GPIO.HIGH) # Može i 1
        except Exception as e:
            print(f"GPIO Error ON: {e}")

    def off(self):
        self.is_on = False
        print(f"[HW] Light OFF (pin {self.pin})")
        try:
            GPIO.output(self.pin, GPIO.LOW) # Može i 0
        except Exception as e:
            print(f"GPIO Error OFF: {e}")

    def toggle(self):
        """Korisno za dugmad na frontendu"""
        if self.is_on:
            self.off()
        else:
            self.on()