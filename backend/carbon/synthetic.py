"""
Synthetic Carbon Data Provider (Development & Testing Fixture).

Explicitly labeled as SYNTHETIC.
Provides deterministic, mathematically formulated diurnal carbon traces
with realistic slot-specific forecast uncertainties and realized values
to enable offline testing and algorithm development in the absence of Member 1's live provider.
"""

from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone
from typing import List, Optional

from backend.carbon.interface import CarbonDataProvider, CarbonForecastPoint, CarbonGrid


class SyntheticCarbonDataProvider(CarbonDataProvider):
    """
    Generates synthetic grid carbon intensity data using diurnal sinusoidal profiles
    and calibrated slot-specific uncertainty patterns.

    DO NOT USE AS LIVE GRID DATA. Strictly for development, testing, and simulation.
    """

    def __init__(
        self,
        base_intensity: float = 250.0,
        diurnal_amplitude: float = 80.0,
        noise_level: float = 15.0,
        uncertainty_base: float = 20.0,
        uncertainty_growth_rate: float = 1.5,
    ) -> None:
        """
        :param base_intensity: Mean grid carbon intensity in gCO2eq/kWh.
        :param diurnal_amplitude: Peak-to-trough diurnal swing amplitude.
        :param noise_level: Amplitude of realized variation vs forecast.
        :param uncertainty_base: Baseline slot-specific forecast uncertainty (std dev).
        :param uncertainty_growth_rate: Additional uncertainty per 12-hour lead time.
        """
        self.base_intensity = base_intensity
        self.diurnal_amplitude = diurnal_amplitude
        self.noise_level = noise_level
        self.uncertainty_base = uncertainty_base
        self.uncertainty_growth_rate = uncertainty_growth_rate

    def get_carbon_grid(
        self,
        start_time: datetime,
        end_time: datetime,
        time_step_minutes: int = 60,
    ) -> CarbonGrid:
        if start_time >= end_time:
            raise ValueError("start_time must be strictly earlier than end_time.")

        start_utc = start_time if start_time.tzinfo else start_time.replace(tzinfo=timezone.utc)
        end_utc = end_time if end_time.tzinfo else end_time.replace(tzinfo=timezone.utc)

        points: List[CarbonForecastPoint] = []
        step = timedelta(minutes=time_step_minutes)
        current = start_utc
        slot_index = 0

        while current <= end_utc:
            # Solar/diurnal cycle: Peak at ~09:00 and 19:00, trough at 13:00 (solar) and 03:00 (night)
            hour_of_day = current.hour + current.minute / 60.0
            diurnal_factor = math.sin((hour_of_day - 9) * 2 * math.pi / 24.0)

            # Secondary 12-hour harmonic (morning + evening peak)
            harmonic = 0.3 * math.sin((hour_of_day - 6) * 4 * math.pi / 24.0)

            predicted = max(
                10.0,
                self.base_intensity + self.diurnal_amplitude * (diurnal_factor + harmonic)
            )

            # Slot-specific uncertainty: increases with forecast horizon and during rapid transition hours
            transition_penalty = 10.0 * abs(math.cos(hour_of_day * 2 * math.pi / 24.0))
            horizon_growth = self.uncertainty_growth_rate * (slot_index / 12.0)
            slot_uncertainty = self.uncertainty_base + transition_penalty + horizon_growth

            # Realized intensity: simulated ground truth observation
            # Deterministic pseudo-random variation based on sine hash
            realized_noise = self.noise_level * math.sin(slot_index * 1.7 + hour_of_day * 0.5)
            realized = max(5.0, predicted + realized_noise)

            ci_half_width = 1.96 * slot_uncertainty
            lower_ci = max(0.0, predicted - ci_half_width)
            upper_ci = predicted + ci_half_width

            points.append(
                CarbonForecastPoint(
                    timestamp=current,
                    predicted_carbon_intensity=round(predicted, 2),
                    slot_specific_uncertainty=round(slot_uncertainty, 2),
                    realized_carbon_intensity=round(realized, 2),
                    lower_bound_ci=round(lower_ci, 2),
                    upper_bound_ci=round(upper_ci, 2),
                    provenance="SYNTHETIC",
                    metadata={
                        "diurnal_swing": round(self.diurnal_amplitude, 1),
                        "slot_index": slot_index,
                        "lead_time_hours": slot_index * (time_step_minutes / 60.0),
                    },
                )
            )
            current += step
            slot_index += 1

        return CarbonGrid(points, time_step_minutes=time_step_minutes)


def create_mock_carbon_grid(
    start_time: datetime,
    values: List[float],
    uncertainties: Optional[List[float]] = None,
    realized_values: Optional[List[float]] = None,
    time_step_minutes: int = 60,
) -> CarbonGrid:
    """
    Convenience factory to create an exact deterministic grid for unit tests.
    """
    start_utc = start_time if start_time.tzinfo else start_time.replace(tzinfo=timezone.utc)
    step = timedelta(minutes=time_step_minutes)
    points = []
    for i, val in enumerate(values):
        ts = start_utc + i * step
        unc = uncertainties[i] if uncertainties else 10.0
        realized = realized_values[i] if realized_values else val
        points.append(
            CarbonForecastPoint(
                timestamp=ts,
                predicted_carbon_intensity=val,
                slot_specific_uncertainty=unc,
                realized_carbon_intensity=realized,
                lower_bound_ci=max(0.0, val - 1.96 * unc),
                upper_bound_ci=val + 1.96 * unc,
                provenance="SYNTHETIC",
                metadata={"test_index": i},
            )
        )
    return CarbonGrid(points, time_step_minutes=time_step_minutes)
