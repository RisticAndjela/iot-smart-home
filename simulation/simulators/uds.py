import time
import random

def generate_values():
    while True:
        # Simuliramo distancu u cm (npr. izmedju 10 i 100 cm)
        yield round(random.uniform(10.0, 100.0), 2)

def run_uds_simulator(delay, callback, stop_event):
    for distance in generate_values():
        time.sleep(delay)
        callback(distance)
        if stop_event.is_set():
            break