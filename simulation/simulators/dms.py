import time
import random

def generate_pin_sequence():
    pin = ['1', '2', '3', '4']
    while True:
        for digit in pin:
            yield digit
        time.sleep(20) # Pauza između dva unosa PIN-a

def run_dms_simulator(delay, callback, stop_event):
    for digit in generate_pin_sequence():
        # Simuliramo brzinu kucanja čoveka (npr. 0.5s između cifara)
        time.sleep(0.5) 
        callback(digit)
        if stop_event.is_set():
            break