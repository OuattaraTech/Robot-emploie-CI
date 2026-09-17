"""Décide si une annonce mérite d'arriver dans la boîte mail.

Le score dit à quel point l'offre ressemble au profil visé :
  · un intitulé dans le TITRE          → beaucoup (le titre ne ment pas)
  · un intitulé dans le corps          → un peu
  · une compétence, où qu'elle soit    → un peu, et ça s'additionne
  · un lieu accepté                    → bonus
  · aucun lieu reconnu                 → malus, sans éliminer
  · un mot d'exclusion dans le titre   → éliminée, quel que soit le score
"""

from __future__ import annotations

from .journal import obtenir
from .modeles import Offre, normaliser

_log = obtenir("filtrage")

POIDS_INTITULE_TITRE = 10
POIDS_INTITULE_CORPS = 3
POIDS_COMPETENCE = 4
PLAFOND_COMPETENCES = 16   # cinq compétences ne doivent pas écraser le reste
BONUS_LIEU = 5
MALUS_LIEU_INCONNU = 4


class Filtre:
    def __init__(self, profil: dict):
        self.intitules = [normaliser(m) for m in profil.get("intitules", []) if m]
        self.competences = [normaliser(m) for m in profil.get("competences", []) if m]
        self.exclusions = [normaliser(m) for m in profil.get("exclusions", []) if m]
        self.lieux = [normaliser(m) for m in profil.get("lieux", []) if m]
        self.score_minimum = int(profil.get("score_minimum", 8))

    def _exclue(self, titre_normalise: str) -> str | None:
        for mot in self.exclusions:
            if mot in titre_normalise:
                return mot
        return None

    def evaluer(self, offre: Offre) -> Offre:
        """Remplit offre.score et offre.motifs. Rend la même offre."""
        titre = normaliser(offre.titre)
        texte = offre.texte_recherchable
        motifs: list[str] = []
        score = 0

        mot_exclu = self._exclue(titre)
        if mot_exclu:
            offre.score = -1
            offre.motifs = [f"écartée : « {mot_exclu} » dans le titre"]
            return offre

        touches_titre = [m for m in self.intitules if m in titre]
        if touches_titre:
            score += POIDS_INTITULE_TITRE
            motifs.append(f"intitulé : {touches_titre[0]}")
        else:
            touches_corps = [m for m in self.intitules if m in texte]
            if touches_corps:
                score += POIDS_INTITULE_CORPS
                motifs.append(f"intitulé cité : {touches_corps[0]}")

        touches_competences = [m for m in self.competences if m in texte]
        if touches_competences:
            score += min(POIDS_COMPETENCE * len(touches_competences),
                         PLAFOND_COMPETENCES)
            motifs.append("compétences : " + ", ".join(touches_competences[:5]))

        if self.lieux:
            lieu_texte = normaliser(f"{offre.lieu} {offre.description}")
            if any(lieu in lieu_texte for lieu in self.lieux):
                score += BONUS_LIEU
                motifs.append(f"lieu : {offre.lieu or 'compatible'}")
            else:
                score -= MALUS_LIEU_INCONNU
                motifs.append(f"lieu hors cible : {offre.lieu or 'non précisé'}")

        offre.score = score
        offre.motifs = motifs
        return offre

    def retenir(self, offres: list[Offre]) -> list[Offre]:
        """Évalue tout le lot et rend les offres au-dessus du seuil, les
        meilleures d'abord."""
        gardees: list[Offre] = []
        ecartees = 0
        for offre in offres:
            self.evaluer(offre)
            if offre.score >= self.score_minimum:
                gardees.append(offre)
            else:
                ecartees += 1
        gardees.sort(key=lambda o: (-o.score, o.titre))
        _log.info("filtrage : %d retenues, %d écartées (seuil %d)",
                  len(gardees), ecartees, self.score_minimum)
        return gardees
