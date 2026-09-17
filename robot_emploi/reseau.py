"""Accès HTTP : une session polie, des réessais, et un recours navigateur
pour les sites qui refusent les requêtes sans JavaScript."""

from __future__ import annotations

import random
import time

import requests

from .journal import obtenir

_log = obtenir("reseau")

NAVIGATEURS = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, "
    "like Gecko) Version/17.4 Safari/605.1.15",
)


class AccesRefuse(RuntimeError):
    """Le site répond, mais par un mur : 403, 429, page de défi."""


class Navigateur:
    """Session HTTP partagée par toutes les sources.

    Un seul objet pour tout le cycle : les connexions sont réutilisées et
    le délai entre requêtes s'applique globalement, pas par source — c'est
    ce qui évite de marteler quatre sites en même temps.
    """

    def __init__(self, delai: float = 2.5, timeout: int = 25, tentatives: int = 3):
        self.delai = delai
        self.timeout = timeout
        self.tentatives = max(1, tentatives)
        self._derniere_requete = 0.0
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": random.choice(NAVIGATEURS),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7",
            "Upgrade-Insecure-Requests": "1",
        })

    def _patienter(self) -> None:
        ecoule = time.monotonic() - self._derniere_requete
        reste = self.delai - ecoule
        if reste > 0:
            time.sleep(reste)
        self._derniere_requete = time.monotonic()

    def obtenir(self, url: str, **kwargs) -> requests.Response:
        """GET avec réessais. Lève AccesRefuse quand le site nous bloque."""
        derniere_erreur: Exception | None = None
        for essai in range(1, self.tentatives + 1):
            self._patienter()
            try:
                reponse = self.session.get(url, timeout=self.timeout, **kwargs)
            except requests.RequestException as erreur:
                derniere_erreur = erreur
                _log.debug("essai %d/%d sur %s : %s", essai, self.tentatives, url, erreur)
                time.sleep(2 * essai)
                continue

            if reponse.status_code in (403, 429, 503):
                # Inutile d'insister : ces codes viennent d'un pare-feu
                # applicatif, pas d'un incident passager.
                raise AccesRefuse(f"{reponse.status_code} sur {url}")
            if reponse.status_code >= 500:
                derniere_erreur = RuntimeError(f"{reponse.status_code} sur {url}")
                time.sleep(2 * essai)
                continue

            reponse.raise_for_status()
            return reponse

        raise RuntimeError(f"échec après {self.tentatives} tentatives : {derniere_erreur}")

    def fermer(self) -> None:
        self.session.close()


def page_via_navigateur(url: str, attente_selecteur: str | None = None,
                        timeout: int = 45) -> str:
    """Ouvre l'URL dans un vrai Chromium et rend le HTML une fois la page
    peuplée. Seule façon de lire les sites derrière Cloudflare ou rendus
    côté client.

    Nécessite Playwright :
        pip install playwright && playwright install chromium
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as erreur:  # pragma: no cover - dépend de l'install
        raise AccesRefuse(
            "Playwright n'est pas installé : "
            "pip install playwright && playwright install chromium"
        ) from erreur

    with sync_playwright() as pilote:
        chromium = pilote.chromium.launch(headless=True)
        contexte = chromium.new_context(
            user_agent=random.choice(NAVIGATEURS),
            locale="fr-FR",
            viewport={"width": 1366, "height": 900},
        )
        page = contexte.new_page()
        try:
            page.goto(url, timeout=timeout * 1000, wait_until="domcontentloaded")
            if attente_selecteur:
                try:
                    page.wait_for_selector(attente_selecteur, timeout=timeout * 1000)
                except Exception:
                    # Le sélecteur peut ne jamais venir (zéro résultat) :
                    # on rend quand même la page, la source tranchera.
                    _log.debug("sélecteur %s jamais apparu sur %s",
                               attente_selecteur, url)
            page.wait_for_timeout(1500)
            return page.content()
        finally:
            contexte.close()
            chromium.close()
