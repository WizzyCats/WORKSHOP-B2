# WORKSHOP-B2

================== PARTIE MR LARBIN ==================

# Mr Larbin — Tamagotchi ESP8266

Tamagotchi maison sur ESP8266 (NodeMCU V3) + écran TFT ST7735 128×160, avec 3 boutons et un buzzer.

## Fichiers du projet

- `MrLarbin.ino` — le sketch principal (logique du jeu, écran, boutons, buzzer)
- `images.h` — les 4 images du personnage, converties en tableaux de pixels RGB565

## Câblage final

| Composant       | Pin ESP8266 | Remarque |
|-----------------|-------------|----------|
| Écran GND       | GND         | |
| Écran VCC       | 3V3         | |
| Écran RES       | TX (GPIO1)  | déplacé depuis D3 : D3=GPIO0 sert au boot |
| Écran DC        | D4 (GPIO2)  | |
| Écran CS        | D8 (GPIO15) | |
| Écran BLK       | D6 (GPIO12) | rétroéclairage |
| Écran SCL       | D5 (GPIO14) | horloge SPI matérielle |
| Écran SDA       | D7 (GPIO13) | données SPI matérielle |
| Bouton MANGER   | D0 (GPIO16) | câblé vers **3V3** (pas GND), pull-down interne |
| Bouton DORMIR   | D1 (GPIO5)  | câblé vers GND, pull-up interne |
| Bouton TRAVAIL  | D2 (GPIO4)  | câblé vers GND, pull-up interne |
| Buzzer +        | RX (GPIO3)  | |
| Buzzer −        | GND         | |

### Pourquoi ce câblage un peu particulier ?

- **RES sur TX plutôt que D3** : D3 = GPIO0, un pin que l'ESP8266 utilise pour décider s'il démarre en mode programmation ou en mode normal. Y brancher le reset de l'écran empêchait l'upload du code (erreur `Timed out waiting for packet header`).
- **SCL sur D5, BLK sur D6** : le SPI matériel de l'ESP8266 (rapide) impose son horloge sur D5. En dessin logiciel (n'importe quels pins, mais lent), afficher une image 128×160 prenait trop de temps et déclenchait un reset watchdog (l'écran affichait l'image à moitié, flashait en blanc, recommençait). Passer en SPI matériel a réglé le problème, d'où le besoin de libérer D5.
- **Bouton MANGER câblé vers 3V3** : GPIO16 (D0) est le seul pin de l'ESP8266 sans pull-up interne — câblé comme les autres (vers GND), il "flotte" et déclenche des appuis fantômes. En revanche GPIO16 dispose d'un pull-down interne spécifique (`INPUT_PULLDOWN_16`), d'où le câblage inversé (le bouton relie D0 à 3V3, et l'appui est détecté à l'état HAUT au lieu de BAS).
- **Buzzer sur RX** : RX sert normalement à la liaison série USB. Le code n'utilise donc pas `Serial.begin()`/`Serial.print()`, car les deux usages sont incompatibles simultanément.

## Procédé de conversion des images

L'écran ST7735 affiche les pixels au format **RGB565** (16 bits par pixel : 5 bits rouge, 6 bits vert, 5 bits bleu), stockés dans un tableau qu'on envoie directement en mémoire flash (`PROGMEM`) pour ne pas consommer la RAM.

Étapes suivies pour convertir tes 4 images PNG (`dors.png`, `idle.png`, `mange.png`, `travaille.png`) :

1. **Redimensionnement** : chaque image est redimensionnée puis recadrée au centre pour remplir exactement **128×160 pixels** (la taille de l'écran), en conservant les proportions (pas de déformation — l'excédent est coupé sur les bords).
2. **Conversion RGB888 → RGB565** : pour chaque pixel, les composantes rouge/vert/bleu classiques (0-255 chacune) sont recompressées sur 16 bits avec la formule :
   ```
   rgb565 = ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3)
   ```
