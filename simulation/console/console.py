from simulation.console.command_bus import enqueue_command


def console_loop(stop_event):
    print("Console ready:")
    print("  l - toggle door light (controller)")
    print("  b - buzzer ON (controller)")
    print("  boff - buzzer OFF (controller)")
    print("  brgb_red / brgb_green / brgb_blue / brgb_white / brgb_off")
    print("  q - quit application")

    while not stop_event.is_set():
        try:
            user_input = input(">> ").strip().lower()
        except KeyboardInterrupt:
            stop_event.set()
            break
        except EOFError:
            continue

        if not user_input:
            continue

        if user_input == "q":
            stop_event.set()
            break

        enqueue_command(user_input)