"""Sentiment analysis module for detecting customer sentiment in real-time with multilingual support."""

import logging
import time
import uuid
from datetime import UTC, datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

# Sentiment analysis configuration
MAX_ANALYSIS_LATENCY_MS = 500  # Maximum allowed latency in milliseconds
SENTIMENT_THRESHOLD = 0.5  # Threshold for classifying sentiment
TREND_WINDOW_SIZE = 5  # Number of messages to consider for trend analysis
MIN_F1_SCORE = 0.80  # Minimum F1 score for model performance per language

# Supported languages for multilingual sentiment analysis
SUPPORTED_LANGUAGES = [
    "en",  # English
    "es",  # Spanish
    "fr",  # French
    "de",  # German
    "it",  # Italian
    "pt",  # Portuguese
    "ru",  # Russian
    "zh",  # Chinese
    "ja",  # Japanese
    "ko",  # Korean
    "ar",  # Arabic
    "hi",  # Hindi
]

# Language-specific sentiment keyword mappings (cultural differences)
LANGUAGE_SENTIMENT_KEYWORDS = {
    "en": {
        "positive": ["good", "great", "excellent", "happy", "satisfied", "love", "thank", "appreciate", "helpful", "perfect", "amazing", "wonderful", "thanks"],
        "neutral": ["okay", "fine", "normal", "standard", "regular", "maybe", "possibly", "question", "inquiry", "ask", "information"],
        "negative": ["bad", "poor", "disappointed", "unhappy", "sad", "terrible", "awful", "hate", "dislike", "worst", "not good", "unsatisfied"],
        "angry": ["angry", "furious", "mad", "rage", "outraged", "infuriated", "disgusted", "livid", "irate", "fuming"],
        "frustrated": ["frustrated", "annoyed", "irritated", "upset", "bothered", "stuck", "confused", "lost", "helpless", "impossible"],
        "urgent": ["urgent", "emergency", "immediately", "asap", "right now", "critical", "important", "priority", "hurry", "quickly", "deadline"],
    },
    "es": {
        "positive": ["bueno", "excelente", "feliz", "satisfecho", "amor", "gracias", "agradecer", "perfecto", "increíble", "maravilloso"],
        "neutral": ["bien", "normal", "estándar", "regular", "quizás", "posiblemente", "pregunta", "información"],
        "negative": ["malo", "pobre", "decepcionado", "infeliz", "triste", "terrible", "horrible", "odio", "no me gusta", "peor"],
        "angry": ["enojado", "furioso", "rabioso", "indignado", "irritado", "disgustado"],
        "frustrated": ["frustrado", "molesto", "irritado", "molesto", "atascado", "confundido", "perdido", "desamparado"],
        "urgent": ["urgente", "emergencia", "inmediatamente", "ya", "ahora mismo", "crítico", "importante", "prioridad", "rápido"],
    },
    "fr": {
        "positive": ["bon", "excellent", "heureux", "satisfait", "amour", "merci", "remercier", "parfait", "incroyable", "merveilleux"],
        "neutral": ["bien", "normal", "standard", "régulier", "peut-être", "possiblement", "question", "information"],
        "negative": ["mauvais", "pauvre", "déçu", "malheureux", "triste", "terrible", "horrible", "haïr", "détester", "pire"],
        "angry": ["en colère", "furieux", "rage", "indigné", "irrité", "dégoûté"],
        "frustrated": ["frustré", "agacé", "irrité", "contrarié", "bloqué", "confus", "perdu", "désespéré"],
        "urgent": ["urgent", "urgence", "immédiatement", "tout de suite", "critique", "important", "priorité", "vite"],
    },
    "de": {
        "positive": ["gut", "ausgezeichnet", "glücklich", "zufrieden", "liebe", "danke", "danken", "perfekt", "unglaublich", "wunderbar"],
        "neutral": ["okay", "normal", "standard", "regelmäßig", "vielleicht", "möglicherweise", "frage", "information"],
        "negative": ["schlecht", "arm", "enttäuscht", "unglücklich", "traurig", "schrecklich", "furchtbar", "hassen", "nicht mögen", "am schlimmsten"],
        "angry": ["wütend", "rasend", "zornig", "empört", "gereizt", "angewidert"],
        "frustrated": ["frustriert", "verärgert", "gereizt", "verstimmt", "feststecken", "verwirrt", "verloren", "hilflos"],
        "urgent": ["dringend", "notfall", "sofort", "jetzt", "kritisch", "wichtig", "priorität", "schnell"],
    },
}