3. **Écriture en tableau C** : les valeurs sont écrites dans `images.h` sous forme de 4 tableaux `const uint16_t` (un par état), stockés en `PROGMEM` pour rester en mémoire flash et ne pas surcharger la RAM (chaque image = 128×160×2 octets = 40 960 octets, soit ~160 Ko pour les 4 images).

Si tu veux remplacer une image plus tard, il suffit de refaire cette conversion (redimensionnement 128×160 + export RGB565) sur la nouvelle image et de remplacer le tableau correspondant dans `images.h`. Envoie-moi la nouvelle image, je peux régénérer le fichier directement.

## Fonctions du code (`MrLarbin.ino`)

### `void setup()`
Exécutée une seule fois au démarrage de la carte. Elle :
- configure les boutons en entrée (`pinMode`) — avec le mode spécial `INPUT_PULLDOWN_16` pour le bouton MANGER (D0) et `INPUT_PULLUP` pour les deux autres ;
- configure le buzzer et l'écran en sortie ;
- allume le rétroéclairage de l'écran ;
- initialise le bus SPI matériel (`SPI.begin()`) puis l'écran (`tft.initR()`) ;
- efface l'écran et affiche l'image de l'état de départ (idle) via `afficherEtat()`.

### `void loop()`
Exécutée en boucle continue tant que la carte est allumée. Elle :
- appelle `lireBoutons()` pour détecter les appuis ;
- toutes les 5 secondes (`INTERVALLE_STATS`), fait descendre la faim et l'énergie (ou remonter l'énergie si Mr Larbin dort) ;
- vérifie si une action temporaire (manger/travailler) est terminée, et repasse en idle si oui ;
- endort automatiquement Mr Larbin si son énergie tombe à 0 ;
- le réveille automatiquement si l'énergie est remontée à 100 (sauf si l'endormissement a été demandé manuellement au bouton DORMIR) ;
- appelle `afficherEtat()` pour rafraîchir l'écran si l'état a changé ;
- termine par un `delay(20)` pour ne pas surcharger le processeur.

