"""Novojob — job board ivoirien, accessible en HTTP simple.

Il remplace en pratique emploi.ci, muré derrière Cloudflare : mêmes
annonces ivoiriennes, mêmes entreprises, mais une page qui se lit sans
navigateur ni contorsion.

Le site publie une liste générale et des rubriques par métier ; on peut
lui donner autant d'adresses qu'on veut dans config.yaml, il les enchaîne
et le dédoublonnage fait le reste.
"""

from __future__ import annotations

import re
from urllib.parse import urljoin

from ..modeles import Offre
from .base import Source

DEFAUT = ["https://www.novojob.com/cote-d-ivoire/offres-d-emploi"]
CARTE = "li.separator-bot"
LIEN_ANNONCE = re.compile(r"/offre-d-emploi/")


class Novojob(Source):
    nom = "novojob"

    def collecter(self) -> list[Offre]:
        adresses = self.reglages.get("urls") or DEFAUT
        moisson: list[Offre] = []

        for adresse in adresses:
            try:
                soupe = self.html(adresse, attente=CARTE)
            except Exception as erreur:
                self.log.warning("%s : %s", adresse, erreur)
                continue

            cartes = soupe.select(CARTE)
            for carte in cartes:
                lien = carte.find("a", href=LIEN_ANNONCE)
                if lien is None:
                    continue

                titre = self.texte(lien, "h2") or self.texte(lien)
                if not titre:
                    continue

                # Le bas de carte empile lieu, date et niveau dans des
                # spans sans classe : seules les icônes les distinguent.
                bas = self.texte(carte, "div.bloc-bottom")
                lieu = self._apres_icone(carte, "fa-map-marker")

                moisson.append(Offre(
                    titre=titre,
                    entreprise=self.texte(carte, "div.contact h6"),
                    lieu=lieu[:60],
                    source=self.nom,
                    url=urljoin(adresse, lien.get("href", "")),
                    description=bas[:400],
                ))

            self.log.debug("%s : %d annonces", adresse.rsplit("/", 1)[-1], len(cartes))

        self.log.info("%d annonces récupérées (%d adresses)", len(moisson), len(adresses))
        return moisson

    @staticmethod
    def _apres_icone(carte, classe_icone: str) -> str:
        """Texte du span qui porte une icône donnée. Le gabarit de Novojob
        ne nomme pas ses champs : l'icône est le seul repère fiable."""
        icone = carte.select_one(f"i.{classe_icone}")
        if icone is None or icone.parent is None:
            return ""
        return Source.texte(icone.parent)[:60]
