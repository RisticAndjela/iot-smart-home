try:
    import RPi.GPIO as GPIO
except ImportError:
    import fake_rpi
    fake_rpi.toggle_print(False)
    GPIO = fake_rpi.RPi.GPIO


class RGB_LED:
    """
    Simple RGB LED actuator driver.

    Important: this class should NOT publish MQTT/Influx events.
    Event emission belongs to the controller (business logic layer).
    """

    def __init__(self, settings):
        self.device_name = str(settings["device"]).upper()   # e.g. "BRGB"
        self.pins = settings["pins"]                         # {"r":17,"g":27,"b":22}
        self.simulated = bool(settings.get("simulated", True))
        self.current_color = "OFF" # FOR DEBUG

        if not self.simulated:
            try:
                GPIO.setmode(GPIO.BCM)
            except Exception:
                # Some GPIO backends may already be configured; ignore
                pass

            for pin in self.pins.values():
                GPIO.setup(pin, GPIO.OUT)
                try:
                    GPIO.output(pin, 0)
                except Exception:
                    pass

        print(f"[{self.device_name}] Initialized with pins: {self.pins} (simulated={self.simulated})")

    def _apply(self, r: int, g: int, b: int):
        """
        Applies raw RGB values (0/1) to GPIO when not simulated.
        """
        if self.simulated:
            return

        try:
            GPIO.output(self.pins["r"], int(bool(r)))
            GPIO.output(self.pins["g"], int(bool(g)))
            GPIO.output(self.pins["b"], int(bool(b)))
        except Exception as e:
            # Keep running even if GPIO is not available
            print(f"[{self.device_name}] GPIO write failed: {e}")

    def set_color(self, r: int, g: int, b: int):
        """
        Sets a color using raw RGB channels (0/1).
        Also updates current_color for logging.
        """
        if r and not g and not b:
            color_name = "RED"
        elif not r and g and not b:
            color_name = "GREEN"
        elif not r and not g and b:
            color_name = "BLUE"
        elif r and g and b:
            color_name = "WHITE"
        else:
            color_name = "OFF"

        self.current_color = color_name
        print(f"[ACTUATOR] {self.device_name} set to {color_name}")

        self._apply(r, g, b)

    def set_color_name(self, color: str):
        """
        Sets a color by name: RED/GREEN/BLUE/WHITE/OFF.
        """
        color = (color or "OFF").strip().upper()

        if color == "RED":
            self.set_color(1, 0, 0)
        elif color == "GREEN":
            self.set_color(0, 1, 0)
        elif color == "BLUE":
            self.set_color(0, 0, 1)
        elif color == "WHITE":
            self.set_color(1, 1, 1)
        else:
            self.turn_off()

    def turn_off(self):
        self.current_color = "OFF"
        print(f"[ACTUATOR] {self.device_name} set to OFF")
        self._apply(0, 0, 0)