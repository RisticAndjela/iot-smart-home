try:
    import RPi.GPIO as GPIO
except ModuleNotFoundError:
    import fake_rpi
    GPIO = fake_rpi.RPi.GPIO

GPIO.setmode(GPIO.BCM)

class DoorLight:
    def __init__(self, pins):
        self.pins = pins
        self.is_on = False
        
        for color, pin in self.pins.items():
            GPIO.setup(pin, GPIO.OUT)
            try:
                GPIO.output(pin, 0) 
            except Exception:
                pass

    def on(self, color='white'): 
        self.is_on = True
        print(f"Light ON (color: {color})")
        
        try:
            if color == 'red':
                self._set_rgb(1, 0, 0)
            elif color == 'green':
                self._set_rgb(0, 1, 0)
            elif color == 'blue':
                self._set_rgb(0, 0, 1)
            else: # White
                self._set_rgb(1, 1, 1)
        except Exception as e:
            print(f"Error turning on RGB: {e}")

    def off(self):
        self.is_on = False
        print("Light OFF")
        try:
            self._set_rgb(0, 0, 0)
        except Exception:
            pass

    def _set_rgb(self, r_val, g_val, b_val):
        GPIO.output(self.pins['r'], r_val)
        GPIO.output(self.pins['g'], g_val)
        GPIO.output(self.pins['b'], b_val)