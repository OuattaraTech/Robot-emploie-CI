"""Socle commun aux sources : récupération de page et lecture JSON-LD."""

from __future__ import annotations

import json
import re
from abc import ABC, abstractmethod
from datetime import date, datetime

from bs4 import BeautifulSoup, Tag

from ..journal import obtenir
from ..modeles import Offre
from ..reseau import AccesRefuse, Navigateur, page_via_navigateur


class Source(ABC):
    """Un site surveillé.

    Une source ne filtre pas et ne dédoublonne pas : elle rend tout ce
    qu'elle trouve. Le tri vient après, dans filtrage.py.
    """

    nom: str = "source"

    def __init__(self, reglages: dict, navigateur: Navigateur):
        self.reglages = reglages or {}
        self.navigateur = navigateur
        self.log = obtenir(self.nom)

    @abstractmethod
    def collecter(self) -> list[Offre]:
        ...

    # ─── Outils partagés ─────────────────────────────────────────────
    def html(self, url: str, attente: str | None = None, **kwargs) -> BeautifulSoup:
        """Rend la page analysée. Passe par un vrai Chromium si la source
        est déclarée « navigateur: true » dans config.yaml, ou si le site
        nous ferme la porte au nez."""
        if self.reglages.get("navigateur"):
            return BeautifulSoup(page_via_navigateur(url, attente), "lxml")
        try:
            reponse = self.navigateur.obtenir(url, **kwargs)
        except AccesRefuse:
            self.log.info("accès direct refusé, seconde tentative via Chromium")
            return BeautifulSoup(page_via_navigateur(url, attente), "lxml")
        return BeautifulSoup(reponse.text, "lxml")

    @staticmethod
    def texte(noeud: Tag | None, selecteur: str | None = None) -> str:
        """Texte propre d'un nœud, ou d'un de ses descendants."""
        if noeud is None:
            return ""
        cible = noeud.select_one(selecteur) if selecteur else noeud
        if cible is None:
            return ""
        return re.sub(r"\s+", " ", cible.get_text(" ", strip=True)).strip()

    @staticmethod
    def date_iso(valeur: str | None) -> date | None:
        if not valeur:
            return None
        valeur = valeur.strip().replace("Z", "+00:00")
        for forme in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"):
            try:
                return datetime.strptime(valeur[:10], forme).date()
            except ValueError:
                continue
        try:
            return datetime.fromisoformat(valeur).date()
        except ValueError:
            return None


def offres_depuis_json_ld(soupe: BeautifulSoup, source: str) -> list[Offre]:
    """Récupère les blocs schema.org/JobPosting d'une page.

    Beaucoup de sites d'emploi en publient pour Google Jobs : quand ils
    sont là, c'est la lecture la plus fiable — elle ne casse pas au
    prochain changement de CSS.
    """
    trouvees: list[Offre] = []

    def aplatir(donnee) -> list[dict]:
        if isinstance(donnee, list):
            return [e for element in donnee for e in aplatir(element)]
        if isinstance(donnee, dict):
            if donnee.get("@type") == "JobPosting":
                return [donnee]
            # Les listes de résultats emballent souvent les offres dans un
            # ItemList ; on descend d'un cran.
            for cle in ("itemListElement", "@graph", "item", "mainEntity"):
                if cle in donnee:
                    return aplatir(donnee[cle])
        return []

    for bloc in soupe.find_all("script", type="application/ld+json"):
        contenu = bloc.string or bloc.get_text()
        if not contenu:
            continue
        try:
            donnee = json.loads(contenu)
        except json.JSONDecodeError:
            continue

        for annonce in aplatir(donnee):
            organisation = annonce.get("hiringOrganization") or {}
            lieu_brut = annonce.get("jobLocation") or {}
            if isinstance(lieu_brut, list):
                lieu_brut = lieu_brut[0] if lieu_brut else {}
            adresse = (lieu_brut or {}).get("address") or {}
            description = re.sub(r"<[^>]+>", " ", str(annonce.get("description", "")))

            trouvees.append(Offre(
                titre=str(annonce.get("title", "")).strip(),
                entreprise=str(organisation.get("name", "")).strip()
                if isinstance(organisation, dict) else str(organisation),
                lieu=" ".join(filter(None, (
                    str(adresse.get("addressLocality", "")),
                    str(adresse.get("addressCountry", ""))
                    if isinstance(adresse.get("addressCountry"), str) else "",
                ))).strip(),
                source=source,
                url=str(annonce.get("url") or annonce.get("@id") or "").strip(),
                description=re.sub(r"\s+", " ", description)[:1500],
                contrat=str(annonce.get("employmentType") or ""),
                date_publication=Source.date_iso(annonce.get("datePosted")),
            ))

    return [o for o in trouvees if o.titre]


def offres_depuis_liens(soupe: BeautifulSoup, source: str, base_url: str,
                        motif_url: str, racine_carte: str = "") -> list[Offre]:
    """Repêchage : construit les offres à partir des liens dont l'adresse
    ressemble à une annonce.

    C'est le filet de sécurité quand ni le JSON-LD ni les sélecteurs
    attendus ne répondent — typiquement après une refonte du site. Moins
    précis (pas d'entreprise ni de date), mais le rapport ne part pas vide.
    """
    from urllib.parse import urljoin

    motif = re.compile(motif_url)
    vues: set[str] = set()
    moisson: list[Offre] = []

    for lien in soupe.find_all("a", href=True):
        href = lien["href"]
        if not motif.search(href):
            continue
        url = urljoin(base_url, href.split("?")[0])
        if url in vues:
            continue

        titre = Source.texte(lien)
        carte = lien.find_parent(racine_carte) if racine_carte else lien.parent
        if len(titre) < 6 and carte is not None:
            titre = Source.texte(carte)[:120]
        if len(titre) < 6:
            continue

        vues.add(url)
        moisson.append(Offre(
            titre=titre[:160],
            source=source,
            url=url,
            description=Source.texte(carte)[:600] if carte is not None else "",
        ))

    return moisson
