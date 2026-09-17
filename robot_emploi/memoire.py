"""Mémoire des annonces déjà vues.

Sans elle, chaque rapport rejouerait les mêmes offres toutes les six
heures. Une base SQLite d'un seul fichier suffit : pas de serveur à
faire tourner, et l'historique survit aux redémarrages.
"""

from __future__ import annotations

import sqlite3
from contextlib import closing
from datetime import datetime, timedelta
from pathlib import Path

from .journal import obtenir
from .modeles import Offre

_log = obtenir("memoire")

SCHEMA = """
CREATE TABLE IF NOT EXISTS offres_vues (
    empreinte    TEXT PRIMARY KEY,
    titre        TEXT NOT NULL,
    entreprise   TEXT,
    lieu         TEXT,
    source       TEXT,
    url          TEXT,
    score        INTEGER,
    vue_le       TEXT NOT NULL,
    envoyee_le   TEXT
);
CREATE INDEX IF NOT EXISTS idx_vue_le ON offres_vues (vue_le);
CREATE INDEX IF NOT EXISTS idx_source ON offres_vues (source);

CREATE TABLE IF NOT EXISTS cycles (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    demarre_le   TEXT NOT NULL,
    termine_le   TEXT,
    recuperees   INTEGER DEFAULT 0,
    retenues     INTEGER DEFAULT 0,
    nouvelles    INTEGER DEFAULT 0,
    erreurs      TEXT
);
"""


class Memoire:
    def __init__(self, chemin: Path | str = "donnees/offres.sqlite3"):
        self.chemin = Path(chemin)
        self.chemin.parent.mkdir(parents=True, exist_ok=True)
        self.connexion = sqlite3.connect(self.chemin)
        self.connexion.row_factory = sqlite3.Row
        with closing(self.connexion.cursor()) as curseur:
            curseur.executescript(SCHEMA)
        self.connexion.commit()

    # ─── Doublons ────────────────────────────────────────────────────
    def deja_vue(self, offre: Offre) -> bool:
        with closing(self.connexion.cursor()) as curseur:
            curseur.execute(
                "SELECT 1 FROM offres_vues WHERE empreinte = ?", (offre.empreinte,)
            )
            return curseur.fetchone() is not None

    def nouvelles(self, offres: list[Offre]) -> list[Offre]:
        """Ne rend que ce qui n'est jamais passé dans un rapport.

        Le dédoublonnage se fait aussi à l'intérieur du lot : la même
        annonce peut remonter de deux recherches LinkedIn différentes.
        """
        if not offres:
            return []
        vues_ce_tour: set[str] = set()
        retenues: list[Offre] = []
        for offre in offres:
            empreinte = offre.empreinte
            if empreinte in vues_ce_tour or self.deja_vue(offre):
                continue
            vues_ce_tour.add(empreinte)
            retenues.append(offre)
        _log.debug("%d offres reçues, %d nouvelles", len(offres), len(retenues))
        return retenues

    # ─── Enregistrement ──────────────────────────────────────────────
    def enregistrer(self, offres: list[Offre], envoyees: bool = True) -> int:
        maintenant = datetime.now().isoformat(timespec="seconds")
        lignes = [
            (o.empreinte, o.titre, o.entreprise, o.lieu, o.source, o.url,
             o.score, maintenant, maintenant if envoyees else None)
            for o in offres
        ]
        with closing(self.connexion.cursor()) as curseur:
            curseur.executemany(
                """INSERT OR IGNORE INTO offres_vues
                   (empreinte, titre, entreprise, lieu, source, url, score,
                    vue_le, envoyee_le)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                lignes,
            )
            ajoutees = curseur.rowcount
        self.connexion.commit()
        return ajoutees

    # ─── Cycles ──────────────────────────────────────────────────────
    def ouvrir_cycle(self) -> int:
        with closing(self.connexion.cursor()) as curseur:
            curseur.execute(
                "INSERT INTO cycles (demarre_le) VALUES (?)",
                (datetime.now().isoformat(timespec="seconds"),),
            )
            self.connexion.commit()
            return int(curseur.lastrowid)

    def fermer_cycle(self, cycle_id: int, recuperees: int, retenues: int,
                     nouvelles: int, erreurs: list[str] | None = None) -> None:
        with closing(self.connexion.cursor()) as curseur:
            curseur.execute(
                """UPDATE cycles
                   SET termine_le = ?, recuperees = ?, retenues = ?,
                       nouvelles = ?, erreurs = ?
                   WHERE id = ?""",
                (datetime.now().isoformat(timespec="seconds"), recuperees,
                 retenues, nouvelles, "; ".join(erreurs or []) or None, cycle_id),
            )
        self.connexion.commit()

    # ─── Entretien ───────────────────────────────────────────────────
    def statistiques(self) -> dict:
        with closing(self.connexion.cursor()) as curseur:
            curseur.execute("SELECT COUNT(*) FROM offres_vues")
            total = curseur.fetchone()[0]
            curseur.execute(
                "SELECT source, COUNT(*) FROM offres_vues GROUP BY source "
                "ORDER BY COUNT(*) DESC"
            )
            par_source = dict(curseur.fetchall())
            curseur.execute("SELECT COUNT(*) FROM cycles WHERE termine_le IS NOT NULL")
            cycles = curseur.fetchone()[0]
        return {"total": total, "par_source": par_source, "cycles": cycles}

    def purger(self, jours: int = 90) -> int:
        """Oublie les annonces trop vieilles : au-delà de trois mois, une
        offre republiée est une vraie nouvelle offre."""
        limite = (datetime.now() - timedelta(days=jours)).isoformat(timespec="seconds")
        with closing(self.connexion.cursor()) as curseur:
            curseur.execute("DELETE FROM offres_vues WHERE vue_le < ?", (limite,))
            supprimees = curseur.rowcount
        self.connexion.commit()
        if supprimees:
            _log.info("mémoire purgée : %d annonces de plus de %d jours",
                      supprimees, jours)
        return supprimees

    def reinitialiser(self) -> None:
        with closing(self.connexion.cursor()) as curseur:
            curseur.execute("DELETE FROM offres_vues")
            curseur.execute("DELETE FROM cycles")
        self.connexion.commit()
        _log.info("mémoire vidée")

    def fermer(self) -> None:
        self.connexion.close()

    def __enter__(self) -> "Memoire":
        return self

    def __exit__(self, *_) -> None:
        self.fermer()
