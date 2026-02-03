from influxdb_client import Point

def write_event_to_influx(write_api, bucket, event):
    if not write_api:
        print("Write API not available, cannot write to InfluxDB")
        return
    point = (
        Point(event.device)
        .tag("pi", event.pi_id)
        .tag("sensor_type", event.sensor_type)
        .field("value", float(event.value))
        .field("simulated", int(event.simulated))
        .time(int(event.timestamp * 1e9))
    )
    write_api.write(bucket=bucket, record=point)
    # print(f"Wrote event to InfluxDB: {point}")
