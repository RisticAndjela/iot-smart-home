from influxdb_client import Point

def write_event_to_influx(write_api, bucket, event):
    if not write_api:
        return

    measurement_name = event.sensor_type.capitalize()
    device_upper = event.device.upper()

    # Specijalni slučajevi gde želimo specifično ime tabele
    if device_upper == "BRGB":
        measurement_name = "BRGB"
    elif device_upper == "LCD":
        measurement_name = "Lcd"
    elif device_upper == "4SD":
        measurement_name = "Kitchen_Timer"

    # 2. Kreiramo Point sa tagovima
    point = (
        Point(measurement_name) 
        .tag("pi", event.pi_id)
        .tag("device", event.device) # Dodajemo device i kao tag za lakše filtriranje
        .tag("sensor_type", event.sensor_type)
    )

    # 3. Pokušavamo da odredimo da li pišemo broj (value) ili tekst (message)
    try:
        # Za PeopleCount, Temp, Hum, Door status (0/1)...
        val = float(event.value)
        point.field("value", val)
    except (ValueError, TypeError):
        # Za LCD poruke i BRGB boje (npr. "RED", "GREEN")
        point.field("message", str(event.value))

    point.field("simulated", int(event.simulated))
    point.time(int(event.timestamp * 1e9))
    
    try:
        write_api.write(bucket=bucket, record=point)
        # Opcioni log da u konzoli vidiš potvrdu za BRGB
        if measurement_name == "BRGB":
            print(f"[LOCAL_DB] Uspešan upis u BRGB: {event.value}")
    except Exception as e:
        print(f"Baza odbija upis za {event.device}: {e}")