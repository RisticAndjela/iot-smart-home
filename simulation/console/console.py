import time

def console_loop(stop_event, dl_actuator, db_actuator):
    print("Console ready:")
    print("  l - toggle door light")
    print("  b - trigger buzzer")
    print("  q - quit application")

    while not stop_event.is_set():
        try:
            user_input = input(">> ").strip().lower()

            if user_input == 'l':
                if dl_actuator:
                    dl_actuator.toggle()
                    # if dl_actuator.is_on:
                    #     dl_actuator.off()
                    # else:
                    #     dl_actuator.on()
                else:
                    print("Door light not initialized.")

            elif user_input == 'b':
                if db_actuator:
                    db_actuator.on()
                else:
                    print("Buzzer not initialized.")

            elif user_input == 'q':
                stop_event.set()
                break

        except KeyboardInterrupt:
            stop_event.set()
            break
        except Exception as e:
            print(f"Error in console: {e}")