import time

def console_loop(stop_event):
    """ Client console loop to display available commands, waits for user input in command bus for 0.1s intervals
        no other actions needed here
    """
    print("Console ready:")
    print("  l - toggle door light")
    print("  b - trigger buzzer")
    print("  q - quit application")

    while not stop_event.is_set():
        try:
            # small sleep to avoid busy waiting
            time.sleep(0.1)
        except KeyboardInterrupt:
            break
