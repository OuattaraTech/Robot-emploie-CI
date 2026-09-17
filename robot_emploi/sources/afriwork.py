"""Afriwork — plateforme d'offres rendue côté client : le HTML servi est
une coquille vide, les annonces arrivent par JavaScript. Chromium est donc
obligatoire ici, quoi qu'en dise config.yaml.
"""

from __future__ import annotations

from ..modeles import Offre
from ..reseau import AccesRefuse
from .base import Source, offres_depuis_json_ld, offres_depuis_liens

DEFAUT = "https://afriworket.com/jobs"
MOTIF_ANNONCE = r"/jobs?/[a-z0-9-]{6,}"
CARTE = "[class*='job-card'], [data-testid*='job'], article"


class Afriwork(Source):
    nom = "afriwork"

    def collecter(self) -> list[Offre]:
        url = self.reglages.get("url", DEFAUT)
        # Le rendu côté client ne laisse pas le choix.
        self.reglages = {**self.reglages, "navigateur": True}

        try:
            soupe = self.html(url, attente=CARTE.split(",")[0])
        except AccesRefuse as refus:
            self.log.warning("source sautée — %s", refus)
            return []

        annonces = offres_depuis_json_ld(soupe, self.nom)
        if not annonces:
            annonces = self._cartes(soupe)
        if not annonces:
            annonces = offres_depuis_liens(soupe, self.nom, url, MOTIF_ANNONCE)

        self.log.info("%d annonces récupérées", len(annonces))
        return [o for o in annonces if o.titre]

    def _cartes(self, soupe) -> list[Offre]:
        trouvees: list[Offre] = []
        for carte in soupe.select(CARTE):
            titre = self.texte(carte, "h2, h3, h4, [class*='title']")
            if len(titre) < 6:
                continue
            lien = carte.select_one("a[href]")
            trouvees.append(Offre(
                titre=titre[:160],
                entreprise=self.texte(carte, "[class*='company'], [class*='org']"),
                lieu=self.texte(carte, "[class*='location'], [class*='city']"),
                source=self.nom,
                url=(lien.get("href", "") if lien else ""),
                description=self.texte(carte)[:600],
            ))
        return trouvees
