"""Envoi du rapport par SMTP, en HTML avec repli texte et Excel joint."""

from __future__ import annotations

import smtplib
import ssl
from email.message import EmailMessage
from pathlib import Path

from ..config import Secrets
from ..journal import obtenir
from ..modeles import Offre
from .. import rapport

_log = obtenir("email")


def _connexion(secrets: Secrets) -> smtplib.SMTP | smtplib.SMTP_SSL:
    contexte = ssl.create_default_context()
    if secrets.smtp_port == 465:
        serveur = smtplib.SMTP_SSL(secrets.smtp_hote, secrets.smtp_port,
                                   context=contexte, timeout=30)
    else:
        serveur = smtplib.SMTP(secrets.smtp_hote, secrets.smtp_port, timeout=30)
        serveur.starttls(context=contexte)
    serveur.login(secrets.smtp_utilisateur, secrets.smtp_motdepasse)
    return serveur


def envoyer_email(offres: list[Offre], secrets: Secrets,
                  piece_jointe: Path | None = None,
                  statistiques: dict | None = None) -> bool:
    """Envoie le rapport. Rend False sans lever : un email raté ne doit
    pas faire tomber le cycle — l'Excel et Telegram restent valables."""
    if not secrets.email_pret:
        _log.warning("email non configuré (voir .env) : envoi ignoré")
        return False

    message = EmailMessage()
    nombre = len(offres)
    message["Subject"] = (
        f"Robot Emploi CI — {nombre} nouvelle{'s' if nombre > 1 else ''} offre"
        f"{'s' if nombre > 1 else ''}" if nombre
        else "Robot Emploi CI — aucune nouvelle offre"
    )
    message["From"] = secrets.email_expediteur or secrets.smtp_utilisateur
    message["To"] = ", ".join(secrets.email_destinataires)
    message.set_content(rapport.texte(offres))
    message.add_alternative(rapport.html(offres, statistiques), subtype="html")

    if piece_jointe and Path(piece_jointe).exists():
        chemin = Path(piece_jointe)
        message.add_attachment(
            chemin.read_bytes(),
            maintype="application",
            subtype="vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            filename=chemin.name,
        )

    try:
        with _connexion(secrets) as serveur:
            serveur.send_message(message)
    except smtplib.SMTPAuthenticationError:
        _log.error("SMTP : identifiants refusés. Sur Gmail, il faut un "
                   "mot de passe d'application, pas le mot de passe du compte.")
        return False
    except Exception as erreur:
        _log.error("envoi email impossible : %s", erreur)
        return False

    _log.info("email envoyé à %s", ", ".join(secrets.email_destinataires))
    return True


def tester_email(secrets: Secrets) -> bool:
    """Vérifie la configuration SMTP de bout en bout, sans attendre un cycle."""
    if not secrets.email_pret:
        _log.error("configuration SMTP incomplète : remplir .env")
        return False

    message = EmailMessage()
    message["Subject"] = "Robot Emploi CI — test de configuration"
    message["From"] = secrets.email_expediteur or secrets.smtp_utilisateur
    message["To"] = ", ".join(secrets.email_destinataires)
    message.set_content(
        "Si tu lis ceci, l'envoi SMTP du Robot Emploi CI fonctionne.\n"
        "Les rapports d'offres arriveront par ce canal."
    )
    try:
        with _connexion(secrets) as serveur:
            serveur.send_message(message)
    except Exception as erreur:
        _log.error("test SMTP échoué : %s", erreur)
        return False

    _log.info("test SMTP réussi — message envoyé à %s",
              ", ".join(secrets.email_destinataires))
    return True
