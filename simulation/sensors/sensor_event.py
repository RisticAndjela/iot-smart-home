from dataclasses import dataclass
from typing import Any, Optional


@dataclass
class SensorEvent:
    """
    Unified event model for sensors, actuators and system events.

    - kind: "sensor" | "actuator" | "system"
    - type: e.g. "door", "ultrasonic", "motion", "buzzer", "light", "rgb", "display"
    - sensor_type: legacy alias for type (kept for backward compatibility)
    """
    pi_id: str                   # e.g. "1", "2", "3"
    device: str                  # e.g. "DS1", "DUS1", "BRGB"
    value: Any                   # can be float/int/str depending on device
    simulated: bool
    timestamp: float

    kind: str = "sensor"         # default to sensor
    type: str = "unknown"        # preferred field name
    sensor_type: Optional[str] = None  # existing because in code we have both "type" and "sensor_type" used in different places; we want to be robust to both, but prefer "type" as the canonical field name

    def __post_init__(self):
        self.pi_id = str(self.pi_id)
        self.device = str(self.device)

        if self.sensor_type and (self.type == "unknown" or not self.type): # somewhere we used "type" and somewhere "sensor_type", we want to be robust to both, but prefer "type" as the canonical field name
            self.type = str(self.sensor_type)

        if self.sensor_type is None:
            self.sensor_type = self.type

        self.kind = str(self.kind or "sensor").lower()
        if self.kind not in ("sensor", "actuator", "system"):
            self.kind = "sensor"