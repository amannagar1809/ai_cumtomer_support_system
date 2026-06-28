"""Intent accuracy metrics API endpoints."""

from datetime import datetime
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.schemas.intent_accuracy import (
    IntentAccuracyAnalyticsResponse,
    IntentAccuracyRecord,
    IntentAccuracyRequest,
    IntentAccuracyResponse,
)
from app.services.analytics.intent_accuracy_service import IntentAccuracyService

router = APIRouter(prefix="/intent-accuracy", tags=["intent-accuracy"])


@router.post(
    "/record",
    response_model=IntentAccuracyResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Record intent accuracy",
)
async def record_intent_accuracy(
    body: IntentAccuracyRequest,
    db: AsyncSession = Depends(get_db),
) -> IntentAccuracyResponse:
    """
    Record intent accuracy (predicted vs actual intent).

    This endpoint:
    - Logs predicted intent vs actual intent
    - Stores confidence scores
    - Tracks for post-conversation review
    - Enables retraining data collection

    Args:
        body: Intent accuracy request
        db: Database session

    Returns:
        Intent accuracy response
    """
    try:
        # Initialize service
        service = IntentAccuracyService(db)

        # Record accuracy
        record = await service.record_accuracy(
            conversation_id=body.conversation_id,
            user_id=body.user_id,
            user_message=body.user_message,
            predicted_intent=body.predicted_intent,
            actual_intent=body.actual_intent,
            predicted_confidence=body.predicted_confidence,
            confidence_distribution=body.confidence_distribution,
            language=body.language,
            model_variant=body.model_variant,
            classification_id=body.classification_id,
            review_notes=body.review_notes,
        )

        return IntentAccuracyResponse(
            record_id=record.id,
            is_correct=record.is_correct == 1,
            success=True,
            message="Intent accuracy recorded successfully",
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to record intent accuracy: {str(e)}",
        )


@router.get(
    "/analytics",
    response_model=IntentAccuracyAnalyticsResponse,
    status_code=status.HTTP_200_OK,
    summary="Get intent accuracy analytics",
)
async def get_intent_accuracy_analytics(
    start_date: Optional[datetime] = Query(None, description="Start date (default: 30 days ago)"),
    end_date: Optional[datetime] = Query(None, description="End date (default: now)"),
    db: AsyncSession = Depends(get_db),
) -> IntentAccuracyAnalyticsResponse:
    """
    Get complete intent accuracy analytics.

    This endpoint:
    - Returns overall accuracy
    - Accuracy per intent class
    - Frequently misclassified queries
    - Confidence score distribution
    - Confusion matrix

    Args:
        start_date: Start date (default: 30 days ago)
        end_date: End date (default: now)
        db: Database session

    Returns:
        Complete intent accuracy analytics
    """
    try:
        # Initialize service
        service = IntentAccuracyService(db)

        # Get analytics
        analytics = await service.get_analytics(
            start_date=start_date,
            end_date=end_date,
        )

        return analytics

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get intent accuracy analytics: {str(e)}",
        )


@router.get(
    "/export-misclassified",
    status_code=status.HTTP_200_OK,
    summary="Export misclassified examples for retraining",
)
async def export_misclassified_examples(
    start_date: Optional[datetime] = Query(None, description="Start date (default: 30 days ago)"),
    end_date: Optional[datetime] = Query(None, description="End date (default: now)"),
    db: AsyncSession = Depends(get_db),
) -> Response:
    """
    Export misclassified examples for retraining.

    This endpoint:
    - Exports misclassified queries as CSV
    - Includes user message, predicted intent, actual intent
    - Includes confidence scores and language
    - Ready for model retraining

    Args:
        start_date: Start date (default: 30 days ago)
        end_date: End date (default: now)
        db: Database session

    Returns:
        CSV file with misclassified examples
    """
    try:
        # Initialize service
        service = IntentAccuracyService(db)

        # Export misclassified examples
        csv_data = await service.export_misclassified_examples(
            start_date=start_date,
            end_date=end_date,
        )

        return Response(
            content=csv_data,
            media_type="text/csv",
            headers={
                "Content-Disposition": "attachment; filename=misclassified_examples.csv"
            },
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to export misclassified examples: {str(e)}",
        )
