import time
import random

def generate_values():
    while True:
        # Simuliramo otvaranje/zatvaranje vrata (0 ili 1)
        yield random.randint(0, 1)

def run_ds_simulator(delay, callback, stop_event):
    for value in generate_values():
        time.sleep(delay)
        callback(value)
        if stop_event.is_set():
            break