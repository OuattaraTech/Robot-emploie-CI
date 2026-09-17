"""LinkedIn — via l'API publique des offres, celle qui sert la pagination
des pages consultables sans compte. Pas de connexion, pas de cookie.
"""

from __future__ import annotations

from urllib.parse import urlencode

from ..modeles import Offre
from .base import Source

RECHERCHE = "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search"
PAR_PAGE = 25


class LinkedIn(Source):
    nom = "linkedin"

    def _url(self, mots: str, debut: int) -> str:
        parametres = {
            "keywords": mots,
            "location": self.reglages.get("lieu", "Côte d'Ivoire"),
            "start": debut,
        }
        anciennete = self.reglages.get("anciennete")
        if anciennete:
            parametres["f_TPR"] = anciennete
        return f"{RECHERCHE}?{urlencode(parametres)}"

    def collecter(self) -> list[Offre]:
        recherches = self.reglages.get("recherches") or ["développeur"]
        pages = int(self.reglages.get("pages", 2))
        moisson: list[Offre] = []

        for mots in recherches:
            for page in range(pages):
                url = self._url(mots, page * PAR_PAGE)
                soupe = self.html(url)
                cartes = soupe.select("div.base-card")
                if not cartes:
                    # Plus rien à paginer pour ce mot-clé.
                    break

                for carte in cartes:
                    lien = carte.select_one("a.base-card__full-link")
                    horodatage = carte.select_one("time")
                    moisson.append(Offre(
                        titre=self.texte(carte, "h3.base-search-card__title"),
                        entreprise=self.texte(carte, "h4.base-search-card__subtitle"),
                        lieu=self.texte(carte, "span.job-search-card__location"),
                        source=self.nom,
                        url=(lien.get("href", "") if lien else "").split("?")[0],
                        description=f"Recherche « {mots} »",
                        date_publication=self.date_iso(
                            horodatage.get("datetime") if horodatage else None
                        ),
                    ))

                self.log.debug("« %s » page %d : %d annonces", mots, page + 1, len(cartes))
                if len(cartes) < PAR_PAGE:
                    break

        self.log.info("%d annonces récupérées", len(moisson))
        return [o for o in moisson if o.titre]
