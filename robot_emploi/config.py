"""Lecture de config.yaml et des secrets .env, en une seule structure."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

import yaml
from dotenv import load_dotenv

RACINE = Path(__file__).resolve().parent.parent


class ConfigInvalide(RuntimeError):
    """config.yaml manquant, illisible ou incomplet."""


@dataclass
class Secrets:
    smtp_hote: str = ""
    smtp_port: int = 587
    smtp_utilisateur: str = ""
    smtp_motdepasse: str = ""
    email_expediteur: str = ""
    email_destinataires: tuple[str, ...] = ()
    telegram_jeton: str = ""
    telegram_chat_id: str = ""

    @property
    def email_pret(self) -> bool:
        return bool(self.smtp_hote and self.smtp_utilisateur
                    and self.smtp_motdepasse and self.email_destinataires)

    @property
    def telegram_pret(self) -> bool:
        return bool(self.telegram_jeton and self.telegram_chat_id)


@dataclass
class Config:
    profil: dict
    sources: dict
    planification: dict
    sorties: dict
    reseau: dict
    secrets: Secrets

    def source(self, nom: str) -> dict:
        return self.sources.get(nom, {})

    def sources_actives(self) -> list[str]:
        return [nom for nom, reglages in self.sources.items()
                if reglages.get("activee", True)]


def _secrets_depuis_environnement() -> Secrets:
    load_dotenv(RACINE / ".env")
    destinataires = tuple(
        adresse.strip()
        for adresse in os.getenv("EMAIL_DESTINATAIRES", "").split(",")
        if adresse.strip()
    )
    try:
        port = int(os.getenv("SMTP_PORT", "587"))
    except ValueError:
        port = 587
    expediteur = os.getenv("EMAIL_EXPEDITEUR", "") or os.getenv("SMTP_UTILISATEUR", "")
    return Secrets(
        smtp_hote=os.getenv("SMTP_HOTE", ""),
        smtp_port=port,
        smtp_utilisateur=os.getenv("SMTP_UTILISATEUR", ""),
        smtp_motdepasse=os.getenv("SMTP_MOTDEPASSE", ""),
        email_expediteur=expediteur,
        email_destinataires=destinataires,
        telegram_jeton=os.getenv("TELEGRAM_JETON", ""),
        telegram_chat_id=os.getenv("TELEGRAM_CHAT_ID", ""),
    )


def charger(chemin: Path | str | None = None) -> Config:
    chemin = Path(chemin) if chemin else RACINE / "config.yaml"
    if not chemin.exists():
        raise ConfigInvalide(
            f"{chemin} est introuvable. Partir de config.yaml fourni avec le projet."
        )
    try:
        brut = yaml.safe_load(chemin.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as erreur:
        raise ConfigInvalide(f"{chemin} est mal formé : {erreur}") from erreur

    profil = brut.get("profil") or {}
    if not profil.get("intitules"):
        raise ConfigInvalide(
            "profil.intitules est vide : le robot ne saurait pas quoi chercher."
        )

    return Config(
        profil=profil,
        sources=brut.get("sources") or {},
        planification=brut.get("planification") or {},
        sorties=brut.get("sorties") or {},
        reseau=brut.get("reseau") or {},
        secrets=_secrets_depuis_environnement(),
    )
