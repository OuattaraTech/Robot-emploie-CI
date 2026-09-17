"""emploi.ci — le plus gros gisement d'annonces ivoiriennes.

Le site est derrière Cloudflare : une requête HTTP nue reçoit la page
« Just a moment… » et rien d'autre. D'où « navigateur: true » dans
config.yaml, qui fait ouvrir un vrai Chromium par Playwright.

Trois lectures sont tentées dans l'ordre, de la plus fiable à la plus
tolérante : le JSON-LD que le site publie pour Google Jobs, les cartes
d'annonces, puis un simple repêchage par adresse. Une refonte du site
dégrade la qualité du rapport sans jamais l'interrompre.
"""

from __future__ import annotations

from urllib.parse import urljoin

from ..modeles import Offre
from ..reseau import AccesRefuse
from .base import Source, offres_depuis_json_ld, offres_depuis_liens

DEFAUT = "https://www.emploi.ci/recherche-jobs-cote-ivoire"
MOTIF_ANNONCE = r"/(offre-emploi|recherche-jobs)[^/]*/"

# Sélecteurs constatés sur le gabarit d'emploi.ci. S'ils cessent de
# répondre, le repêchage par adresse prend le relais.
CARTE = "div.card-job, div.job-description-wrapper, article.job"
TITRE = "h5 a, h2 a, h3 a, .card-job-title a"
ENTREPRISE = ".card-job-company, .company-name, .job-company"
LIEU = ".card-job-location, .job-location, li.location"


class EmploiCI(Source):
    nom = "emploici"

    def collecter(self) -> list[Offre]:
        base = self.reglages.get("url", DEFAUT)
        pages = int(self.reglages.get("pages", 2))
        moisson: list[Offre] = []

        for page in range(1, pages + 1):
            url = base if page == 1 else f"{base}?page={page}"
            try:
                soupe = self.html(url, attente=CARTE.split(",")[0])
            except AccesRefuse as refus:
                # Playwright absent, ou Cloudflare qui tient bon : on le
                # dit clairement et on laisse le cycle continuer.
                self.log.warning("source sautée — %s", refus)
                break

            annonces = offres_depuis_json_ld(soupe, self.nom)
            if not annonces:
                annonces = self._cartes(soupe, url)
            if not annonces:
                annonces = offres_depuis_liens(soupe, self.nom, url, MOTIF_ANNONCE)

            if not annonces:
                self.log.debug("page %d : aucune annonce lisible", page)
                break

            moisson.extend(annonces)
            self.log.debug("page %d : %d annonces", page, len(annonces))

        self.log.info("%d annonces récupérées", len(moisson))
        return [o for o in moisson if o.titre]

    def _cartes(self, soupe, url: str) -> list[Offre]:
        trouvees: list[Offre] = []
        for carte in soupe.select(CARTE):
            lien = carte.select_one(TITRE)
            titre = self.texte(lien) or self.texte(carte, "h5, h2, h3")
            if not titre:
                continue
            trouvees.append(Offre(
                titre=titre,
                entreprise=self.texte(carte, ENTREPRISE),
                lieu=self.texte(carte, LIEU),
                source=self.nom,
                url=urljoin(url, lien.get("href", "")) if lien else url,
                description=self.texte(carte)[:600],
            ))
        return trouvees
