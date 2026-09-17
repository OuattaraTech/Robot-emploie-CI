"""L'offre d'emploi telle qu'elle circule dans tout le robot."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from datetime import date, datetime
from urllib.parse import urlparse, urlunparse


def _url_canonique(url: str) -> str:
    """Retire les paramètres de suivi : la même annonce doit produire la
    même empreinte, qu'elle arrive d'une recherche ou d'une autre."""
    if not url:
        return ""
    morceaux = urlparse(url)
    return urlunparse((morceaux.scheme, morceaux.netloc, morceaux.path, "", "", ""))


def normaliser(texte: str) -> str:
    """Minuscules, accents aplatis, espaces tassés — pour comparer sans
    se faire piéger par « Développeur » contre « developpeur »."""
    if not texte:
        return ""
    texte = texte.lower()
    for accentue, plat in (
        ("àâä", "a"), ("éèêë", "e"), ("îï", "i"),
        ("ôö", "o"), ("ùûü", "u"), ("ç", "c"),
    ):
        for lettre in accentue:
            texte = texte.replace(lettre, plat)
    return re.sub(r"\s+", " ", texte).strip()


@dataclass
class Offre:
    titre: str
    entreprise: str = ""
    lieu: str = ""
    source: str = ""
    url: str = ""
    description: str = ""
    contrat: str = ""
    date_publication: date | None = None
    recuperee_le: datetime = field(default_factory=datetime.now)

    # Remplis par le filtrage, pas par les sources.
    score: int = 0
    motifs: list[str] = field(default_factory=list)

    @property
    def empreinte(self) -> str:
        """Identifiant stable d'une annonce. L'URL fait foi quand elle
        existe ; sinon on retombe sur titre + entreprise + source."""
        base = _url_canonique(self.url) or "|".join(
            (normaliser(self.titre), normaliser(self.entreprise), self.source)
        )
        return hashlib.sha1(base.encode("utf-8")).hexdigest()[:16]

    @property
    def texte_recherchable(self) -> str:
        return normaliser(" ".join((self.titre, self.entreprise, self.lieu,
                                    self.contrat, self.description)))

    def __str__(self) -> str:
        lieu = f" — {self.lieu}" if self.lieu else ""
        return f"[{self.source}] {self.titre} · {self.entreprise or '?'}{lieu}"
