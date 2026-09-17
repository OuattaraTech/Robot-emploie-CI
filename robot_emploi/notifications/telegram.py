"""Notification Telegram : l'alerte immédiate, quand l'email attendra."""

from __future__ import annotations

import requests

from ..config import Secrets
from ..journal import obtenir
from ..modeles import Offre
from .. import rapport

_log = obtenir("telegram")

API = "https://api.telegram.org/bot{jeton}/sendMessage"
LIMITE = 4000   # l'API coupe à 4096 ; on garde de la marge


def envoyer_telegram(offres: list[Offre], secrets: Secrets) -> bool:
    if not secrets.telegram_pret:
        _log.debug("Telegram non configuré : envoi ignoré")
        return False

    texte = rapport.telegram(offres)
    morceaux = [texte[i:i + LIMITE] for i in range(0, len(texte), LIMITE)] or [texte]

    for morceau in morceaux:
        try:
            reponse = requests.post(
                API.format(jeton=secrets.telegram_jeton),
                json={
                    "chat_id": secrets.telegram_chat_id,
                    "text": morceau,
                    "parse_mode": "HTML",
                    "disable_web_page_preview": True,
                },
                timeout=20,
            )
        except requests.RequestException as erreur:
            _log.error("Telegram injoignable : %s", erreur)
            return False

        if not reponse.ok:
            _log.error("Telegram a refusé le message : %s", reponse.text[:200])
            return False

    _log.info("notification Telegram envoyée")
    return True
