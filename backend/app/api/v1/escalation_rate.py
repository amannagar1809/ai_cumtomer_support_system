"""Escalation rate metrics API endpoints."""

from datetime import datetime
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.schemas.escalation_rate import (
    EscalationRateAnalyticsResponse,
    EscalationRateRequest,
    EscalationRateResponse,
)
from app.services.analytics.escalation_rate_service import EscalationRateService

router = APIRouter(prefix="/escalation-rate", tags=["escalation-rate"])


@router.post(
    "/metrics",
    response_model=EscalationRateResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Record escalation rate metrics",
)
async def record_escalation_rate_metrics(
    body: EscalationRateRequest,
    db: AsyncSession = Depends(get_db),
) -> EscalationRateResponse:
    """
    Record escalation rate metrics for a conversation.

    This endpoint:
    - Tracks total vs escalated conversations
    - Records escalation reason
    - Stores conversation context
    - Tracks sentiment and confidence scores

    Args:
        body: Escalation rate metrics request
        db: Database session

    Returns:
        Escalation rate metrics response
    """
    try:
        # Initialize service
        service = EscalationRateService(db)

        # Record metrics
        metrics = await service.record_metrics(
            conversation_id=body.conversation_id,
            user_id=body.user_id,
            is_escalated=body.is_escalated,
            escalation_reason=body.escalation_reason,
            escalated_to=body.escalated_to,
            escalation_timestamp=body.escalation_timestamp,
            total_messages=body.total_messages,
            ai_responses=body.ai_responses,
            user_messages=body.user_messages,
            channel=body.channel,
            language=body.language,
            sentiment_score=body.sentiment_score,
            confidence_score=body.confidence_score,
        )

        return EscalationRateResponse(
            metrics_id=metrics.id,
            is_escalated=metrics.is_escalated == 1,
            escalation_rate_threshold=metrics.escalation_rate_threshold,
            threshold_violation=metrics.threshold_violation == 1,
            success=True,
            message="Escalation rate metrics recorded successfully",
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to record escalation rate metrics: {str(e)}",
        )


@router.get(
    "/analytics",
    response_model=EscalationRateAnalyticsResponse,
    status_code=status.HTTP_200_OK,
    summary="Get escalation rate analytics",
)
async def get_escalation_rate_analytics(
    start_date: Optional[datetime] = Query(None, description="Start date (default: 30 days ago)"),
    end_date: Optional[datetime] = Query(None, description="End date (default: now)"),
    db: AsyncSession = Depends(get_db),
) -> EscalationRateAnalyticsResponse:
    """
    Get complete escalation rate analytics.

    This endpoint:
    - Returns daily, weekly, monthly summaries
    - Breakdown by escalation reason
    - Trend over time (goal: decreasing)
    - Active alerts for high rates

    Args:
        start_date: Start date (default: 30 days ago)
        end_date: End date (default: now)
        db: Database session

    Returns:
        Complete escalation rate analytics
    """
    try:
        # Initialize service
        service = EscalationRateService(db)

        # Get analytics
        analytics = await service.get_analytics(
            start_date=start_date,
            end_date=end_date,
        )

        return analytics

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get escalation rate analytics: {str(e)}",
        )
