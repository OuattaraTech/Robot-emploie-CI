"""Le cycle complet : récolter, filtrer, oublier les doublons, prévenir.

Un cycle ne s'interrompt jamais à cause d'une source. Un site en panne,
bloqué ou refondu produit un avertissement dans le rapport ; les trois
autres partent quand même.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from . import rapport
from .config import Config
from .export_excel import exporter
from .filtrage import Filtre
from .journal import obtenir
from .memoire import Memoire
from .modeles import Offre
from .notifications import envoyer_email, envoyer_telegram
from .reseau import Navigateur
from .sources import construire

_log = obtenir("robot")


@dataclass
class Bilan:
    recuperees: int = 0
    retenues: int = 0
    nouvelles: int = 0
    par_source: dict[str, int] = field(default_factory=dict)
    erreurs: list[str] = field(default_factory=list)
    fichier_excel: Path | None = None
    email_envoye: bool = False
    telegram_envoye: bool = False

    def resume(self) -> str:
        detail = ", ".join(f"{nom} {n}" for nom, n in self.par_source.items())
        ligne = (f"{self.recuperees} annonces lues ({detail}) → "
                 f"{self.retenues} au profil → {self.nouvelles} nouvelles")
        if self.erreurs:
            ligne += f" — {len(self.erreurs)} source(s) en échec"
        return ligne


class Robot:
    def __init__(self, config: Config, base: Path | str = "donnees/offres.sqlite3"):
        self.config = config
        self.memoire = Memoire(base)
        self.filtre = Filtre(config.profil)
        reglages = config.reseau
        self.navigateur = Navigateur(
            delai=float(reglages.get("delai_entre_requetes", 2.5)),
            timeout=int(reglages.get("timeout", 25)),
            tentatives=int(reglages.get("tentatives", 3)),
        )

    # ─── Étapes ──────────────────────────────────────────────────────
    def recolter(self, sources: list[str] | None = None) -> tuple[list[Offre], dict, list[str]]:
        noms = sources or self.config.sources_actives()
        moisson: list[Offre] = []
        par_source: dict[str, int] = {}
        erreurs: list[str] = []

        for nom in noms:
            _log.info("── %s ──", nom)
            try:
                source = construire(nom, self.config.source(nom), self.navigateur)
                trouvees = source.collecter()
            except Exception as erreur:              # une source ne fait pas tomber le cycle
                _log.error("%s : %s", nom, erreur)
                erreurs.append(f"{nom} : {erreur}")
                par_source[nom] = 0
                continue

            moisson.extend(trouvees)
            par_source[nom] = len(trouvees)

        return moisson, par_source, erreurs

    def cycle(self, sources: list[str] | None = None, envoyer: bool = True) -> Bilan:
        cycle_id = self.memoire.ouvrir_cycle()
        bilan = Bilan()

        moisson, bilan.par_source, bilan.erreurs = self.recolter(sources)
        bilan.recuperees = len(moisson)

        retenues = self.filtre.retenir(moisson)
        bilan.retenues = len(retenues)

        nouvelles = self.memoire.nouvelles(retenues)
        plafond = int(self.config.planification.get("max_offres_par_rapport", 40))
        nouvelles = nouvelles[:plafond]
        bilan.nouvelles = len(nouvelles)
        _log.info(bilan.resume())

        sorties = self.config.sorties
        if nouvelles and envoyer and sorties.get("excel", True):
            bilan.fichier_excel = exporter(
                nouvelles, sorties.get("dossier_exports", "exports")
            )

        if envoyer:
            statistiques = {
                **self.memoire.statistiques(),
                "intervalle": self.config.planification.get("intervalle_heures", 6),
            }
            if sorties.get("email", True):
                bilan.email_envoye = envoyer_email(
                    nouvelles, self.config.secrets, bilan.fichier_excel, statistiques
                )
            # Rien de neuf : inutile de faire vibrer le téléphone.
            if sorties.get("telegram", True) and nouvelles:
                bilan.telegram_envoye = envoyer_telegram(nouvelles, self.config.secrets)

            self.memoire.enregistrer(nouvelles, envoyees=True)
        else:
            _log.info("mode essai : ni fichier, ni envoi, ni mémorisation")
            print()
            print(rapport.texte(nouvelles))

        self.memoire.fermer_cycle(cycle_id, bilan.recuperees, bilan.retenues,
                                  bilan.nouvelles, bilan.erreurs)
        self.memoire.purger(jours=90)
        return bilan

    def fermer(self) -> None:
        self.navigateur.fermer()
        self.memoire.fermer()

    def __enter__(self) -> "Robot":
        return self

    def __exit__(self, *_) -> None:
        self.fermer()
