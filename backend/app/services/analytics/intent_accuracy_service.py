"""Intent accuracy metrics service."""

import json
import logging
from datetime import datetime, timedelta
from typing import Optional
from uuid import UUID, uuid4

from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.intent_accuracy import IntentAccuracy
from app.schemas.intent_accuracy import (
    ConfusionMatrixCell,
    ConfidenceDistribution,
    IntentAccuracyAnalyticsResponse,
    IntentClassAccuracy,
    MisclassifiedQuery,
)

logger = logging.getLogger(__name__)


class IntentAccuracyService:
    """Service for intent accuracy metrics."""

    def __init__(self, db: AsyncSession):
        """
        Initialize intent accuracy service.

        Args:
            db: Database session
        """
        self.db = db
        self.logger = logger

    async def record_accuracy(
        self,
        conversation_id: UUID,
        user_id: UUID,
        user_message: str,
        predicted_intent: str,
        actual_intent: str,
        predicted_confidence: float,
        confidence_distribution: Optional[dict],
        language: str,
        model_variant: Optional[str],
        classification_id: Optional[str],
        review_notes: Optional[str],
    ) -> IntentAccuracy:
        """
        Record intent accuracy (predicted vs actual intent).

        Args:
            conversation_id: Conversation ID
            user_id: User ID
            user_message: User message
            predicted_intent: Predicted intent
            actual_intent: Actual intent (from review)
            predicted_confidence: Predicted confidence score
            confidence_distribution: Confidence distribution dict
            language: Language
            model_variant: Model variant
            classification_id: Classification ID
            review_notes: Review notes

        Returns:
            Created intent accuracy record
        """
        # Determine if prediction was correct
        is_correct = 1 if predicted_intent == actual_intent else 0

        # Convert confidence distribution to JSON string
        confidence_dist_json = json.dumps(confidence_distribution) if confidence_distribution else None

        # Create record
        record = IntentAccuracy(
            conversation_id=conversation_id,
            user_id=user_id,
            user_message=user_message,
            predicted_intent=predicted_intent,
            actual_intent=actual_intent,
            is_correct=is_correct,
            predicted_confidence=predicted_confidence,
            confidence_distribution=confidence_dist_json,
            language=language,
            model_variant=model_variant,
            classification_id=classification_id,
            reviewed_by=user_id,
            reviewed_at=datetime.utcnow(),
            review_notes=review_notes,
        )

        self.db.add(record)
        await self.db.commit()
        await self.db.refresh(record)

        self.logger.info(
            f"Intent accuracy recorded: predicted={predicted_intent}, "
            f"actual={actual_intent}, correct={is_correct}, "
            f"confidence={predicted_confidence:.2f}"
        )

        return record

    async def calculate_overall_accuracy(
        self,
        start_date: datetime,
        end_date: datetime,
    ) -> tuple[float, int]:
        """
        Calculate overall accuracy.

        Args:
            start_date: Start date
            end_date: End date

        Returns:
            Tuple of (accuracy, total_predictions)
        """
        query = (
            select(
                func.sum(IntentAccuracy.is_correct).label("correct"),
                func.count(IntentAccuracy.id).label("total"),
            )
            .where(
                IntentAccuracy.created_at >= start_date,
                IntentAccuracy.created_at <= end_date,
            )
        )

        result = await self.db.execute(query)
        row = result.one_or_none()

        if row and row.total > 0:
            accuracy = float(row.correct) / row.total
            total = int(row.total)
        else:
            accuracy = 0.0
            total = 0

        return accuracy, total

    async def calculate_intent_class_accuracy(
        self,
        start_date: datetime,
        end_date: datetime,
    ) -> list[IntentClassAccuracy]:
        """
        Calculate accuracy per intent class.

        Args:
            start_date: Start date
            end_date: End date

        Returns:
            List of intent class accuracy metrics
        """
        query = (
            select(
                IntentAccuracy.predicted_intent.label("intent_class"),
                func.count(IntentAccuracy.id).label("total"),
                func.sum(IntentAccuracy.is_correct).label("correct"),
                func.avg(IntentAccuracy.predicted_confidence).label("avg_conf"),
            )
            .where(
                IntentAccuracy.created_at >= start_date,
                IntentAccuracy.created_at <= end_date,
            )
            .group_by(IntentAccuracy.predicted_intent)
        )

        result = await self.db.execute(query)
        class_accuracies = []

        for row in result:
            total = int(row.total)
            accuracy = float(row.correct) / total if total > 0 else 0.0
            avg_conf = float(row.avg_conf) if row.avg_conf else 0.0

            class_accuracies.append(
                IntentClassAccuracy(
                    intent_class=str(row.intent_class),
                    total_predictions=total,
                    correct_predictions=int(row.correct),
                    accuracy=accuracy,
                    avg_confidence=avg_conf,
                )
            )

        return class_accuracies

    async def get_misclassified_queries(
        self,
        start_date: datetime,
        end_date: datetime,
        limit: int = 50,
    ) -> list[MisclassifiedQuery]:
        """
        Get frequently misclassified queries.

        Args:
            start_date: Start date
            end_date: End date
            limit: Maximum number to return

        Returns:
            List of misclassified queries
        """
        query = (
            select(IntentAccuracy)
            .where(
                and_(
                    IntentAccuracy.created_at >= start_date,
                    IntentAccuracy.created_at <= end_date,
                    IntentAccuracy.is_correct == 0,
                )
            )
            .order_by(IntentAccuracy.created_at.desc())
            .limit(limit)
        )

        result = await self.db.execute(query)
        misclassified = []

        for row in result:
            misclassified.append(
                MisclassifiedQuery(
                    id=row.id,
                    user_message=row.user_message,
                    predicted_intent=row.predicted_intent,
                    actual_intent=row.actual_intent,
                    predicted_confidence=row.predicted_confidence,
                    language=row.language,
                    occurred_at=row.created_at,
                )
            )

        return misclassified

    async def calculate_confidence_distribution(
        self,
        start_date: datetime,
        end_date: datetime,
    ) -> ConfidenceDistribution:
        """
        Calculate confidence score distribution.

        Args:
            start_date: Start date
            end_date: End date

        Returns:
            Confidence distribution
        """
        # Get all confidence scores
        query = (
            select(IntentAccuracy.predicted_confidence)
            .where(
                IntentAccuracy.created_at >= start_date,
                IntentAccuracy.created_at <= end_date,
            )
        )

        result = await self.db.execute(query)
        scores = [row[0] for row in result]

        # Calculate distribution
        range_0_20 = sum(1 for s in scores if 0.0 <= s < 0.2)
        range_20_40 = sum(1 for s in scores if 0.2 <= s < 0.4)
        range_40_60 = sum(1 for s in scores if 0.4 <= s < 0.6)
        range_60_80 = sum(1 for s in scores if 0.6 <= s < 0.8)
        range_80_100 = sum(1 for s in scores if 0.8 <= s <= 1.0)

        # Calculate average and median
        avg_confidence = sum(scores) / len(scores) if scores else 0.0
        sorted_scores = sorted(scores)
        median_confidence = (
            sorted_scores[len(sorted_scores) // 2] if sorted_scores else 0.0
        )

        return ConfidenceDistribution(
            range_0_20=range_0_20,
            range_20_40=range_20_40,
            range_40_60=range_40_60,
            range_60_80=range_60_80,
            range_80_100=range_80_100,
            avg_confidence=avg_confidence,
            median_confidence=median_confidence,
        )

    async def generate_confusion_matrix(
        self,
        start_date: datetime,
        end_date: datetime,
    ) -> list[ConfusionMatrixCell]:
        """
        Generate confusion matrix.

        Args:
            start_date: Start date
            end_date: End date

        Returns:
            Confusion matrix cells
        """
        query = (
            select(
                IntentAccuracy.predicted_intent,
                IntentAccuracy.actual_intent,
                func.count(IntentAccuracy.id).label("count"),
            )
            .where(
                IntentAccuracy.created_at >= start_date,
                IntentAccuracy.created_at <= end_date,
            )
            .group_by(
                IntentAccuracy.predicted_intent,
                IntentAccuracy.actual_intent,
            )
        )

        result = await self.db.execute(query)
        matrix_cells = []

        for row in result:
            matrix_cells.append(
                ConfusionMatrixCell(
                    predicted_intent=str(row.predicted_intent),
                    actual_intent=str(row.actual_intent),
                    count=int(row.count),
                )
            )

        return matrix_cells

    async def export_misclassified_examples(
        self,
        start_date: datetime,
        end_date: datetime,
    ) -> str:
        """
        Export misclassified examples for retraining.

        Args:
            start_date: Start date
            end_date: End date

        Returns:
            CSV string of misclassified examples
        """
        misclassified = await self.get_misclassified_queries(start_date, end_date, limit=1000)

        # Build CSV
        lines = ["user_message,predicted_intent,actual_intent,confidence,language"]
        for item in misclassified:
            # Escape quotes in message
            message = item.user_message.replace('"', '""')
            lines.append(
                f'"{message}",{item.predicted_intent},{item.actual_intent},'
                f'{item.predicted_confidence:.3f},{item.language}'
            )

        return "\n".join(lines)

    async def get_analytics(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> IntentAccuracyAnalyticsResponse:
        """
        Get complete intent accuracy analytics.

        Args:
            start_date: Start date (default: 30 days ago)
            end_date: End date (default: now)

        Returns:
            Complete intent accuracy analytics
        """
        # Set default dates
        if not end_date:
            end_date = datetime.utcnow()
        if not start_date:
            start_date = end_date - timedelta(days=30)

        # Calculate overall accuracy
        overall_accuracy, total_predictions = await self.calculate_overall_accuracy(
            start_date, end_date
        )

        # Calculate intent class accuracy
        intent_class_accuracy = await self.calculate_intent_class_accuracy(
            start_date, end_date
        )

        # Get misclassified queries
        misclassified_queries = await self.get_misclassified_queries(
            start_date, end_date, limit=50
        )

        # Calculate confidence distribution
        confidence_distribution = await self.calculate_confidence_distribution(
            start_date, end_date
        )

        # Generate confusion matrix
        confusion_matrix = await self.generate_confusion_matrix(start_date, end_date)

        return IntentAccuracyAnalyticsResponse(
            overall_accuracy=overall_accuracy,
            total_predictions=total_predictions,
            intent_class_accuracy=intent_class_accuracy,
            misclassified_queries=misclassified_queries,
            confidence_distribution=confidence_distribution,
            confusion_matrix=confusion_matrix,
        )
