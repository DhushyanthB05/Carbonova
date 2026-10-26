"""
Carbonova Backend Application.

FastAPI main application exposing scheduling, carbon forecast, and workload management endpoints.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.app.routers import carbon, health, jobs, schedule

app = FastAPI(
    title="Carbonova Scheduling Engine API",
    description="Explainable, Uncertainty-Aware Carbon Scheduling Platform for Flexible AI Workloads.",
    version="0.1.0",
)

# Enable CORS for frontend development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount API routers
app.include_router(health.router)
app.include_router(carbon.router)
app.include_router(jobs.router)
app.include_router(schedule.router)


@app.get("/")
def root():
    return {
        "project": "Carbonova",
        "tagline": "Smarter AI. Cleaner Computing.",
        "docs_url": "/docs",
        "health_url": "/api/health",
    }
