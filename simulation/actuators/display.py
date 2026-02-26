import threading
import time
from messaging.event_queue import event_queue
from simulation.sensors.sensor_event import SensorEvent

def run_4sd(settings, threads, stop_event):
    device_name = settings['device']
    pi_id = settings['pi']
    simulated = settings.get('simulated', True)
    
    display_state = {"text": "    "}

    # --- 1. BRZA HARDVERSKA PETLJA (MULTIPLEKSIRANJE) ---
    def multiplexer_loop():
        try:
            import RPi.GPIO as GPIO
        except ImportError:
            import fake_rpi
            GPIO = fake_rpi.RPi.GPIO

        GPIO.setmode(GPIO.BCM)
        
        segments = settings.get('segments', (11,4,23,8,7,10,18,25))
        digits = settings.get('digits', (22,27,17,24))

        for segment in segments:
            GPIO.setup(segment, GPIO.OUT)
            GPIO.output(segment, 0)
        for digit in digits:
            GPIO.setup(digit, GPIO.OUT)
            GPIO.output(digit, 1)

        num_map = {
            ' ':(0,0,0,0,0,0,0), '0':(1,1,1,1,1,1,0),
            '1':(0,1,1,0,0,0,0), '2':(1,1,0,1,1,0,1),
            '3':(1,1,1,1,0,0,1), '4':(0,1,1,0,0,1,1),
            '5':(1,0,1,1,0,1,1), '6':(1,0,1,1,1,1,1),
            '7':(1,1,1,0,0,0,0), '8':(1,1,1,1,1,1,1),
            '9':(1,1,1,1,0,1,1)
        }

        try:
            while not stop_event.is_set():
                s = display_state["text"].rjust(4)
                
                for digit_idx in range(4):
                    char = s[digit_idx] if digit_idx < len(s) else ' '
                    if char not in num_map: char = ' '
                    
                    for loop in range(0,7):
                        GPIO.output(segments[loop], num_map[char][loop])
                    
                    GPIO.output(digits[digit_idx], 0)
                    time.sleep(0.001) # Tromost oka (1ms)
                    
                    GPIO.output(digits[digit_idx], 1)
        finally:
            GPIO.cleanup()

    def timer_loop():
        if not simulated:
            mux_thread = threading.Thread(target=multiplexer_loop, daemon=True)
            mux_thread.start()

        print(f"Starting {device_name} Kitchen Timer on PI{pi_id}...")

        while not stop_event.is_set():
            time.sleep(15)
            
            for i in range(5, -1, -1):
                if stop_event.is_set(): break
                
                display_str = f"{i:04d}" 
                
                display_state["text"] = display_str

                if simulated:
                    print(f"[SIM] {device_name} Timer: {display_str}")

                event = SensorEvent(
                    pi_id=pi_id,
                    device=device_name,
                    sensor_type="actuator", 
                    value=display_str,
                    simulated=simulated,
                    timestamp=time.time()
                )
                event_queue.put(event)
                time.sleep(1) 
                
            display_state["text"] = "0000"

    t = threading.Thread(target=timer_loop, daemon=True)
    t.start()
    threads.append(t)