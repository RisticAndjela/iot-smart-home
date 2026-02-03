import time
import random

def generate_values():
    while True:
        yield 1  

def run_dms_simulator(delay, callback, stop_event):
    for value in generate_values():
        time.sleep(delay)
        callback(value)
        if stop_event.is_set():
            break
