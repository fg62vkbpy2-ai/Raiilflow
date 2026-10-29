"""RailFlow demo engine: simulated railway conflict detection only.

This is an educational prototype. It is NOT a railway signalling or safety system.
All distances are metres, speeds m/s internally, and timestamps are simulated.
"""
from __future__ import annotations
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import Optional
import math


@dataclass
class Train:
    train_id: str
    name: str
    position_m: float
    speed_mps: float
    status: str = "RUNNING"

    @property
    def speed_kmh(self) -> float:
        return self.speed_mps * 3.6


@dataclass
class Detection:
    severity: str
    code: str
    message: str
    gap_m: float
    stopping_distance_m: float
    reaction_distance_m: float
    required_distance_m: float
    time_to_collision_s: Optional[float]
    timestamp: str


class RailFlowEngine:
    """Small deterministic engine for a single-track, same-direction demo."""

    def __init__(
        self,
        braking_deceleration_mps2: float = 0.8,
        reaction_time_s: float = 3.0,
        safety_margin_m: float = 500.0,
        amber_factor: float = 1.5,
    ):
        if braking_deceleration_mps2 <= 0 or reaction_time_s < 0 or safety_margin_m < 0:
            raise ValueError("Braking deceleration must be positive; times/margins non-negative.")
        self.braking_deceleration_mps2 = braking_deceleration_mps2
        self.reaction_time_s = reaction_time_s
        self.safety_margin_m = safety_margin_m
        self.amber_factor = amber_factor

    def stopping_distance(self, speed_mps: float) -> float:
        """Kinematic stopping distance v²/(2a); excludes reaction distance."""
        return max(0.0, speed_mps) ** 2 / (2 * self.braking_deceleration_mps2)

    def detect(self, following: Train, stopped_ahead: Train, sim_time_s: float = 0.0) -> Detection:
        gap = max(0.0, stopped_ahead.position_m - following.position_m)
        v = max(0.0, following.speed_mps)
        brake = self.stopping_distance(v)
        reaction = v * self.reaction_time_s
        required = brake + reaction + self.safety_margin_m
        ttc = gap / v if v > 0 else None

        if gap <= 0:
            severity, code = "RED", "COLLISION"
            message = "La separación simulada ha llegado a cero."
        elif v > 0 and gap <= required:
            severity, code = "RED", "CONFLICT_IMMINENT"
            message = "La distancia disponible es igual o inferior a la distancia requerida de parada."
        elif v > 0 and gap <= required * self.amber_factor:
            severity, code = "AMBER", "CONFLICT_WARNING"
            message = "La separación entra en el margen preventivo; requiere atención inmediata."
        else:
            severity, code = "GREEN", "NORMAL"
            message = "Sin conflicto detectado con los parámetros actuales."

        # Simulated timestamp is labelled clearly; it is not a wall-clock timestamp.
        stamp = f"T+{sim_time_s:06.1f}s"
        return Detection(
            severity=severity,
            code=code,
            message=message,
            gap_m=gap,
            stopping_distance_m=brake,
            reaction_distance_m=reaction,
            required_distance_m=required,
            time_to_collision_s=ttc,
            timestamp=stamp,
        )

    def step(self, following: Train, stopped_ahead: Train, dt_s: float = 1.0,
             apply_demo_brake: bool = False) -> tuple[Train, Detection]:
        """Advance simulation one step. Optional braking is demo-only, never real control."""
        if dt_s <= 0:
            raise ValueError("dt_s must be positive")
        detection = self.detect(following, stopped_ahead)
        speed = following.speed_mps
        if apply_demo_brake and detection.severity == "RED":
            speed = max(0.0, speed - self.braking_deceleration_mps2 * dt_s)
        new_position = following.position_m + speed * dt_s
        updated = Train(
            train_id=following.train_id,
            name=following.name,
            position_m=new_position,
            speed_mps=speed,
            status="SIMULATED_BRAKING" if apply_demo_brake and detection.severity == "RED" else following.status,
        )
        return updated, detection


def scenario_defaults() -> tuple[Train, Train]:
    """Return following train 2.5 km behind a stopped train, travelling at 200 km/h."""
    return (
        Train("RF-102", "Tren aproximándose", position_m=15_000.0, speed_mps=200 / 3.6),
        Train("RF-101", "Tren detenido", position_m=17_500.0, speed_mps=0.0, status="STOPPED"),
    )


def to_event_dict(detection: Detection, following: Train, stopped_ahead: Train) -> dict:
    return {
        "timestamp_simulated": detection.timestamp,
        "severity": detection.severity,
        "event_code": detection.code,
        "message": detection.message,
        "following_train": following.train_id,
        "stopped_train": stopped_ahead.train_id,
        "following_position_m": round(following.position_m, 2),
        "stopped_position_m": round(stopped_ahead.position_m, 2),
        "speed_kmh": round(following.speed_kmh, 2),
        "gap_m": round(detection.gap_m, 2),
        "stopping_distance_m": round(detection.stopping_distance_m, 2),
        "reaction_distance_m": round(detection.reaction_distance_m, 2),
        "required_distance_m": round(detection.required_distance_m, 2),
        "time_to_collision_s": None if detection.time_to_collision_s is None else round(detection.time_to_collision_s, 2),
        "demo_only": True,
    }
