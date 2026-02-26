import time

def run_gyro_real_loop(callback, stop_event, delay):
    try:
        import smbus
        bus = smbus.SMBus(1)

        Device_Address = 0x68
        
        bus.write_byte_data(Device_Address, 0x19, 7)
        bus.write_byte_data(Device_Address, 0x6B, 1)
        bus.write_byte_data(Device_Address, 0x1C, 0)
        bus.write_byte_data(Device_Address, 0x1B, 24)
        bus.write_byte_data(Device_Address, 0x38, 1)
        
        def read_raw_data(addr):
            high = bus.read_byte_data(Device_Address, addr)
            low = bus.read_byte_data(Device_Address, addr+1)
            value = ((high << 8) | low)
            if value > 32768:
                value = value - 65536
            return value

        while not stop_event.is_set():

            acc_z = read_raw_data(0x3F)
            Az = acc_z / 16384.0 
            
            is_shaking = abs(Az) > 1.5
            
            callback(round(Az * 9.81, 2), is_shaking)
            time.sleep(delay)
            
    except Exception as e:
        print(f"[GSG ERROR] Nije moguće pokrenuti pravi I2C žiroskop: {e}")