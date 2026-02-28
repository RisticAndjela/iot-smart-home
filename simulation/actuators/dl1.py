try:
    import RPi.GPIO as GPIO
except ModuleNotFoundError:
    import fake_rpi
    fake_rpi.toggle_print(False)
    GPIO = fake_rpi.RPi.GPIO


class DoorLight:
    """
    Simple RGB door light actuator driver.

    Important: this class should NOT publish MQTT/Influx events.
    Event emission belongs to the controller (business logic layer).
    """

    def __init__(self, pins):
        # pins example: {"r": 13, "g": 19, "b": 12}
        self.pins = dict(pins)
        self.is_on = False
        self.current_color = "OFF"

        try:
            GPIO.setmode(GPIO.BCM)
        except Exception:
            pass

        for _, pin in self.pins.items():
            GPIO.setup(pin, GPIO.OUT)
            try:
                GPIO.output(pin, 0)
            except Exception:
                pass

    def _apply(self, r_val: int, g_val: int, b_val: int):
        """
        Applies raw RGB values (0/1) to GPIO.
        """
        try:
            GPIO.output(self.pins["r"], int(bool(r_val)))
            GPIO.output(self.pins["g"], int(bool(g_val)))
            GPIO.output(self.pins["b"], int(bool(b_val)))
        except Exception as e:
            print(f"[DL] GPIO write failed: {e}")

    def on(self, color: str = "WHITE"):
        """
        Turns the light on and sets a color.
        Supported colors: WHITE, RED, GREEN, BLUE.
        """
        color = (color or "WHITE").strip().upper()
        self.is_on = True
        self.current_color = color

        if color == "RED":
            self._apply(1, 0, 0)
        elif color == "GREEN":
            self._apply(0, 1, 0)
        elif color == "BLUE":
            self._apply(0, 0, 1)
        else:
            # Default to white
            self._apply(1, 1, 1)

        print(f"[ACTUATOR] DoorLight ON (color: {self.current_color})")

    def off(self):
        """
        Turns the light off.
        """
        self.is_on = False
        self.current_color = "OFF"
        self._apply(0, 0, 0)
        print("[ACTUATOR] DoorLight OFF")