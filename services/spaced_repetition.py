import math
from datetime import datetime, timedelta


class SpacedRepetition:
    """Simple SM-2 inspired spaced repetition algorithm."""

    @staticmethod
    def calculate_next_interval(quality: int, repetitions: int,
                                 previous_interval: float) -> float:
        """
        quality: 0-5 (0=complete blackout, 5=perfect recall)
        repetitions: number of consecutive correct recalls
        previous_interval: days since last review
        """
        if quality < 3:
            return 1.0

        if repetitions == 0:
            return 1.0
        elif repetitions == 1:
            return 3.0
        elif repetitions == 2:
            return 7.0
        else:
            return previous_interval * SpacedRepetition._ease_factor(quality)

    @staticmethod
    def _ease_factor(quality: int) -> float:
        if quality >= 4:
            return 2.0
        elif quality == 3:
            return 1.5
        else:
            return 1.0

    @staticmethod
    def next_review_date(interval_days: float) -> datetime:
        return datetime.now() + timedelta(days=interval_days)

    @staticmethod
    def confidence_to_quality(confidence: int) -> int:
        mapping = {1: 1, 2: 2, 3: 3, 4: 4, 5: 5}
        return mapping.get(confidence, 3)
