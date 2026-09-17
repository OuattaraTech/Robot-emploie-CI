"""JobnetAfrica — la page /jobs/ liste les missions de toute l'Afrique
dans des blocs « ezekia-assignment ». On récupère tout, on filtre le pays
ensuite : c'est plus robuste que de deviner leurs paramètres d'URL.
"""

from __future__ import annotations

from urllib.parse import urljoin

from ..modeles import Offre, normaliser
from .base import Source

DEFAUT = "https://jobnetafrica.com/jobs/"


class JobnetAfrica(Source):
    nom = "jobnetafrica"

    def collecter(self) -> list[Offre]:
        url = self.reglages.get("url", DEFAUT)
        soupe = self.html(url, attente="div.ezekia-assignment")
        blocs = soupe.select("div.ezekia-assignment")
        pays_vises = [normaliser(p) for p in (self.reglages.get("pays") or []) if p]
        moisson: list[Offre] = []

        for bloc in blocs:
            titre = self.texte(bloc, "div.ezekia-assignment-name")
            if not titre:
                continue

            pays = self.texte(bloc, "div.ezekia-assignment-country").removeprefix("Country:").strip()
            if pays_vises and not any(vise in normaliser(pays) for vise in pays_vises):
                continue

            secteur = self.texte(bloc, "div.ezekia-assignment-sector").removeprefix("Sector:").strip()
            metier = self.texte(bloc, "div.ezekia-assignment-job-role").removeprefix("Job Role:").strip()
            contrat = self.texte(bloc, "div.ezekia-assignment-job-type").removeprefix("Job Type:").strip()
            lien = bloc.select_one("div.ezekia-assignment-see-details a")

            moisson.append(Offre(
                titre=titre,
                entreprise="JobnetAfrica",
                lieu=pays,
                source=self.nom,
                url=urljoin(url, lien.get("href", "")) if lien else url,
                description=" · ".join(filter(None, (secteur, metier))),
                contrat=contrat,
            ))

        self.log.info("%d annonces récupérées (%d blocs lus)", len(moisson), len(blocs))
        return moisson
