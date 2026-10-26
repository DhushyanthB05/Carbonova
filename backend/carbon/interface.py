"""
Carbon Data & Forecast Contract Interface.

Defines the formal typed interface for carbon intensity data and forecasts
provided by Member 1 (Carbon Forecast Engine).

Includes data models for forecast points, uncertainty bounds, time series grids,
and the abstract base class `CarbonDataProvider`.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Sequence
from pydantic import BaseModel, Field, field_validator, model_validator


class CarbonForecastPoint(BaseModel):
    """
    Represents carbon intensity and uncertainty for a single discrete time slot.

    Units:
      - predicted_carbon_intensity: gCO2eq / kWh
      - slot_specific_uncertainty: gCO2eq / kWh (standard deviation or 1-sigma spread)
      - realized_carbon_intensity: gCO2eq / kWh (ground truth, populated for evaluation only)
    """

    timestamp: datetime = Field(
        ...,
        description="Slot starting timestamp (half-open [timestamp, timestamp + step)), timezone-aware UTC."
    )
    predicted_carbon_intensity: float = Field(
        ...,
        ge=0.0,
        description="Forecasted average marginal/average grid carbon intensity in gCO2eq/kWh."
    )
    slot_specific_uncertainty: float = Field(
        ...,
        ge=0.0,
        description="Estimated slot-specific forecast uncertainty (std dev or interval width) in gCO2eq/kWh."
    )
    realized_carbon_intensity: Optional[float] = Field(
        default=None,
        ge=0.0,
        description="Observed ground truth carbon intensity (for post-hoc evaluation and oracle only)."
    )
    lower_bound_ci: Optional[float] = Field(
        default=None,
        ge=0.0,
        description="Lower bound of forecast confidence interval (e.g., 90% or 95% interval)."
    )
    upper_bound_ci: Optional[float] = Field(
        default=None,
        ge=0.0,
        description="Upper bound of forecast confidence interval."
    )
    provenance: str = Field(
        default="SYNTHETIC",
        description="Source of the data point, e.g. 'SYNTHETIC', 'ELECTRICITY_MAPS', 'NATIONAL_GRID_ESO'."
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional slot metadata, such as renewable fraction or model version."
    )

    @field_validator("timestamp")
    @classmethod
    def ensure_utc(cls, v: datetime) -> datetime:
        if v.tzinfo is None:
            # Default naive to UTC
            return v.replace(tzinfo=timezone.utc)
        return v.astimezone(timezone.utc)

    @model_validator(mode="after")
    def validate_bounds(self) -> CarbonForecastPoint:
        if self.lower_bound_ci is not None and self.upper_bound_ci is not None:
            if self.lower_bound_ci > self.upper_bound_ci:
                raise ValueError("lower_bound_ci cannot exceed upper_bound_ci")
        return self


class CarbonGrid:
    """
    In-memory indexed lookup of carbon forecast points on a regular time grid.
    Guarantees strict UTC ordering, no duplicates, and fast slot-interval lookups.
    """

    def __init__(self, points: Sequence[CarbonForecastPoint], time_step_minutes: int = 60) -> None:
        if not points:
            raise ValueError("CarbonGrid requires at least one CarbonForecastPoint.")
        if time_step_minutes <= 0:
            raise ValueError("time_step_minutes must be positive.")

        # Sort and deduplicate / check duplicates
        sorted_points = sorted(points, key=lambda p: p.timestamp)
        seen_timestamps = set()
        cleaned_points: List[CarbonForecastPoint] = []
        for p in sorted_points:
            ts = p.timestamp
            if ts in seen_timestamps:
                raise ValueError(f"Duplicate timestamp detected in CarbonGrid: {ts.isoformat()}")
            seen_timestamps.add(ts)
            cleaned_points.append(p)

        self._points = cleaned_points
        self._time_step_minutes = time_step_minutes
        self._lookup: Dict[datetime, CarbonForecastPoint] = {p.timestamp: p for p in self._points}
        self._timestamps = [p.timestamp for p in self._points]

    @property
    def points(self) -> List[CarbonForecastPoint]:
        return list(self._points)

    @property
    def time_step_minutes(self) -> int:
        return self._time_step_minutes

    @property
    def start_time(self) -> datetime:
        return self._timestamps[0]

    @property
    def end_time(self) -> datetime:
        return self._timestamps[-1]

    def has_slot(self, timestamp: datetime) -> bool:
        ts_utc = timestamp if timestamp.tzinfo else timestamp.replace(tzinfo=timezone.utc)
        return ts_utc in self._lookup

    def get_slot(self, timestamp: datetime) -> Optional[CarbonForecastPoint]:
        ts_utc = timestamp if timestamp.tzinfo else timestamp.replace(tzinfo=timezone.utc)
        return self._lookup.get(ts_utc)

    def get_interval_points(self, start: datetime, duration_slots: int) -> List[CarbonForecastPoint]:
        """
        Retrieves consecutive slots starting at `start` for `duration_slots`.
        Returns empty list if any slot in the span is missing.
        """
        from datetime import timedelta
        ts_utc = start if start.tzinfo else start.replace(tzinfo=timezone.utc)
        result: List[CarbonForecastPoint] = []
        step = timedelta(minutes=self._time_step_minutes)
        current = ts_utc
        for _ in range(duration_slots):
            pt = self._lookup.get(current)
            if pt is None:
                return []
            result.append(pt)
            current += step
        return result


class CarbonDataProvider(ABC):
    """
    Abstract Base Class for carbon data ingestion and forecasting.
    Member 1 will implement this interface with live grid providers (e.g. ElectricityMaps, WattTime).
    """

    @abstractmethod
    def get_carbon_grid(
        self,
        start_time: datetime,
        end_time: datetime,
        time_step_minutes: int = 60,
    ) -> CarbonGrid:
        """
        Fetch or compute the carbon forecast grid covering [start_time, end_time].
        """
        pass
