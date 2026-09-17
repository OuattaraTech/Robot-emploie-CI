"""Canaux de sortie du rapport."""

from .courriel import envoyer_email, tester_email
from .telegram import envoyer_telegram

__all__ = ["envoyer_email", "tester_email", "envoyer_telegram"]
