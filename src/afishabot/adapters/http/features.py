from typing import cast

from fastapi import APIRouter, Request
from pydantic import BaseModel

from afishabot.core.config import Settings

router = APIRouter(tags=["platform"])


class FeatureManifest(BaseModel):
    navigation_v2: bool
    notifications_v2: bool
    safety_cases: bool
    attendance: bool
    private_event_feedback: bool
    reputation_profiles: bool


@router.get("/features", response_model=FeatureManifest)
async def features(request: Request) -> FeatureManifest:
    """Expose only safe rollout switches; every mutation still checks its flag server-side."""
    settings = cast(Settings, request.app.state.settings)
    return FeatureManifest(
        navigation_v2=settings.feature_navigation_v2,
        notifications_v2=settings.feature_notifications_v2,
        safety_cases=settings.feature_safety_cases,
        attendance=settings.feature_attendance,
        private_event_feedback=settings.feature_private_event_feedback,
        reputation_profiles=settings.feature_reputation_profiles,
    )
