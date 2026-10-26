"""
Pydantic Data Schemas for Carbonova Carbon Intensity Forecasting.

Defines data contracts for:
  - CarbonIntensitySlot: Individual half-hour forecast interval with conformal bounds.
  - CarbonForecastResponse: Complete serializable forecast payload for scheduler integration.
  - CarbonObservation: Input schema for historical carbon intensity readings.
"""

from datetime import datetime, timezone
from typing import List, Optional
from pydantic import BaseModel, Field, field_validator, model_validator, ConfigDict


class CarbonObservation(BaseModel):
    """Input observation representing a finalized half-hour carbon intensity outturn."""
    model_config = ConfigDict(extra="ignore")

    timestamp_utc: datetime = Field(
        ...,
        description="Observation timestamp in UTC (end or settlement interval)."
    )
    carbon_intensity_gco2_per_kwh: float = Field(
        ...,
        ge=0.0,
        description="Actual measured carbon intensity in gCO2/kWh (must be non-negative)."
    )

    @field_validator("timestamp_utc")
    @classmethod
    def ensure_utc(cls, v: datetime) -> datetime:
        if v.tzinfo is None:
            return v.replace(tzinfo=timezone.utc)
        return v.astimezone(timezone.utc)


class CarbonIntensitySlot(BaseModel):
    """
    Individual half-hour forecast interval with nominal 90% conformal prediction bounds.
    """
    model_config = ConfigDict(extra="forbid")

    timestamp_utc: datetime = Field(
        ...,
        description="Target half-hour forecast interval timestamp in UTC."
    )
    predicted_intensity_gco2_per_kwh: float = Field(
        ...,
        ge=0.0,
        description="Predicted carbon intensity in gCO2/kWh (non-negative)."
    )
    lower_90_gco2_per_kwh: float = Field(
        ...,
        ge=0.0,
        description="Lower bound of the nominal 90% prediction interval in gCO2/kWh."
    )
    upper_90_gco2_per_kwh: float = Field(
        ...,
        ge=0.0,
        description="Upper bound of the nominal 90% prediction interval in gCO2/kWh."
    )
    uncertainty_width_gco2_per_kwh: float = Field(
        ...,
        ge=0.0,
        description="Full width of the nominal 90% prediction interval (upper - lower)."
    )
    model_name: str = Field(
        default="RandomForestRegressor_Conformal",
        description="Identifier of the model used to produce the forecast."
    )
    forecast_horizon: str = Field(
        default="next_half_hour",
        description="Forecasting horizon label (e.g. 'next_half_hour')."
    )

    @field_validator("timestamp_utc")
    @classmethod
    def ensure_utc(cls, v: datetime) -> datetime:
        if v.tzinfo is None:
            return v.replace(tzinfo=timezone.utc)
        return v.astimezone(timezone.utc)

    @model_validator(mode="after")
    def validate_bounds_integrity(self) -> "CarbonIntensitySlot":
        if self.lower_90_gco2_per_kwh > self.upper_90_gco2_per_kwh:
            raise ValueError(
                f"Invalid bounds: lower_90_gco2_per_kwh ({self.lower_90_gco2_per_kwh}) "
                f"exceeds upper_90_gco2_per_kwh ({self.upper_90_gco2_per_kwh})."
            )
        computed_width = round(self.upper_90_gco2_per_kwh - self.lower_90_gco2_per_kwh, 4)
        if abs(self.uncertainty_width_gco2_per_kwh - computed_width) > 1e-3:
            raise ValueError(
                f"Uncertainty width mismatch: uncertainty_width_gco2_per_kwh ({self.uncertainty_width_gco2_per_kwh}) "
                f"does not match upper - lower ({computed_width})."
            )
        return self


class CarbonForecastResponse(BaseModel):
    """
    Complete forecast response payload designed for scheduler integration and JSON serialization.
    """
    model_config = ConfigDict(extra="forbid")

    generated_at_utc: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Timestamp when this forecast response was generated in UTC."
    )
    model_name: str = Field(
        default="RandomForestRegressor_Conformal",
        description="Name of the predictive model."
    )
    model_version: str = Field(
        default="1.0.0",
        description="Semantic version of the deployed model."
    )
    data_status: str = Field(
        default="live",
        description="Operational status of the underlying data ('live', 'historical_backtest', 'fallback_persistence')."
    )
    nominal_interval_label: str = Field(
        default="Nominal 90% Prediction Interval",
        description="Label indicating the nominal statistical coverage level."
    )
    calibrated_quantile_q_hat_gco2_per_kwh: float = Field(
        ...,
        ge=0.0,
        description="Calibrated conformal quantile cutoff half-width in gCO2/kWh."
    )
    slots: List[CarbonIntensitySlot] = Field(
        ...,
        description="List of forecasted half-hour slots."
    )
    disclaimer: str = Field(
        default=(
            "Nominal 90% prediction intervals calibrated via split conformal prediction on "
            "historical grid observations. Intervals provide empirical coverage under "
            "exchangeable conditions and do not guarantee future performance under "
            "non-stationary grid regime shifts."
        ),
        description="Transparency statement on statistical assumptions and non-stationary grid limits."
    )

    @field_validator("generated_at_utc")
    @classmethod
    def ensure_utc(cls, v: datetime) -> datetime:
        if v.tzinfo is None:
            return v.replace(tzinfo=timezone.utc)
        return v.astimezone(timezone.utc)
