import json
import time
import queue
from messaging.event_queue import event_queue


def _pi_topic(pi) -> str:
    """
    Normalize PI id for topics:
      "1" -> "pi1", 1 -> "pi1", "PI1" -> "pi1", "pi2" -> "pi2"
    """
    if pi is None:
        return "piunknown"
    s = str(pi).strip().lower()
    if s.startswith("pi"):
        return s
    return f"pi{s}"


def _device_topic(device: str) -> str:
    """Normalize device name for topics (lowercase)."""
    return (device or "unknown").strip().lower()


def _normalize_timestamp(ts) -> float:
    """
    Normalize timestamps to seconds (float).
    Accepts:
      - seconds (float, ~1e9 range)
      - milliseconds (int, ~1e12-1e13 range)
      - nanoseconds (int, ~1e18 range) [rare but possible]
    """
    if ts is None:
        return time.time()

    try:
        t = float(ts)
    except (TypeError, ValueError):
        return time.time()

    if t > 1e17:      # nanoseconds
        return t / 1e9
    if t > 1e14:      # microseconds (just in case)
        return t / 1e6
    if t > 1e11:      # milliseconds
        return t / 1e3
    return t          # seconds


def batch_publisher(mqtt_client, stop_event, batch_size=10, interval=5, write_callback=None):
    """
    publishes events from event_queue to Mosquitto in batches.

    topic convention:
      - sensors/{pi_topic}/{device_topic}   for kind == "sensor"
      - actuators/{pi_topic}/{device_topic} for kind == "actuator"
      - events/{pi_topic}/{device_topic}    for kind == "system" (or unknown)

    payload includes redundant identifiers (pi, device) to make consumers robust even if
    they don't parse the topic.
    """
    batch = []
    last_flush = time.time()

    while not stop_event.is_set():
        try:
            event = event_queue.get(timeout=interval)
            batch.append(event)

            # Write to InfluxDB immediately upon reception (optional)
            if write_callback:
                write_callback(event)

        except queue.Empty:
            pass

        now = time.time()
        if not batch:
            continue

        if len(batch) >= batch_size or (now - last_flush) >= interval:
            n = len(batch)  # capture size BEFORE clearing
            for e in batch:
                pi = getattr(e, "pi_id", None) or getattr(e, "pi", None) or "unknown"
                device = str(getattr(e, "device", "UNKNOWN") or "UNKNOWN")

                # prefer "type", fallback to legacy "sensor_type"
                ev_type = getattr(e, "type", None)
                if ev_type is None:
                    ev_type = getattr(e, "sensor_type", None)
                ev_type = str(ev_type or "unknown")

                kind = str(getattr(e, "kind", None) or "sensor").lower()
                if kind not in ("sensor", "actuator", "system"):
                    kind = "sensor"

                pi_seg = _pi_topic(pi)
                dev_seg = _device_topic(device)

                if kind == "sensor":
                    base = "sensors"
                elif kind == "actuator":
                    base = "actuators"
                else:
                    base = "events"

                topic = f"{base}/{pi_seg}/{dev_seg}"

                payload = {
                    "pi": str(pi),
                    "device": device.upper(),  # canonical form in payload
                    "type": ev_type,
                    "kind": kind,
                    "value": getattr(e, "value", None),
                    "simulated": bool(getattr(e, "simulated", False)),
                    "timestamp": _normalize_timestamp(getattr(e, "timestamp", None)),
                }
                
                payload["sensor_type"] = payload["type"] # somewhere in code we have both "type" and "sensor_type" used in different places, we want to be robust to both, but prefer "type" as the canonical field name

                mqtt_client.publish(topic=topic, payload=json.dumps(payload, ensure_ascii=False))

            batch.clear()
            last_flush = now
            print(f"[MQTT] Published batch of events of size {n}")