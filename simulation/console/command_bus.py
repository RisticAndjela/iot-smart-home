from actuators.controller import get_cmd_queue
def command_loop(stop_event):
    """Class for command bus to send commands to controller thread from console input thread"""
    cmd_queue = get_cmd_queue()
    while not stop_event.is_set():
        try:
            cmd = input("> ").strip().lower()
        except EOFError:
            continue
        if cmd:
            cmd_queue.put(cmd)
