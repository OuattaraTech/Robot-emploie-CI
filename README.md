# Robot Emploi CI

Un robot qui surveille en continu les sites d'emploi ivoiriens et envoie par
email les offres qui correspondent à un profil précis.

Chercher un emploi en Côte d'Ivoire, c'est visiter les mêmes sites plusieurs
fois par jour et relire les mêmes annonces. Ce robot le fait à la place du
candidat, vingt-quatre heures sur vingt-quatre : il parcourt **LinkedIn**,
**Novojob** et **JobnetAfrica**, filtre chaque annonce selon le
profil et les compétences visées, écarte celles déjà vues, puis compose toutes
les six heures un rapport envoyé par email — avec, pour chaque offre, le lien
direct pour postuler. Les résultats partent aussi en Excel et en notification
Telegram.

---

## Démarrer en cinq minutes

```bash
cd "Robo emploie CI"

python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env        # puis remplir SMTP et, si voulu, Telegram
nano .env

python main.py --essai      # un cycle à blanc : rien n'est envoyé
```

Si le rapport affiché ressemble à ce qu'on cherche :

```bash
python main.py              # un vrai cycle : email + Excel + Telegram
python main.py --boucle     # en continu, un rapport toutes les six heures
```

---

## Les commandes

| Commande | Effet |
|---|---|
| `python main.py` | un cycle complet, puis arrêt |
| `python main.py --boucle` | un cycle toutes les six heures, sans fin |
| `python main.py --essai` | affiche le rapport sans rien envoyer ni mémoriser |
| `python main.py --sources linkedin,novojob` | n'interroge que ces sources |
| `python main.py --test-email` | envoie un message de test et s'arrête |
| `python main.py --etat` | ce que la mémoire contient |
| `python main.py --oublier-tout` | vide la mémoire : tout redeviendra « nouveau » |
| `python main.py --verbeux` | journal détaillé, utile quand une source mollit |

---

## Régler le robot

Tout se passe dans **`config.yaml`** — c'est le seul fichier à toucher pour
changer ce que le robot cherche.

```yaml
profil:
  intitules:   [developpeur, data analyst, agroeconomiste]   # ce qu'on vise
  competences: [python, react, sql, power bi]                # ce qui fait monter le score
  exclusions:  [chauffeur, televendeur]                      # éliminatoire dans le titre
  lieux:       [abidjan, yamoussoukro, remote]               # hors zone = malus
  score_minimum: 8                                           # seuil d'entrée au rapport
```

**Le rapport est trop bavard ?** Monter `score_minimum` à 12 ou 15.
**Il rate des offres ?** Le descendre à 5, ou enrichir `intitules`.

### Comment le score est calculé

| Signal | Points |
|---|---|
| un intitulé visé dans le **titre** | +10 |
| un intitulé visé dans le corps de l'annonce | +3 |
| chaque compétence trouvée | +4 (plafonné à 16) |
| lieu accepté | +5 |
| lieu hors cible | −4 |
| mot d'exclusion dans le titre | **éliminée**, quel que soit le reste |

Chaque offre du rapport affiche *pourquoi* elle remonte : c'est ce qui permet
de corriger le tir en une minute plutôt que de deviner.

---

## Les secrets

Ils vivent dans `.env`, jamais dans `config.yaml`, et `.env` n'est pas versionné.

**Email (Gmail).** Le mot de passe habituel ne marche pas : il faut un
*mot de passe d'application*, sur https://myaccount.google.com/apppasswords
(la validation en deux étapes doit être active au préalable).

