# WORKSHOP-B2

=========================================================
                    PARTIE MR LARBIN
=========================================================

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

=========================================================
                    PARTIE PORTAL BOX
=========================================================
