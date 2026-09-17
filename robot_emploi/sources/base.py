"""Socle commun aux sources : récupération de page et lecture JSON-LD."""

from __future__ import annotations

import re
from abc import ABC, abstractmethod
from datetime import date, datetime

from bs4 import BeautifulSoup, Tag

from ..journal import obtenir
from ..modeles import Offre
from ..reseau import AccesRefuse, Navigateur, page_via_navigateur


class Source(ABC):
    """Un site surveillé.

    Une source ne filtre pas et ne dédoublonne pas : elle rend tout ce
    qu'elle trouve. Le tri vient après, dans filtrage.py.
    """

    nom: str = "source"

    def __init__(self, reglages: dict, navigateur: Navigateur):
        self.reglages = reglages or {}
        self.navigateur = navigateur
        self.log = obtenir(self.nom)

    @abstractmethod
    def collecter(self) -> list[Offre]:
        ...

    # ─── Outils partagés ─────────────────────────────────────────────
    def html(self, url: str, attente: str | None = None, **kwargs) -> BeautifulSoup:
        """Rend la page analysée. Passe par un vrai Chromium si la source
        est déclarée « navigateur: true » dans config.yaml, ou si le site
        nous ferme la porte au nez."""
        if self.reglages.get("navigateur"):
            return BeautifulSoup(page_via_navigateur(url, attente), "lxml")
        try:
            reponse = self.navigateur.obtenir(url, **kwargs)
        except AccesRefuse:
            self.log.info("accès direct refusé, seconde tentative via Chromium")
            return BeautifulSoup(page_via_navigateur(url, attente), "lxml")
        return BeautifulSoup(reponse.text, "lxml")

    @staticmethod
    def texte(noeud: Tag | None, selecteur: str | None = None) -> str:
        """Texte propre d'un nœud, ou d'un de ses descendants."""
        if noeud is None:
            return ""
        cible = noeud.select_one(selecteur) if selecteur else noeud
        if cible is None:
            return ""
        return re.sub(r"\s+", " ", cible.get_text(" ", strip=True)).strip()

    @staticmethod
    def date_iso(valeur: str | None) -> date | None:
        if not valeur:
            return None
        valeur = valeur.strip().replace("Z", "+00:00")
        for forme in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"):
            try:
                return datetime.strptime(valeur[:10], forme).date()
            except ValueError:
                continue
        try:
            return datetime.fromisoformat(valeur).date()
        except ValueError:
            return None
