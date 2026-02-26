import time
import threading
from simulation.state.global_state import global_state

def run_lcd(settings, threads, stop_event):
    device_name = settings['device']
    pi_id = settings['pi']
    simulated = settings.get('simulated', True)

    lcd = None
    mcp = None
    if not simulated:
        try:
            from simulation.actuators.PCF8574 import PCF8574_GPIO
            from simulation.actuators.Adafruit_LCD1602 import Adafruit_CharLCD
            
            try:
                mcp = PCF8574_GPIO(0x27)
            except Exception:
                try:
                    mcp = PCF8574_GPIO(0x3F)
                except Exception as e:
                    print(f"[{device_name}] I2C Address Error: {e}")
            
            if mcp:
                lcd = Adafruit_CharLCD(pin_rs=0, pin_e=2, pins_db=[4,5,6,7], GPIO=mcp)
                mcp.output(3, 1)  
                lcd.begin(16, 2)
                lcd.clear()
                print(f"[{device_name}] I2C LCD initialized successfully.")
        except Exception as e:
            print(f"[{device_name}] Hardware init failed. Da li su PCF8574 i Adafruit fajlovi tu? Greska: {e}")

    def lcd_loop():
        print(f"Starting {device_name} loop on PI{pi_id}...")
        last_msg = ""
        
        while not stop_event.is_set():

            raw_msg = global_state.get("lcd_message", "Waiting...")
            
            if raw_msg != last_msg:
                if " " in raw_msg and not raw_msg.startswith("Wait"):
                    parts = raw_msg.split(" ", 1)
                    display_msg = f"{parts[0]}\n{parts[1]}"
                else:
                    display_msg = raw_msg

                if simulated or not lcd:
                    print(f"[SIM ACTUATOR] {device_name} Displaying:\n{display_msg}")
                else:
                    try:
                        lcd.clear()
                        lcd.setCursor(0, 0)
                        lcd.message(display_msg)
                    except Exception as e:
                        print(f"[{device_name}] Display error: {e}")
                
                last_msg = raw_msg
                
            time.sleep(0.5) 

    t = threading.Thread(target=lcd_loop, daemon=True)
    t.start()
    threads.append(t)