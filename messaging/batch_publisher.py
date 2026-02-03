import time
import json
import queue
from database.sensor_service import write_event_to_influx
from messaging.event_queue import event_queue

def batch_publisher(mqtt_client, stop_event, batch_size=10, interval=5):
    batch = []
    last_flush = time.time()

    while not stop_event.is_set():
        try:
            event = event_queue.get(timeout=interval)
            batch.append(event)
            write_event_to_influx(event)
        except queue.Empty:
            pass

        now = time.time()

        if batch and (
            len(batch) >= batch_size or
            now - last_flush >= interval
        ):
            for e in batch:
                mqtt_client.publish(
                    topic=f"sensors/{e.pi_id}/{e.device}",
                    payload=json.dumps({
                        "sensor_type": e.sensor_type,
                        "value": e.value,
                        "simulated": e.simulated,
                        "timestamp": e.timestamp
                    })
                )
            batch.clear()
            last_flush = now