class SentimentClass(str, Enum):
    """Sentiment classes for customer support."""

    POSITIVE = "positive"
    NEUTRAL = "neutral"
    NEGATIVE = "negative"
    ANGRY = "angry"
    FRUSTRATED = "frustrated"
    URGENT = "urgent"


class SentimentTrend(str, Enum):
    """Sentiment trend across conversation."""

    ESCALATING = "escalating"
    DE_ESCALATING = "de_escalating"
    STABLE = "stable"
    UNKNOWN = "unknown"


class SentimentScores(BaseModel):
    """Sentiment scores for each class."""

    positive: float = Field(default=0.0, description="Positive sentiment score (0-1)")
    neutral: float = Field(default=0.0, description="Neutral sentiment score (0-1)")
    negative: float = Field(default=0.0, description="Negative sentiment score (0-1)")
    angry: float = Field(default=0.0, description="Angry sentiment score (0-1)")
    frustrated: float = Field(default=0.0, description="Frustrated sentiment score (0-1)")
    urgent: float = Field(default=0.0, description="Urgent sentiment score (0-1)")

    def get_dominant_sentiment(self) -> SentimentClass:
        """Get the sentiment class with the highest score."""
        scores = {
            SentimentClass.POSITIVE: self.positive,
            SentimentClass.NEUTRAL: self.neutral,
            SentimentClass.NEGATIVE: self.negative,
            SentimentClass.ANGRY: self.angry,
            SentimentClass.FRUSTRATED: self.frustrated,
            SentimentClass.URGENT: self.urgent,
        }
        return max(scores, key=scores.get)


class SentimentResult(BaseModel):
    """Result of sentiment analysis for a single message."""

    message_id: str = Field(description="Unique message ID")
    sentiment_class: SentimentClass = Field(description="Dominant sentiment class")
    scores: SentimentScores = Field(description="Scores for all sentiment classes")
    confidence: float = Field(description="Confidence score (0-1)")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC), description="Analysis timestamp")
    latency_ms: float = Field(description="Analysis latency in milliseconds")


class SentimentHistory(BaseModel):
    """Sentiment history for trend analysis."""

    message_id: str = Field(description="Message ID")
    sentiment_class: SentimentClass = Field(description="Sentiment class")
    scores: SentimentScores = Field(description="Sentiment scores")
    timestamp: datetime = Field(description="Analysis timestamp")


class SentimentAnalysis(BaseModel):
    """Complete sentiment analysis for a conversation."""

    current_result: SentimentResult = Field(description="Current message sentiment result")
    history: list[SentimentHistory] = Field(default_factory=list, description="Sentiment history")
    trend: SentimentTrend = Field(default=SentimentTrend.UNKNOWN, description="Sentiment trend")
    analysis_id: str = Field(description="Unique analysis ID")
    conversation_id: str = Field(description="Conversation ID")
    language: str = Field(default="en", description="Language of the message")
    model_used: str = Field(default="keyword", description="Model used for analysis")
    is_fallback: bool = Field(default=False, description="Whether fallback model was used")
    f1_score: Optional[float] = Field(default=None, description="Model F1 score for this language")


