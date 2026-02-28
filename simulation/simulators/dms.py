import time


def run_dms_simulator(delay, callback, stop_event):
    """
    Simulates a user entering 1234, with a pause between sequences.
    """
    pin = ["1", "2", "3", "4"]

    while not stop_event.is_set():
        for digit in pin:
            if stop_event.is_set():
                break
            time.sleep(delay)   # speed of typing
            callback(digit)

        # pause between PIN entries, but keep it interruptible
        for _ in range(40):     # 40 * 0.5s = 20s
            if stop_event.is_set():
                break
            time.sleep(0.5)