### `void lireBoutons(unsigned long maintenant)`
Lit l'état des 3 boutons (avec un anti-rebond de 200 ms via `DEBOUNCE`) et déclenche l'action correspondante :
- **MANGER** (actif à l'état HAUT, câblage inversé) → passe en état "mange", fait un bip, augmente la faim de 30 ;
- **DORMIR** (actif à l'état BAS) → bascule entre "dort" et "idle" (permet de forcer le sommeil ou de réveiller manuellement) ;
- **TRAVAIL** (actif à l'état BAS) → passe en état "travaille", fait un bip, augmente le score de travail de 10.

Un seul bouton est traité par appel (structure `if / else if`), pour éviter les conflits si plusieurs sont pressés en même temps.

### `void beep()`
Émet un bip de 80 ms à 2000 Hz sur le buzzer via la fonction native `tone()` (non bloquante, pilotée par un timer matériel — elle ne ralentit pas la boucle principale). Appelée à chaque pression de bouton dans `lireBoutons()`.

### `void afficherEtat(EtatMrLarbin etat, bool forcer)`
Affiche à l'écran l'image correspondant à l'état donné (idle/dort/mange/travaille), en évitant de redessiner si l'état n'a pas changé depuis le dernier appel (paramètre `dernierEtatAffiche`), sauf si `forcer` vaut `true` (utilisé une seule fois au démarrage). Utilise `tft.drawRGBBitmap()` pour envoyer directement le tableau de pixels à l'écran.

## Variables globales principales

| Variable | Rôle |
|----------|------|
| `etatActuel` | État courant de Mr Larbin (idle / dort / mange / travaille) |
| `faim`, `energie`, `travail` | Statistiques du personnage (0 à 100) |
| `actionEnCours` | Vrai pendant une action temporaire (manger/travailler) qui doit se terminer toute seule après quelques secondes |
| `dormirManuel` | Vrai si le sommeil a été déclenché par le bouton DORMIR (pour ne pas réveiller automatiquement Mr Larbin dans ce cas) |
| `dernierAppuiBouton` | Sert à l'anti-rebond des boutons |

## Pistes d'évolution possibles

- Afficher les stats (faim/énergie/travail) en texte ou en barres sur l'écran
- Ajouter un état "mort" si la faim ou l'énergie tombent à 0 trop longtemps
- Sauvegarder les stats en mémoire flash (`EEPROM`/`LittleFS`) pour les garder après une coupure de courant

================== PARTIE PORTAL BOX ==================

# WorkshopB2 — Portail Web Raspberry Pi 4

Serveur web Flask pour Raspberry Pi 4 qui affiche une interface plein écran contrôlée par un bouton physique branché sur les broches GPIO : écran noir par défaut, bascule vers un GIF animé à l'appui du bouton (et inversement).

## Fichiers du projet

- `app.py` — le script principal (serveur Flask + gestion GPIO + page HTML/CSS/JS embarquée)
- `requirements.txt` — dépendances Python (`flask`, `gpiozero`)
- `workshopb2-portail.service` — service systemd pour le lancement automatique au démarrage
- `static/portail.gif` — le GIF affiché à l'écran

## Fonctionnement

- **Affichage par défaut :** fond noir plein écran sur le navigateur du client (ex : téléphone connecté au même réseau que le Pi).
- **Action du bouton :** un appui sur le bouton physique bascule l'état de l'application. La page passe du noir à l'affichage du GIF (et inversement au prochain appui).
- **Mise à jour en temps réel :** le navigateur interroge le serveur en arrière-plan (polling AJAX via `fetch('/status')` toutes les 300 ms) pour mettre à jour l'affichage sans jamais recharger la page.
- **Anti-cache GIF :** à chaque activation, l'URL du GIF reçoit un paramètre unique (`?t=Date.now()`) pour forcer le navigateur à rejouer l'animation depuis le début.

> **Note :** une évolution future du projet est prévue avec un son (`portail_gun.mp3`) joué en complément du GIF. Le code actuel de `app.py` ne gère que le GIF ; le son n'est pas encore implémenté côté serveur.

## Câblage final

| Composant     | Pin Raspberry Pi 4        | Remarque |
|---------------|----------------------------|----------|
| Bouton Signal | GPIO 17 (broche BCM 17)   | configurable via `BOUTON_PIN` dans `app.py` |
| Bouton GND    | GND                        | masse électrique |

### Pourquoi ce câblage un peu particulier ?

- **Pas de résistance externe** : la résistance de rappel au plus (pull-up) interne du Raspberry Pi est activée directement par le code (`pull_up=True`). Aucun composant ni résistance externe n'est nécessaire.
- **Anti-rebond logiciel** : un délai de 50 ms (`BOUNCE_TIME`) est configuré pour éviter les déclenchements multiples sur un seul appui.

## Structure du projet

```text
workshopb2_portail_pi/
├── app.py                       # Script principal Flask + gestion GPIO
├── requirements.txt             # Dépendances Python (flask, gpiozero)
├── workshopb2-portail.service   # Service systemd pour le lancement automatique
└── static/
    └── portail.gif              # Le GIF à afficher
```

## Installation

### 1. Installer les dépendances

Sur les Raspberry Pi OS récents, l'utilisation d'un environnement virtuel est nécessaire (erreur "externally-managed-environment" sinon) :

```bash
sudo apt update
sudo apt install python3-venv
cd ~/workshopb2_portail_pi
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

Une fois le venv créé, il suffit de refaire `source venv/bin/activate` aux prochaines sessions manuelles ; le service systemd (voir plus bas) s'en charge automatiquement au démarrage.

### 2. Mettre le GIF en place

Copie ton fichier dans `static/` :

```
static/portail.gif
```

Renomme-le exactement ainsi, ou modifie la constante `GIF_FILENAME` en haut de `app.py` si tu préfères un autre nom.

### 3. Adapter le GPIO du bouton

Dans `app.py` :

```python
BOUTON_PIN = 17  # broche BCM du bouton
```

Câblage : bouton entre cette broche et GND (pull-up géré par le code, voir section Câblage).

### 4. Connecter le Pi au réseau (ex : hotspot du téléphone)

Active le partage de connexion sur ton téléphone, puis sur le Pi :

```bash
sudo raspi-config
# System Options -> Wireless LAN -> choisis le SSID de ton téléphone
```

Récupère l'IP du Pi sur ce réseau :

```bash
hostname -I
```

## Exécution

Le serveur utilise le port réseau **80** (port HTTP standard), ce qui nécessite les privilèges administrateur sous Linux.

```bash
sudo venv/bin/python3 app.py
```

Le fichier possède aussi un shebang (`#!/usr/bin/env python3`), qui permet de le lancer directement une fois rendu exécutable :

```bash
chmod +x app.py
sudo ./app.py
```

Sur le téléphone ou le PC connecté au même réseau, ouvre le navigateur à l'adresse IP du Raspberry Pi :

```
http://<IP_du_Pi>/
```

### Comportement attendu
- Écran noir au chargement de la page.
- 1er appui sur le bouton → le GIF s'affiche, sans recharger la page.
- 2e appui → retour à l'écran noir.

## Lancement automatique au démarrage (optionnel)

Le fichier `workshopb2-portail.service` permet de lancer le serveur automatiquement au démarrage du Pi via systemd.

```bash
sudo cp workshopb2-portail.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable workshopb2-portail.service --now
```

> Adapte les champs `WorkingDirectory` et `ExecStart` du fichier `.service` si ton utilisateur n'est pas `pi`/`root` ou si le dossier du projet n'est pas installé dans `/home/<user>/workshopb2_portail_pi`.

## Fonctions et routes du code (`app.py`)

### `basculer()`
Inverse la variable globale `afficher_gif` (`True`/`False`). Appelée automatiquement par `gpiozero` à chaque appui sur le bouton via `bouton.when_pressed`.

### Route `/`
Sert la page HTML/CSS/JS principale, générée directement en Python (pas de dossier `templates`).

### Route `/status`
Renvoie l'état actuel sous forme de JSON (`{"actif": true/false}`), interrogée par le navigateur toutes les 300 ms.

### Route `/static/<fichier>`
Sert les fichiers multimédias contenus dans le dossier `static` (ex : `portail.gif`).

### Côté navigateur (HTML/CSS/JS embarqué dans `app.py`)
- **CSS :** page configurée en plein écran (`100vw`/`100vh`), fond noir, sans marges, centrage Flexbox.
- **JavaScript (polling) :** `setInterval` exécute une requête `fetch('/status')` toutes les 300 ms et met à jour l'affichage du GIF si l'état a changé.
- **Gestion du cache GIF :** l'URL du GIF reçoit un paramètre unique (`?t=Date.now()`) à chaque activation pour forcer le rejeu de l'animation depuis le début.

## Variables globales principales

| Variable | Rôle |
|----------|------|
| `afficher_gif` | État courant de l'affichage (`True` = GIF visible, `False` = écran noir) |
| `BOUTON_PIN` | Broche GPIO (BCM) utilisée par le bouton |
| `BOUNCE_TIME` | Délai anti-rebond du bouton (en secondes) |
| `GIF_FILENAME` | Nom du fichier GIF servi par le serveur |

## Pistes d'évolution possibles

- Implémenter le son (`portail_gun.mp3`) évoqué dans le comportement cible, en le jouant côté client au moment du retour à l'écran noir
- Ajouter un endpoint pour changer le GIF ou le son sans modifier le code
- Historiser les appuis (nombre d'activations, horodatage) pour du debug ou des statistiques
