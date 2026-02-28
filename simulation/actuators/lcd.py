import time
import threading
from simulation.state.global_state import global_state


def _format_for_16x2(msg: str) -> str:
    """
    Formats a message for a 16x2 LCD.
    - If message already contains a newline, keep it.
    - Otherwise try to split into two lines.
    """
    msg = (msg or "").strip()

    if "\n" in msg:
        lines = msg.split("\n", 1)
        return f"{lines[0][:16]}\n{lines[1][:16]}"

    # Try to split on first space so it looks nicer
    if " " in msg and not msg.lower().startswith("wait"):
        left, right = msg.split(" ", 1)
        return f"{left[:16]}\n{right[:16]}"

    # Fallback: hard wrap
    return f"{msg[:16]}\n{msg[16:32]}"


def run_lcd(settings, threads, stop_event):
    device_name = settings["device"]          # e.g. "LCD"
    pi_id = settings["pi"]                   # e.g. "3"
    simulated = settings.get("simulated", True)

    lcd = None
    mcp = None

    # Hardware init only when not simulated
    if not simulated:
        try:
            from actuators.hardware.PCF8574 import PCF8574_GPIO
            from actuators.hardware.Adafruit_LCD1602 import Adafruit_CharLCD

            # Try common I2C addresses
            try:
                mcp = PCF8574_GPIO(0x27)
            except Exception:
                mcp = PCF8574_GPIO(0x3F)

            lcd = Adafruit_CharLCD(pin_rs=0, pin_e=2, pins_db=[4, 5, 6, 7], GPIO=mcp)
            mcp.output(3, 1)  # enable backlight
            lcd.begin(16, 2)
            lcd.clear()

            print(f"[{device_name}] I2C LCD initialized successfully on PI{pi_id}.")
        except Exception as e:
            print(f"[{device_name}] Hardware init failed on PI{pi_id}: {e}")
            lcd = None
            mcp = None

    def lcd_loop():
        print(f"Starting {device_name} loop on PI{pi_id}...")
        last_msg = None

        while not stop_event.is_set():
            raw_msg = global_state.get("lcd_message", "Waiting...")

            # Update only when message changes
            if raw_msg != last_msg:
                formatted = _format_for_16x2(str(raw_msg))

                if simulated or lcd is None:
                    print(f"[SIM ACTUATOR] {device_name} displaying:\n{formatted}")
                else:
                    try:
                        lcd.clear()
                        lcd.setCursor(0, 0)
                        lcd.message(formatted)
                    except Exception as e:
                        print(f"[{device_name}] Display error: {e}")

                last_msg = raw_msg

            time.sleep(0.2)

    t = threading.Thread(target=lcd_loop, daemon=True)
    t.start()
    threads.append(t)