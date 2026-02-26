from simulation.actuators.controller import get_cmd_queue


def enqueue_command(cmd: str):
    if cmd is None:
        return
    cmd = str(cmd).strip().lower()
    if not cmd:
        return
    get_cmd_queue().put(cmd)


def command_loop(stop_event):
    while not stop_event.is_set():
        try:
            cmd = input(">> ").strip().lower()
        except EOFError:
            continue
        except KeyboardInterrupt:
            stop_event.set()
            break

        if cmd:
            enqueue_command(cmd)