"""
Carbon Forecast and Data Router.
"""

from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, Query

from backend.app.storage import store
from backend.carbon.interface import CarbonForecastPoint

router = APIRouter(prefix="/api", tags=["Carbon"])


@router.get("/carbon", response_model=List[CarbonForecastPoint])
def get_carbon_data(
    start_time: Optional[datetime] = Query(None, description="Start timestamp (UTC)"),
    end_time: Optional[datetime] = Query(None, description="End timestamp (UTC)"),
    time_step_minutes: int = Query(60, ge=1, description="Grid resolution in minutes"),
):
    grid = store.get_default_carbon_grid(start_time, end_time, time_step_minutes)
    return grid.points