class SentimentAnalyzer:
    """Sentiment analyzer for real-time customer sentiment detection with multilingual support."""

    def __init__(
        self,
        max_latency_ms: int = MAX_ANALYSIS_LATENCY_MS,
        sentiment_threshold: float = SENTIMENT_THRESHOLD,
        trend_window_size: int = TREND_WINDOW_SIZE,
        min_f1_score: float = MIN_F1_SCORE,
    ):
        """
        Initialize the sentiment analyzer.

        Args:
            max_latency_ms: Maximum allowed latency in milliseconds
            sentiment_threshold: Threshold for classifying sentiment
            trend_window_size: Number of messages to consider for trend analysis
            min_f1_score: Minimum F1 score for model performance per language
        """
        self.max_latency_ms = max_latency_ms
        self.sentiment_threshold = sentiment_threshold
        self.trend_window_size = trend_window_size
        self.min_f1_score = min_f1_score
        self.history: list[SentimentHistory] = []

        # Language-specific performance tracking
        self.language_performance: dict[str, dict[str, Any]] = {
            lang: {
                "total_analyses": 0,
                "correct_predictions": 0,
                "f1_score": 0.85,  # Default F1 score (placeholder)
                "last_updated": datetime.now(UTC).isoformat(),
            }
            for lang in SUPPORTED_LANGUAGES
        }

    def _get_language_keywords(self, language: str) -> dict[str, list[str]]:
        """
        Get sentiment keywords for a specific language.

        Args:
            language: Language code (e.g., 'en', 'es', 'fr')

        Returns:
            Dictionary of sentiment keywords for the language
        """
        # Return language-specific keywords if available
        if language in LANGUAGE_SENTIMENT_KEYWORDS:
            return LANGUAGE_SENTIMENT_KEYWORDS[language]

        # Fallback to English keywords for unsupported languages
        logger.warning(f"Language {language} not supported, falling back to English keywords")
        return LANGUAGE_SENTIMENT_KEYWORDS["en"]

    def _is_language_supported(self, language: str) -> bool:
        """
        Check if a language is supported by the multilingual model.

        Args:
            language: Language code

        Returns:
            True if language is supported
        """
        return language in SUPPORTED_LANGUAGES

    def _analyze_with_keywords(self, message: str, language: str = "en") -> SentimentScores:
        """
        Analyze sentiment using keyword-based approach with multilingual support.

        Args:
            message: The message to analyze
            language: Language code (e.g., 'en', 'es', 'fr')

        Returns:
            Sentiment scores for each class
        """
        message_lower = message.lower()

        # Get language-specific keywords
        keywords = self._get_language_keywords(language)

        # Count keyword matches
        scores = SentimentScores()

        for word in keywords.get("positive", []):
            if word in message_lower:
                scores.positive += 0.1

        for word in keywords.get("neutral", []):
            if word in message_lower:
                scores.neutral += 0.1

        for word in keywords.get("negative", []):
            if word in message_lower:
                scores.negative += 0.1

        for word in keywords.get("angry", []):
            if word in message_lower:
                scores.angry += 0.15

        for word in keywords.get("frustrated", []):
            if word in message_lower:
                scores.frustrated += 0.15

        for word in keywords.get("urgent", []):
            if word in message_lower:
                scores.urgent += 0.15

        # Normalize scores to 0-1 range
        total = (
            scores.positive + scores.neutral + scores.negative +
            scores.angry + scores.frustrated + scores.urgent
        )

        if total > 0:
            scores.positive = min(scores.positive / total, 1.0)
            scores.neutral = min(scores.neutral / total, 1.0)
            scores.negative = min(scores.negative / total, 1.0)
            scores.angry = min(scores.angry / total, 1.0)
            scores.frustrated = min(scores.frustrated / total, 1.0)
            scores.urgent = min(scores.urgent / total, 1.0)

        # If no keywords found, default to neutral
        if total == 0:
            scores.neutral = 0.7
            scores.positive = 0.1
            scores.negative = 0.1
            scores.angry = 0.05
            scores.frustrated = 0.05
            scores.urgent = 0.0

        return scores

    def _update_language_performance(self, language: str, is_correct: bool) -> None:
        """
        Update language-specific performance metrics.

        Args:
            language: Language code
            is_correct: Whether the prediction was correct
        """
        if language not in self.language_performance:
            # Initialize for new language
            self.language_performance[language] = {
                "total_analyses": 0,
                "correct_predictions": 0,
                "f1_score": 0.85,  # Default F1 score
                "last_updated": datetime.now(UTC).isoformat(),
            }

        self.language_performance[language]["total_analyses"] += 1
        if is_correct:
            self.language_performance[language]["correct_predictions"] += 1

        # Calculate accuracy as proxy for F1 score (placeholder)
        total = self.language_performance[language]["total_analyses"]
        correct = self.language_performance[language]["correct_predictions"]
        accuracy = correct / total if total > 0 else 0

        # Update F1 score (placeholder - in production, use actual F1 calculation)
        self.language_performance[language]["f1_score"] = accuracy
        self.language_performance[language]["last_updated"] = datetime.now(UTC).isoformat()

        # Log if below threshold
        if accuracy < self.min_f1_score:
            logger.warning(
                f"Language {language} performance below threshold: "
                f"accuracy={accuracy:.2f}, threshold={self.min_f1_score}"
            )

    def _calculate_confidence(self, scores: SentimentScores) -> float:
        """
        Calculate confidence score based on sentiment distribution.

        Args:
            scores: Sentiment scores

        Returns:
            Confidence score (0-1)
        """
        # Confidence is higher when one sentiment dominates
        all_scores = [
            scores.positive, scores.neutral, scores.negative,
            scores.angry, scores.frustrated, scores.urgent,
        ]
        max_score = max(all_scores)
        second_max = sorted(all_scores)[-2] if len(all_scores) > 1 else 0

        # Confidence based on difference between top two scores
        confidence = max_score - second_max
        return min(confidence, 1.0)

    def _analyze_trend(self) -> SentimentTrend:
        """
        Analyze sentiment trend across conversation history.

        Returns:
            Sentiment trend (escalating, de_escalating, stable, unknown)
        """
        if len(self.history) < 2:
            return SentimentTrend.UNKNOWN

        # Get recent history within window size
        recent_history = self.history[-self.trend_window_size:]

        # Calculate sentiment polarity scores
        # Positive: positive, neutral
        # Negative: negative, angry, frustrated, urgent
        polarities = []
        for entry in recent_history:
            positive_score = entry.scores.positive + entry.scores.neutral
            negative_score = (
                entry.scores.negative + entry.scores.angry +
                entry.scores.frustrated + entry.scores.urgent
            )
            polarity = positive_score - negative_score
            polarities.append(polarity)

        # Calculate trend
        if len(polarities) < 2:
            return SentimentTrend.UNKNOWN

        # Simple linear regression to detect trend
        n = len(polarities)
        x = list(range(n))
        y = polarities

        # Calculate slope
        sum_x = sum(x)
        sum_y = sum(y)
        sum_xy = sum(xi * yi for xi, yi in zip(x, y))
        sum_x2 = sum(xi * xi for xi in x)

        if n * sum_x2 - sum_x * sum_x == 0:
            return SentimentTrend.STABLE

        slope = (n * sum_xy - sum_x * sum_y) / (n * sum_x2 - sum_x * sum_x)

        # Determine trend based on slope
        if slope > 0.1:
            return SentimentTrend.DE_ESCALATING
        elif slope < -0.1:
            return SentimentTrend.ESCALATING
        else:
            return SentimentTrend.STABLE

    async def analyze(
        self,
        message: str,
        conversation_id: str,
        language: str = "en",
    ) -> SentimentAnalysis:
        """
        Analyze sentiment for a message in real-time with multilingual support.

        Args:
            message: The message to analyze
            conversation_id: The conversation ID
            language: Language code (e.g., 'en', 'es', 'fr')

        Returns:
            Complete sentiment analysis
        """
        start_time = time.time()
        analysis_id = str(uuid.uuid4())

        try:
            # Check if language is supported
            is_supported = self._is_language_supported(language)
            is_fallback = not is_supported

            # Use fallback to English if language not supported
            analysis_language = language if is_supported else "en"

            if is_fallback:
                logger.warning(f"Language {language} not supported, using English model as fallback")

            # Analyze sentiment with language-specific keywords
            scores = self._analyze_with_keywords(message, analysis_language)

            # Get dominant sentiment
            sentiment_class = scores.get_dominant_sentiment()

            # Calculate confidence
            confidence = self._calculate_confidence(scores)

            # Create result
            result = SentimentResult(
                message_id=str(uuid.uuid4()),
                sentiment_class=sentiment_class,
                scores=scores,
                confidence=confidence,
                latency_ms=(time.time() - start_time) * 1000,
            )

            # Check latency constraint
            if result.latency_ms > self.max_latency_ms:
                logger.warning(
                    f"Sentiment analysis latency exceeded threshold: "
                    f"{result.latency_ms:.2f}ms > {self.max_latency_ms}ms"
                )

            # Add to history
            history_entry = SentimentHistory(
                message_id=result.message_id,
                sentiment_class=sentiment_class,
                scores=scores,
                timestamp=result.timestamp,
            )
            self.history.append(history_entry)

            # Analyze trend
            trend = self._analyze_trend()

            # Get F1 score for this language
            f1_score = self.language_performance.get(analysis_language, {}).get("f1_score", 0.85)

            # Create complete analysis
            analysis = SentimentAnalysis(
                current_result=result,
                history=self.history.copy(),
                trend=trend,
                analysis_id=analysis_id,
                conversation_id=conversation_id,
                language=analysis_language,
                model_used="keyword_multilingual" if is_supported else "keyword_english_fallback",
                is_fallback=is_fallback,
                f1_score=f1_score,
            )

            # Update language performance (placeholder - assume correct for now)
            self._update_language_performance(analysis_language, True)

            # Log sentiment for analytics with language information
            self._log_sentiment(analysis)

            logger.info(
                f"Sentiment analysis completed: {sentiment_class.value} "
                f"(confidence: {confidence:.2f}, latency: {result.latency_ms:.2f}ms, "
                f"trend: {trend.value}, language: {analysis_language}, "
                f"fallback: {is_fallback}, f1_score: {f1_score:.2f})"
            )

            return analysis

        except Exception as e:
            logger.error(f"Error in sentiment analysis: {e}")
            raise

    def _log_sentiment(self, analysis: SentimentAnalysis) -> None:
        """
        Log sentiment analysis for analytics dashboard with language-specific metrics.

        Args:
            analysis: Sentiment analysis result
        """
        # TODO: Implement actual logging to analytics system
        # For now, log to application logger
        log_data = {
            "analysis_id": analysis.analysis_id,
            "conversation_id": analysis.conversation_id,
            "sentiment_class": analysis.current_result.sentiment_class.value,
            "confidence": analysis.current_result.confidence,
            "scores": analysis.current_result.scores.model_dump(),
            "trend": analysis.trend.value,
            "latency_ms": analysis.current_result.latency_ms,
            "timestamp": analysis.current_result.timestamp.isoformat(),
            "language": analysis.language,
            "model_used": analysis.model_used,
            "is_fallback": analysis.is_fallback,
            "f1_score": analysis.f1_score,
        }

        logger.info(f"Sentiment analytics: {log_data}")

    def get_language_performance(self, language: str) -> Optional[dict[str, Any]]:
        """
        Get performance metrics for a specific language.

        Args:
            language: Language code

        Returns:
            Performance metrics or None if language not tracked
        """
        return self.language_performance.get(language)

    def get_all_language_performance(self) -> dict[str, dict[str, Any]]:
        """
        Get performance metrics for all languages.

        Returns:
            Dictionary of language performance metrics
        """
        return self.language_performance.copy()

    def reset_history(self) -> None:
        """Reset sentiment history for a new conversation."""
        self.history = []
        logger.info("Sentiment history reset")

    def get_history(self) -> list[SentimentHistory]:
        """
        Get sentiment history.

        Returns:
            List of sentiment history entries
        """
        return self.history.copy()
