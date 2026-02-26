import time
import random

def generate_values():
    while True:
        # Simuliramo detekciju pokreta (0 ili 1)
        if random.random() < 0.2: 
            yield 1
        else:
            yield 0

def run_pir_simulator(delay, callback, stop_event):
    for value in generate_values():
        time.sleep(delay)
        callback(value)
        if stop_event.is_set():
            break