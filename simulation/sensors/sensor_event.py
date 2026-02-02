from dataclasses import dataclass

@dataclass
class SensorEvent:
    pi_id: str            # eg. "PI1"
    device: str           # eg. "UDS1"
    sensor_type: str      # "ultrasonic", "pir", "door"
    value: float | int
    simulated: bool
    timestamp: float
