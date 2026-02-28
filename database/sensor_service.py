from influxdb_client import Point
from typing import Optional


def write_event_to_influx(write_api, bucket, event, *, kind: Optional[str] = None):
    """
    writes a single event to InfluxDB, primarily grouped *by device*, with a PI prefix:
        measurement = "PI{id}_{DEVICE}"
        e.g. "PI1_DS1", "PI3_BRGB"
    tags are used for filtering (pi, device, type, kind, mqtt_topic),
    while the payload is stored as either a numeric `value` field or a text `message` field.
    """
    if write_api is None:
        return

    # PI id may be available as event.pi_id or event.pi depending on your event model
    pi = getattr(event, "pi_id", None)
    if pi is None:
        pi = getattr(event, "pi", None)
    pi_str = str(pi) if pi is not None else "unknown"

    device = str(getattr(event, "device", "") or "UNKNOWN")
    device_upper = device.upper()

    # in config its called "type", but older code used "sensor_type" so we check both
    ev_type = getattr(event, "sensor_type", None)
    if ev_type is None:
        ev_type = getattr(event, "type", None)
    ev_type = str(ev_type or "unknown")

    # kind can be passed from the caller (e.g. "sensor" / "actuator"); fallback to event.kind or "unknown"
    kind = (kind or getattr(event, "kind", None) or "unknown").lower()

    measurement_name = f"PI{pi_str}_{device_upper}" 

    point = (
        Point(measurement_name)
        .tag("pi", pi_str)
        .tag("device", device_upper)
        .tag("type", ev_type)
        .tag("kind", kind)
        .tag("simulated", str(bool(getattr(event, "simulated", False))).lower()) # true/false as string for easier querying
    )

    mqtt_topic = getattr(event, "mqtt_topic", None) # we will keep the full topic as a tag for filtering, but not use it for measurement/device since it can be very variable (e.g. "sensors/PI1/DS1" vs "actuators/PI2/BRGB")
    if mqtt_topic:
        point.tag("mqtt_topic", str(mqtt_topic))

    raw_value = getattr(event, "value", None) # this is the raw value which we will try to store as a numeric field; if it's not a number, we will store it as a string in the "message" field instead
    try:
        point.field("value", float(raw_value))
    except (ValueError, TypeError):
        point.field("message", "" if raw_value is None else str(raw_value))

    ts = getattr(event, "timestamp", None)
    if ts is not None:
        point.time(int(float(ts) * 1e9))  # seconds -> nanoseconds

    try:
        write_api.write(bucket=bucket, record=point)
    except Exception as e:
        print(f"[INFLUX] Write rejected: measurement={measurement_name}, device={device_upper}, err={e}")