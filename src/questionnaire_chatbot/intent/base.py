"""Classifier contract only; no intent classification is implemented."""

from typing import Protocol


class IntentClassifier(Protocol):
    """Common contract for future classifier adapters."""

    def classify(self, text: str) -> str:
        """Return an application-defined intent label."""
        ...
