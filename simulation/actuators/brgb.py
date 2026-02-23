try:
    import RPi.GPIO as GPIO
except ImportError:
    import fake_rpi
    GPIO = fake_rpi.RPi.GPIO

class RGB_LED:
    def __init__(self, settings):
        self.device_name = settings['device']
        self.pins = settings['pins'] 
        self.simulated = settings['simulated']
        
        if not self.simulated:
            for pin in self.pins.values():
                GPIO.setup(pin, GPIO.OUT)
                GPIO.output(pin, 0)
        
        print(f"[{self.device_name}] Initialized with pins: {self.pins}")

    def set_color(self, r, g, b):
        color_name = "OFF"
        if r and not g and not b: color_name = "RED"
        elif not r and g and not b: color_name = "GREEN"
        elif not r and not g and b: color_name = "BLUE"
        elif r and g and b: color_name = "WHITE"
        
        print(f"[ACTUATOR] RGB LED set to {color_name}")
        
        GPIO.output(self.pins['r'], r)
        GPIO.output(self.pins['g'], g)
        GPIO.output(self.pins['b'], b)

    def turn_off(self):
        self.set_color(0, 0, 0)