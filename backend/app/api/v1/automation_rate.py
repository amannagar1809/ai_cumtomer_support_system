"""Automation rate metrics API endpoints."""

from datetime import datetime
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.schemas.automation_rate import (
    AutomationRateAnalyticsResponse,
    AutomationRateRequest,
    AutomationRateResponse,
)
from app.services.analytics.automation_rate_service import AutomationRateService

router = APIRouter(prefix="/automation-rate", tags=["automation-rate"])


@router.post(
    "/metrics",
    response_model=AutomationRateResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Record automation rate metrics",
)
async def record_automation_rate_metrics(
    body: AutomationRateRequest,
    db: AsyncSession = Depends(get_db),
) -> AutomationRateResponse:
    """
    Record automation rate metrics for a conversation.

    This endpoint:
    - Tracks automation type (fully_automated, hybrid, human_only)
    - Records conversation metrics
    - Calculates cost savings
    - Stores intent category for target tracking

    Args:
        body: Automation rate metrics request
        db: Database session

    Returns:
        Automation rate metrics response
    """
    try:
        # Initialize service
        service = AutomationRateService(db)

        # Record metrics
        metrics = await service.record_metrics(
            conversation_id=body.conversation_id,
            user_id=body.user_id,
            automation_type=body.automation_type,
            total_messages=body.total_messages,
            ai_messages=body.ai_messages,
            human_messages=body.human_messages,
            conversation_duration_seconds=body.conversation_duration_seconds,
            intent_category=body.intent_category,
            predicted_intent=body.predicted_intent,
            estimated_human_time_minutes=body.estimated_human_time_minutes,
            actual_human_time_minutes=body.actual_human_time_minutes,
            agent_cost_per_hour=body.agent_cost_per_hour,
            channel=body.channel,
            language=body.language,
        )

        return AutomationRateResponse(
            metrics_id=metrics.id,
            automation_type=metrics.automation_type,
            cost_savings=metrics.cost_savings,
            success=True,
            message="Automation rate metrics recorded successfully",
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to record automation rate metrics: {str(e)}",
        )


@router.get(
    "/analytics",
    response_model=AutomationRateAnalyticsResponse,
    status_code=status.HTTP_200_OK,
    summary="Get automation rate analytics",
)
async def get_automation_rate_analytics(
    start_date: Optional[datetime] = Query(None, description="Start date (default: 30 days ago)"),
    end_date: Optional[datetime] = Query(None, description="End date (default: now)"),
    db: AsyncSession = Depends(get_db),
) -> AutomationRateAnalyticsResponse:
    """
    Get complete automation rate analytics.

    This endpoint:
    - Returns monthly automation rate summary
    - Breakdown by automation type
    - Cost savings metrics
    - Automation targets by intent category

    Args:
        start_date: Start date (default: 30 days ago)
        end_date: End date (default: now)
        db: Database session

    Returns:
        Complete automation rate analytics
    """
    try:
        # Initialize service
        service = AutomationRateService(db)

        # Get analytics
        analytics = await service.get_analytics(
            start_date=start_date,
            end_date=end_date,
        )

        return analytics

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get automation rate analytics: {str(e)}",
        )
