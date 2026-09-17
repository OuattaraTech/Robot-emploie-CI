"""Journalisation : une ligne lisible à l'écran, tout l'historique sur disque."""

from __future__ import annotations

import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

_CONFIGURE = False


def configurer(dossier: Path = Path("journaux"), verbeux: bool = False) -> None:
    """Branche la sortie écran et le fichier tournant. Idempotent."""
    global _CONFIGURE
    if _CONFIGURE:
        return

    dossier.mkdir(parents=True, exist_ok=True)
    racine = logging.getLogger("robot")
    racine.setLevel(logging.DEBUG if verbeux else logging.INFO)
    racine.propagate = False

    ecran = logging.StreamHandler(sys.stdout)
    ecran.setLevel(logging.DEBUG if verbeux else logging.INFO)
    ecran.setFormatter(logging.Formatter("%(asctime)s  %(message)s", "%H:%M:%S"))
    racine.addHandler(ecran)

    # 2 Mo par fichier, cinq fichiers : de quoi remonter plusieurs semaines
    # de cycles sans jamais saturer le disque.
    fichier = RotatingFileHandler(
        dossier / "robot.log", maxBytes=2_000_000, backupCount=5, encoding="utf-8"
    )
    fichier.setLevel(logging.DEBUG)
    fichier.setFormatter(
        logging.Formatter("%(asctime)s  %(levelname)-7s %(name)s  %(message)s")
    )
    racine.addHandler(fichier)

    _CONFIGURE = True


def obtenir(nom: str) -> logging.Logger:
    return logging.getLogger(f"robot.{nom}")
