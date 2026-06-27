"""Resolution time metrics API endpoints."""

from datetime import datetime
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.schemas.resolution_time import (
    ResolutionTimeAnalyticsResponse,
    ResolutionTimeMetricsRequest,
    ResolutionTimeMetricsResponse,
)
from app.services.analytics.resolution_time_service import ResolutionTimeService

router = APIRouter(prefix="/resolution-time", tags=["resolution-time"])


@router.post(
    "/metrics",
    response_model=ResolutionTimeMetricsResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Record resolution time metrics",
)
async def record_resolution_time_metrics(
    body: ResolutionTimeMetricsRequest,
    db: AsyncSession = Depends(get_db),
) -> ResolutionTimeMetricsResponse:
    """
    Record resolution time metrics for a conversation.

    This endpoint:
    - Tracks conversation start → end timestamps
    - Calculates First Response Time (FRT)
    - Calculates Average Handle Time (AHT)
    - Checks SLA violations
    - Stores metrics with dimensions

    Args:
        body: Resolution time metrics request
        db: Database session

    Returns:
        Resolution time metrics response
    """
    try:
        # Initialize service
        service = ResolutionTimeService(db)

        # Record metrics
        metrics = await service.record_metrics(
            conversation_id=body.conversation_id,
            user_id=body.user_id,
            conversation_started_at=body.conversation_started_at,
            first_message_at=body.first_message_at,
            first_response_at=body.first_response_at,
            conversation_ended_at=body.conversation_ended_at,
            priority_level=body.priority_level,
            channel=body.channel,
            customer_tier=body.customer_tier,
        )

        return ResolutionTimeMetricsResponse(
            metrics_id=metrics.id,
            conversation_id=metrics.conversation_id,
            first_response_time_seconds=metrics.first_response_time_seconds,
            average_handle_time_seconds=metrics.average_handle_time_seconds,
            sla_frt_violation=metrics.sla_frt_violation == 1,
            sla_aht_violation=metrics.sla_aht_violation == 1,
            success=True,
            message="Resolution time metrics recorded successfully",
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to record resolution time metrics: {str(e)}",
        )


@router.get(
    "/analytics",
    response_model=ResolutionTimeAnalyticsResponse,
    status_code=status.HTTP_200_OK,
    summary="Get resolution time analytics",
)
async def get_resolution_time_analytics(
    start_date: Optional[datetime] = Query(None, description="Start date (default: 30 days ago)"),
    end_date: Optional[datetime] = Query(None, description="End date (default: now)"),
    db: AsyncSession = Depends(get_db),
) -> ResolutionTimeAnalyticsResponse:
    """
    Get complete resolution time analytics.

    This endpoint:
    - Returns daily, weekly, monthly summaries
    - Breakdown by priority, channel, customer tier
    - SLA compliance rates
    - Recent SLA violations

    Args:
        start_date: Start date (default: 30 days ago)
        end_date: End date (default: now)
        db: Database session

    Returns:
        Complete resolution time analytics
    """
    try:
        # Initialize service
        service = ResolutionTimeService(db)

        # Get analytics
        analytics = await service.get_analytics(
            start_date=start_date,
            end_date=end_date,
        )

        return analytics

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get resolution time analytics: {str(e)}",
        )
