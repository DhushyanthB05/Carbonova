"""
Carbon module for Carbonova.
Provides interfaces and synthetic fixtures for carbon intensity data and forecasts.
"""

from backend.carbon.interface import (
    CarbonDataProvider,
    CarbonForecastPoint,
    CarbonGrid,
)
from backend.carbon.neso_provider import NESORealTraceCarbonDataProvider
from backend.carbon.synthetic import (
    SyntheticCarbonDataProvider,
    create_mock_carbon_grid,
)

__all__ = [
    "CarbonDataProvider",
    "CarbonForecastPoint",
    "CarbonGrid",
    "NESORealTraceCarbonDataProvider",
    "SyntheticCarbonDataProvider",
    "create_mock_carbon_grid",
]
