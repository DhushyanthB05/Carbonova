"""
Health Check Router.
"""

from fastapi import APIRouter

router = APIRouter(prefix="/api", tags=["Health"])


@router.get("/health")
def get_health():
    return {
        "status": "ok",
        "service": "carbonova-backend",
        "engine_version": "0.1.0",
        "member_responsibility": "Member 2 - Core Scheduling Engine",
    }
