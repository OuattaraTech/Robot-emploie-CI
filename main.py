#!/usr/bin/env python3
"""Robot Emploi CI — point d'entrée.

    python main.py                     un cycle, puis on s'arrête
    python main.py --boucle            un cycle toutes les six heures
    python main.py --essai             affiche sans envoyer ni mémoriser
    python main.py --sources linkedin  n'interroge que ces sources
    python main.py --test-email        vérifie la configuration SMTP
    python main.py --etat              ce que la mémoire contient
    python main.py --oublier-tout      vide la mémoire (tout reviendra)
"""

from __future__ import annotations

import argparse
import sys
import time
from datetime import datetime, timedelta

from robot_emploi import journal
from robot_emploi.config import ConfigInvalide, charger
from robot_emploi.memoire import Memoire
from robot_emploi.notifications import tester_email
from robot_emploi.robot import Robot
from robot_emploi.sources import REGISTRE

_log = journal.obtenir("main")


def arguments() -> argparse.Namespace:
    analyseur = argparse.ArgumentParser(
        prog="robot-emploi-ci",
        description="Veille automatisée des offres d'emploi ivoiriennes.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    analyseur.add_argument("--boucle", action="store_true",
                           help="tourner en continu, un cycle toutes les N heures")
    analyseur.add_argument("--essai", action="store_true",
                           help="afficher le rapport sans rien envoyer ni mémoriser")
    analyseur.add_argument("--sources", default="",
                           help=f"liste séparée par des virgules parmi : "
                                f"{', '.join(sorted(REGISTRE))}")
    analyseur.add_argument("--config", default=None, help="autre fichier de configuration")
    analyseur.add_argument("--test-email", action="store_true",
                           help="envoyer un message de test et s'arrêter")
    analyseur.add_argument("--etat", action="store_true",
                           help="afficher les statistiques de la mémoire")
    analyseur.add_argument("--oublier-tout", action="store_true",
                           help="vider la mémoire des annonces déjà vues")
    analyseur.add_argument("--verbeux", action="store_true", help="journal détaillé")
    return analyseur.parse_args()


def etat() -> int:
    statistiques = Memoire().statistiques()
    print(f"\n  Annonces mémorisées : {statistiques['total']}")
    print(f"  Cycles terminés     : {statistiques['cycles']}")
    if statistiques["par_source"]:
        print("  Par source :")
        for nom, nombre in statistiques["par_source"].items():
            print(f"    · {nom:<14} {nombre}")
    print()
    return 0


def un_cycle(config, sources: list[str] | None, essai: bool) -> int:
    debut = time.monotonic()
    with Robot(config) as robot:
        bilan = robot.cycle(sources=sources, envoyer=not essai)

    duree = time.monotonic() - debut
    _log.info("cycle terminé en %.0f s", duree)
    if bilan.erreurs:
        for erreur in bilan.erreurs:
            _log.warning("source en échec — %s", erreur)
    # Un cycle dont toutes les sources échouent est un vrai échec : le
    # code de sortie le dit, pour que cron ou systemd puisse alerter.
    return 1 if bilan.erreurs and bilan.recuperees == 0 else 0


def boucle(config, sources: list[str] | None) -> int:
    heures = float(config.planification.get("intervalle_heures", 6))
    _log.info("mode continu : un cycle toutes les %g heures. Ctrl+C pour arrêter.", heures)
    while True:
        try:
            un_cycle(config, sources, essai=False)
        except KeyboardInterrupt:
            _log.info("arrêt demandé")
            return 0
        except Exception as erreur:
            # Le robot doit survivre à une nuit de coupure réseau.
            _log.error("cycle interrompu : %s", erreur, exc_info=True)

        prochain = datetime.now() + timedelta(hours=heures)
        _log.info("prochain cycle à %s", prochain.strftime("%d/%m à %Hh%M"))
        try:
            time.sleep(heures * 3600)
        except KeyboardInterrupt:
            _log.info("arrêt demandé")
            return 0


def main() -> int:
    options = arguments()
    journal.configurer(verbeux=options.verbeux)

    if options.etat:
        return etat()

    if options.oublier_tout:
        memoire = Memoire()
        memoire.reinitialiser()
        memoire.fermer()
        print("Mémoire vidée : les annonces déjà vues reviendront au prochain cycle.")
        return 0

    try:
        config = charger(options.config)
    except ConfigInvalide as erreur:
        _log.error("%s", erreur)
        return 2

    if options.test_email:
        return 0 if tester_email(config.secrets) else 1

    sources = [s.strip() for s in options.sources.split(",") if s.strip()] or None
    if sources:
        inconnues = [s for s in sources if s not in REGISTRE]
        if inconnues:
            _log.error("source(s) inconnue(s) : %s", ", ".join(inconnues))
            return 2

    if options.boucle:
        return boucle(config, sources)
    return un_cycle(config, sources, options.essai)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\nArrêt.")
        sys.exit(130)
