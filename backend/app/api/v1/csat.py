"""CSAT (Customer Satisfaction) API endpoints."""

from datetime import datetime
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.schemas.csat import (
    CSATAnalyticsResponse,
    CSATSurveyRequest,
    CSATSurveyResponse,
)
from app.services.analytics.csat_service import CSATService

router = APIRouter(prefix="/csat", tags=["csat"])


@router.post(
    "/survey",
    response_model=CSATSurveyResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Submit CSAT survey",
)
async def submit_csat_survey(
    body: CSATSurveyRequest,
    db: AsyncSession = Depends(get_db),
) -> CSATSurveyResponse:
    """
    Submit a CSAT survey response.

    This endpoint:
    - Accepts CSAT survey with score (1-5)
    - Stores survey response in database
    - Records channel, language, agent type
    - Stores optional text feedback

    Args:
        body: CSAT survey request
        db: Database session

    Returns:
        CSAT survey response
    """
    try:
        # Initialize CSAT service
        csat_service = CSATService(db)

        # Submit survey
        survey = await csat_service.submit_survey(
            conversation_id=body.conversation_id,
            user_id=body.user_id,
            score=body.score,
            feedback=body.feedback,
            channel=body.channel,
            language=body.language,
            agent_type=body.agent_type,
            agent_id=body.agent_id,
        )

        return CSATSurveyResponse(
            survey_id=survey.id,
            conversation_id=survey.conversation_id,
            score=survey.score,
            feedback=survey.feedback,
            channel=survey.channel,
            language=survey.language,
            agent_type=survey.agent_type,
            agent_id=survey.agent_id,
            survey_completed_at=survey.survey_completed_at,
            success=True,
            message="CSAT survey submitted successfully",
        )

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to submit CSAT survey: {str(e)}",
        )


@router.get(
    "/analytics",
    response_model=CSATAnalyticsResponse,
    status_code=status.HTTP_200_OK,
    summary="Get CSAT analytics",
)
async def get_csat_analytics(
    start_date: Optional[datetime] = Query(None, description="Start date (default: 30 days ago)"),
    end_date: Optional[datetime] = Query(None, description="End date (default: now)"),
    db: AsyncSession = Depends(get_db),
) -> CSATAnalyticsResponse:
    """
    Get complete CSAT analytics.

    This endpoint:
    - Returns daily, weekly, monthly metrics
    - Breakdown by channel, language, agent type
    - Trend line over time
    - Active alerts for low scores

    Args:
        start_date: Start date (default: 30 days ago)
        end_date: End date (default: now)
        db: Database session

    Returns:
        Complete CSAT analytics
    """
    try:
        # Initialize CSAT service
        csat_service = CSATService(db)

        # Get analytics
        analytics = await csat_service.get_analytics(
            start_date=start_date,
            end_date=end_date,
        )

        return analytics

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get CSAT analytics: {str(e)}",
        )
