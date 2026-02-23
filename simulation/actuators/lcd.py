import time
import threading

try:
    import RPi.GPIO as GPIO
except ModuleNotFoundError:
    import fake_rpi
    GPIO = fake_rpi.RPi.GPIO

# Za pravi rad na Malini, instaliraj: pip install RPLCD

HAS_RPLCD = False
try:
    from RPLCD.gpio import CharLCD
    HAS_RPLCD = True
except ImportError:
    HAS_RPLCD = False

def run_lcd(settings, threads, stop_event):
    device_name = settings['device']
    pi_id = settings['pi']
    simulated = settings['simulated']
    # Očekujemo listu pinova iz settings.json: [RS, E, D4, D5, D6, D7]
    pins = settings['pins'] 

    # --- Inicijalizacija hardvera ---
    lcd = None
    if not simulated and HAS_RPLCD:
        try:
            # Podešavanje za 16x2 LCD u paralelnom modu
            lcd = CharLCD(pin_rs=pins[0], pin_e=pins[1], 
                          pins_data=[pins[2], pins[3], pins[4], pins[5]],
                          numbering_mode=GPIO.BCM,
                          cols=16, rows=2)
            print(f"[{device_name}] Real LCD initialized.")
        except Exception as e:
            print(f"[{device_name}] Hardware init failed: {e}")

    def lcd_loop():
        print(f"Starting {device_name} loop...")
        while not stop_event.is_set():
            # Poruka koju ispisujemo
            msg = "Welcome home!"
            
            if simulated or not lcd:
                # Simulacija: Samo ispis u konzolu
                print(f"[ACTUATOR] {device_name} display: {msg}")
                time.sleep(10)
            else:
                # Pravi hardver
                try:
                    lcd.clear()
                    lcd.write_string(msg)
                except Exception as e:
                    print(f"[{device_name}] Display error: {e}")
                time.sleep(60)

    t = threading.Thread(target=lcd_loop, daemon=True)
    t.start()
    threads.append(t)