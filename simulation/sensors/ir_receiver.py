import time
from datetime import datetime
try:
    import RPi.GPIO as GPIO
except ImportError:
    import fake_rpi
    GPIO = fake_rpi.RPi.GPIO

def run_ir_real_loop(pin, callback, stop_event):
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(pin, GPIO.IN)

    def getBinary():
        num1s = 0 
        binary = 1 
        command = [] 
        previousValue = 0 
        value = GPIO.input(pin) 

        while value:
            time.sleep(0.0001)
            value = GPIO.input(pin)
            if stop_event.is_set(): return None
            
        startTime = datetime.now()
        
        while not stop_event.is_set():
            if previousValue != value:
                now = datetime.now()
                pulseTime = now - startTime
                startTime = now
                command.append((previousValue, pulseTime.microseconds))
                
            if value: num1s += 1
            else: num1s = 0
            
            if num1s > 10000: break
                
            previousValue = value
            value = GPIO.input(pin)
            
        for (typ, tme) in command:
            if typ == 1:
                if tme > 1000:
                    binary = binary * 10 + 1
                else:
                    binary *= 10
                    
        if len(str(binary)) > 34:
            binary = int(str(binary)[:34])
            
        return binary

    def convertHex(binaryValue):
        tmpB2 = int(str(binaryValue), 2)
        return hex(tmpB2)

    while not stop_event.is_set():
        value = GPIO.input(pin)
        # Kada senzor padne na 0, detektovan je početak signala
        if value == 0:
            bin_val = getBinary()
            if bin_val:
                hex_val = convertHex(bin_val)
                callback(hex_val) # Ovo šalje "0x300ff30cf" u components/ir.py
            time.sleep(0.5) # Debounce
        else:
            time.sleep(0.1)