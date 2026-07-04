"""Agent performance metrics API endpoints."""

from datetime import datetime
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.schemas.agent_performance import (
    AgentPerformanceAnalyticsResponse,
    AgentPerformanceRequest,
    AgentPerformanceResponse,
)
from app.services.analytics.agent_performance_service import AgentPerformanceService

router = APIRouter(prefix="/agent-performance", tags=["agent-performance"])


@router.post(
    "/metrics",
    response_model=AgentPerformanceResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Record agent performance metrics",
)
async def record_agent_performance_metrics(
    body: AgentPerformanceRequest,
    db: AsyncSession = Depends(get_db),
) -> AgentPerformanceResponse:
    """
    Record agent performance metrics for a conversation.

    This endpoint:
    - Tracks per-agent metrics (tickets closed, AHT, CSAT)
    - Calculates agent utilization
    - Records escalation types
    - Tracks AI vs agent handling

    Args:
        body: Agent performance metrics request
        db: Database session

    Returns:
        Agent performance metrics response
    """
    try:
        # Initialize service
        service = AgentPerformanceService(db)

        # Record metrics
        metrics = await service.record_metrics(
            conversation_id=body.conversation_id,
            agent_id=body.agent_id,
            tickets_closed=body.tickets_closed,
            average_handle_time_seconds=body.average_handle_time_seconds,
            csat_score=body.csat_score,
            csat_count=body.csat_count,
            active_time_seconds=body.active_time_seconds,
            total_time_seconds=body.total_time_seconds,
            agent_escalated=body.agent_escalated,
            auto_escalated=body.auto_escalated,
            escalation_reason=body.escalation_reason,
            ai_handled=body.ai_handled,
            handoff_to_agent=body.handoff_to_agent,
            ai_vs_agent=body.ai_vs_agent,
            channel=body.channel,
            language=body.language,
            period_start=body.period_start,
            period_end=body.period_end,
        )

        return AgentPerformanceResponse(
            metrics_id=metrics.id,
            utilization_rate=metrics.utilization_rate,
            success=True,
            message="Agent performance metrics recorded successfully",
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to record agent performance metrics: {str(e)}",
        )


@router.get(
    "/analytics",
    response_model=AgentPerformanceAnalyticsResponse,
    status_code=status.HTTP_200_OK,
    summary="Get agent performance analytics",
)
async def get_agent_performance_analytics(
    start_date: Optional[datetime] = Query(None, description="Start date (default: 30 days ago)"),
    end_date: Optional[datetime] = Query(None, description="End date (default: now)"),
    db: AsyncSession = Depends(get_db),
) -> AgentPerformanceAnalyticsResponse:
    """
    Get complete agent performance analytics.

    This endpoint:
    - Returns per-agent metrics (tickets closed, AHT, CSAT)
    - Agent utilization rates
    - Escalation ratio (agent-escalated vs auto-escalated)
    - AI vs agent performance comparison
    - Weekly agent performance reports

    Args:
        start_date: Start date (default: 30 days ago)
        end_date: End date (default: now)
        db: Database session

    Returns:
        Complete agent performance analytics
    """
    try:
        # Initialize service
        service = AgentPerformanceService(db)

        # Get analytics
        analytics = await service.get_analytics(
            start_date=start_date,
            end_date=end_date,
        )

        return analytics

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get agent performance analytics: {str(e)}",
        )