**Telegram (facultatif).** Jeton via [@BotFather](https://t.me/BotFather)
(`/newbot`), identifiant de discussion via [@userinfobot](https://t.me/userinfobot).
Laisser les deux vides désactive proprement le canal.

Vérifier que tout est branché :

```bash
python main.py --test-email
```

---

## Les sources

Trois sites, tous vérifiés en conditions réelles le **17 septembre 2026**.

| Source | Accès | Volume constaté |
|---|---|---|
| **LinkedIn** | API publique des offres, sans compte ni cookie | 40 annonces par cycle |
| **Novojob** | pages publiques, HTTP simple | 68 annonces par cycle |
| **JobnetAfrica** | page publique `/jobs/`, filtrée sur le pays | postes internationaux, volume faible |

**LinkedIn** porte l'essentiel du rapport. Chaque mot-clé de `recherches` est
une recherche à part entière ; le dédoublonnage se charge des annonces qui
remontent dans plusieurs.

```yaml
linkedin:
  recherches: ["développeur", "developer", "data analyst", "agro"]
  lieu: "Côte d'Ivoire"
  pages: 2               # 25 annonces par page et par mot-clé
  anciennete: "r604800"  # 7 jours — r86400 pour les dernières 24 h
```

**Novojob** se cible par rubrique métier. Le catalogue complet est sur
`novojob.com/cote-d-ivoire/offres-d-emploi/offres-par-fonction` ; on ajoute
autant d'adresses qu'on veut, le robot les enchaîne.

```yaml
novojob:
  urls:
    - "https://www.novojob.com/cote-d-ivoire/offres-d-emploi"
    - ".../offres-par-fonction/365-informatique-systemes-d-information-internet"
```

### Deux sites écartés, et pourquoi

**emploi.ci** est passé sous un challenge Cloudflare Turnstile qui ne cède ni en
Chromium headless, ni en fenêtre réelle avec profil persistant. Même
`/robots.txt` répond 403 : le blocage est au bord du réseau, pas dans la page.
Passer outre demanderait un service de résolution de captcha — fragile, payant,
et hostile envers le site. **Novojob couvre le même gisement d'annonces
ivoiriennes**, et se lit sans contorsion.

**afriworket.com** est *Afriwork Ethiopia* — numéros +251, annonces
éthiopiennes, listes réservées aux comptes connectés. Ce n'était pas une source
ivoirienne.

### Ajouter un site

Écrire un module dans `robot_emploi/sources/`, sur le modèle de `novojob.py`
(le plus classique : des cartes HTML à parcourir), puis l'inscrire dans
`sources/__init__.py`. Une source ne filtre ni ne dédoublonne : elle rend tout
ce qu'elle trouve, le reste du robot s'en charge.

Si le site refuse les requêtes simples, `Source.html()` retente
automatiquement dans un vrai Chromium — à condition que Playwright soit là :

```bash
pip install playwright && playwright install chromium
```

---

## Faire tourner le robot en permanence

### Sur GitHub Actions — recommandé, gratuit, aucune machine à allumer

Le dépôt embarque `.github/workflows/veille.yml` : GitHub exécute un cycle
toutes les six heures sur ses propres serveurs. La Côte d'Ivoire étant à UTC+0
toute l'année, les rapports tombent à **00 h, 06 h, 12 h et 18 h** heure locale.

Une seule chose à faire, une fois : déposer les secrets dans
**Settings → Secrets and variables → Actions → New repository secret**.

| Secret | Valeur |
|---|---|
| `SMTP_HOTE` | `smtp.gmail.com` |
| `SMTP_PORT` | `587` |
| `SMTP_UTILISATEUR` | ton adresse Gmail |
| `SMTP_MOTDEPASSE` | le **mot de passe d'application**, pas celui du compte |
| `EMAIL_EXPEDITEUR` | ton adresse Gmail |
| `EMAIL_DESTINATAIRES` | où recevoir les rapports, séparés par des virgules |
| `TELEGRAM_JETON` | facultatif |
| `TELEGRAM_CHAT_ID` | facultatif |

Onglet **Actions → Veille emploi → Run workflow** déclenche un cycle
immédiatement, sans attendre la prochaine échéance.

**La mémoire des annonces vues** est rangée dans le cache GitHub entre deux
cycles. Si le cache est purgé — ça arrive après une longue inactivité — un
seul rapport rejoue des offres déjà vues, puis tout repart normalement.

**Un piège à connaître :** GitHub désactive les workflows planifiés d'un dépôt
resté **60 jours sans le moindre commit**, et prévient par email. Un commit,
même trivial, remet le compteur à zéro.

### Sur ta propre machine — si elle reste allumée

Avec cron :

```cron
0 */6 * * * cd "/home/ouattara/Documents/Robo emploie CI" && .venv/bin/python main.py >> journaux/cron.log 2>&1
```

Avec systemd, qui redémarre tout seul après une coupure —
`~/.config/systemd/user/robot-emploi.service` :

```ini
[Unit]
Description=Robot Emploi CI
After=network-online.target

[Service]
Type=simple
WorkingDirectory=/home/ouattara/Documents/Robo emploie CI
ExecStart=/home/ouattara/Documents/Robo emploie CI/.venv/bin/python main.py --boucle
Restart=always
RestartSec=300

[Install]
WantedBy=default.target
```

```bash
systemctl --user daemon-reload
systemctl --user enable --now robot-emploi
systemctl --user status robot-emploi
```

---

## Ce que le robot produit

```
donnees/offres.sqlite3     mémoire des annonces déjà vues, et journal des cycles
exports/offres_*.xlsx      un classeur par rapport, liens cliquables, filtres actifs
journaux/robot.log         historique complet, tournant sur cinq fichiers
```

La mémoire est ce qui empêche la même annonce de revenir quatre fois par jour.
Une annonce y reste **90 jours** ; passé ce délai, une offre republiée compte à
nouveau comme neuve — ce qui est presque toujours le cas dans les faits.

---

## Comment c'est construit

```
main.py                      ligne de commande, boucle des six heures
config.yaml                  profil, sources, planification
robot_emploi/
  robot.py                   le cycle : récolter → filtrer → dédoublonner → prévenir
  config.py                  config.yaml + .env en une seule structure
  modeles.py                 l'offre, et son empreinte anti-doublon
  reseau.py                  session HTTP polie, réessais, recours Chromium
  filtrage.py                le score, et ce qui le justifie
  memoire.py                 SQLite : annonces vues, cycles, purge
  export_excel.py            le classeur
  rapport.py                 le rapport en HTML, en texte, en Telegram
  sources/                   linkedin.py, novojob.py, jobnetafrica.py
  notifications/             email SMTP, Telegram
```

Un principe traverse tout le code : **aucune étape ne fait tomber les autres**.
Une source bloquée est notée et sautée ; un email refusé laisse l'Excel et
Telegram partir ; un cycle qui explose en mode `--boucle` est journalisé, et le
suivant part six heures plus tard comme si de rien n'était.

---

## Dépannage

| Symptôme | Cause la plus fréquente |
|---|---|
| `SMTP : identifiants refusés` | mot de passe du compte au lieu du mot de passe d'application |
| Zéro offre retenue | `score_minimum` trop haut, ou `intitules` trop étroits |
| Les mêmes offres reviennent | la mémoire a été vidée, ou le fichier `donnees/offres.sqlite3` a disparu |
| Une source rend 0 annonce du jour au lendemain | le site a été refondu : ajuster les sélecteurs de son module |

---

Ouattara Yaya — [ouattaratech.pages.dev](https://ouattaratech.pages.dev)
