"""Registre des sources. Ajouter un site = écrire un module et l'inscrire ici."""

from __future__ import annotations

from ..reseau import Navigateur
from .afriwork import Afriwork
from .base import Source
from .emploici import EmploiCI
from .jobnetafrica import JobnetAfrica
from .linkedin import LinkedIn
from .novojob import Novojob

REGISTRE: dict[str, type[Source]] = {
    LinkedIn.nom: LinkedIn,
    Novojob.nom: Novojob,
    JobnetAfrica.nom: JobnetAfrica,
    EmploiCI.nom: EmploiCI,
    Afriwork.nom: Afriwork,
}


def construire(nom: str, reglages: dict, navigateur: Navigateur) -> Source:
    if nom not in REGISTRE:
        raise KeyError(
            f"source inconnue : {nom}. Connues : {', '.join(sorted(REGISTRE))}"
        )
    return REGISTRE[nom](reglages, navigateur)


__all__ = ["REGISTRE", "Source", "construire"]
