try:
    import RPi.GPIO as GPIO
except ModuleNotFoundError:
    import fake_rpi
    fake_rpi.toggle_print(False)
    import sys
    sys.modules["RPi"] = fake_rpi.RPi
    sys.modules["RPi.GPIO"] = fake_rpi.RPi.GPIO
    import RPi.GPIO as GPIO


class DoorBuzzer:
    """
    Simple buzzer actuator driver.

    Important: this class should NOT publish MQTT/Influx events.
    Event emission belongs to the controller (business logic layer).
    """

    def __init__(self, pin: int):
        self.pin = int(pin)
        self.is_on = False

        try:
            GPIO.setmode(GPIO.BCM)
        except Exception:
            # Ignore if GPIO mode was already configured elsewhere
            pass

        GPIO.setup(self.pin, GPIO.OUT)

        # Ensure buzzer starts OFF
        try:
            GPIO.output(self.pin, 0)
        except Exception:
            pass

    def on(self):
        if self.is_on:
            return
        try:
            GPIO.output(self.pin, 1)
        except Exception:
            pass
        self.is_on = True
        print(f"[ACTUATOR] Buzzer ON (pin {self.pin})")

    def off(self):
        if not self.is_on:
            return
        try:
            GPIO.output(self.pin, 0)
        except Exception:
            pass
        self.is_on = False
        print(f"[ACTUATOR] Buzzer OFF (pin {self.pin})")