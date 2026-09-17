"""Mise en forme du rapport : une version HTML pour la boîte mail, une
version texte pour les clients qui refusent le HTML, une version courte
pour Telegram.

La règle de composition : chaque offre porte son bouton « Postuler ».
Le rapport doit se lire sur un téléphone, pouce en main, sans zoomer.
"""

from __future__ import annotations

from datetime import datetime
from html import escape

from .modeles import Offre

MARINE = "#1F3A5F"
OR = "#C8A24A"
ARDOISE = "#5A6472"


def _entete_offre(offre: Offre) -> str:
    details = " · ".join(filter(None, (
        escape(offre.entreprise or ""),
        escape(offre.lieu or ""),
        escape(offre.contrat or ""),
    )))
    date = (f"Publiée le {offre.date_publication:%d/%m/%Y}"
            if offre.date_publication else "")
    return details + (f" · {date}" if date else "")


def _carte_html(offre: Offre, rang: int) -> str:
    motifs = escape(" · ".join(offre.motifs)) if offre.motifs else ""
    bouton = (
        f'<a href="{escape(offre.url)}" '
        f'style="display:inline-block;background:{MARINE};color:#ffffff;'
        f'text-decoration:none;padding:10px 18px;border-radius:6px;'
        f'font-size:14px;font-weight:600;">Postuler →</a>'
    ) if offre.url else ""

    return f"""
    <tr><td style="padding:0 0 14px 0;">
      <table width="100%" cellpadding="0" cellspacing="0" role="presentation"
             style="background:#ffffff;border:1px solid #E4E7EC;border-radius:10px;">
        <tr><td style="padding:18px 20px;">
          <div style="font-size:12px;color:{OR};font-weight:700;letter-spacing:.06em;
                      text-transform:uppercase;">
            {rang}. {escape(offre.source)} · score {offre.score}
          </div>
          <div style="font-size:17px;font-weight:700;color:{MARINE};margin:6px 0 4px;">
            {escape(offre.titre)}
          </div>
          <div style="font-size:14px;color:{ARDOISE};margin-bottom:10px;">
            {_entete_offre(offre)}
          </div>
          {f'<div style="font-size:12px;color:{ARDOISE};margin-bottom:14px;">{motifs}</div>' if motifs else ''}
          {bouton}
        </td></tr>
      </table>
    </td></tr>"""


def html(offres: list[Offre], statistiques: dict | None = None) -> str:
    statistiques = statistiques or {}
    maintenant = datetime.now()
    cartes = "".join(_carte_html(o, i) for i, o in enumerate(offres, 1))

    par_source: dict[str, int] = {}
    for offre in offres:
        par_source[offre.source] = par_source.get(offre.source, 0) + 1
    repartition = " · ".join(f"{nom} : {nombre}" for nom, nombre in par_source.items())

    corps = cartes or f"""
    <tr><td style="padding:30px;text-align:center;color:{ARDOISE};font-size:15px;">
      Aucune nouvelle offre correspondant au profil sur ce cycle.<br>
      Les sites ont bien été consultés — il n'y avait rien de neuf.
    </td></tr>"""

    return f"""<!doctype html>
<html lang="fr"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="margin:0;padding:0;background:#F4F6F8;
             font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0" role="presentation">
    <tr><td align="center" style="padding:24px 12px;">
      <table width="100%" cellpadding="0" cellspacing="0" role="presentation"
             style="max-width:620px;">

        <tr><td style="background:{MARINE};border-radius:10px;padding:22px 24px;">
          <div style="color:{OR};font-size:12px;letter-spacing:.14em;
                      text-transform:uppercase;font-weight:700;">Robot Emploi CI</div>
          <div style="color:#ffffff;font-size:22px;font-weight:700;margin-top:6px;">
            {len(offres)} nouvelle{'s' if len(offres) > 1 else ''} offre{'s' if len(offres) > 1 else ''}
          </div>
          <div style="color:#C6D0DC;font-size:13px;margin-top:4px;">
            Cycle du {maintenant:%d/%m/%Y à %Hh%M}{f' — {repartition}' if repartition else ''}
          </div>
        </td></tr>

        <tr><td style="height:18px;"></td></tr>
        {corps}

        <tr><td style="padding:18px 6px 0;color:{ARDOISE};font-size:12px;
                       line-height:1.6;border-top:1px solid #E4E7EC;">
          Rapport automatique — prochain passage dans {statistiques.get('intervalle', 6)} heures.<br>
          {statistiques.get('total', 0)} annonces déjà mémorisées : aucune ne reviendra deux fois.
        </td></tr>

      </table>
    </td></tr>
  </table>
</body></html>"""


def texte(offres: list[Offre]) -> str:
    if not offres:
        return ("Robot Emploi CI — aucune nouvelle offre sur ce cycle.\n"
                "Les sites ont été consultés, il n'y avait rien de neuf.")

    lignes = [
        f"ROBOT EMPLOI CI — {len(offres)} nouvelle(s) offre(s)",
        f"Cycle du {datetime.now():%d/%m/%Y à %Hh%M}",
        "=" * 58, "",
    ]
    for rang, offre in enumerate(offres, 1):
        lignes += [
            f"{rang}. {offre.titre}  (score {offre.score})",
            f"   {offre.entreprise or '—'} · {offre.lieu or '—'} · {offre.source}",
            f"   {offre.url}" if offre.url else "   (pas de lien direct)",
            "",
        ]
    return "\n".join(lignes)


def telegram(offres: list[Offre], maximum: int = 10) -> str:
    """Message court : Telegram plafonne à 4096 caractères."""
    if not offres:
        return "🤖 <b>Robot Emploi CI</b>\nAucune nouvelle offre sur ce cycle."

    lignes = [f"🤖 <b>Robot Emploi CI</b> — {len(offres)} nouvelle(s) offre(s)", ""]
    for offre in offres[:maximum]:
        titre = escape(offre.titre)
        entreprise = escape(offre.entreprise or offre.source)
        lieu = escape(offre.lieu or "")
        lien = f'<a href="{escape(offre.url)}">Postuler</a>' if offre.url else ""
        lignes.append(f"▸ <b>{titre}</b>\n   {entreprise}{f' · {lieu}' if lieu else ''} · {lien}")

    if len(offres) > maximum:
        lignes.append(f"\n… et {len(offres) - maximum} autre(s) dans l'email et l'Excel.")
    return "\n".join(lignes)
