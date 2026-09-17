# WORKSHOP-B2

PARTIE MR LARBIN:

/*
  =========================================================
   MR LARBIN - Tamagotchi ESP8266 + TFT 128x160 (ST7735)
  =========================================================
  Bibliothèques nécessaires (à installer via le Gestionnaire
  de bibliothèques de l'IDE Arduino) :
    - Adafruit GFX Library
    - Adafruit ST7735 and ST7789 Library

  Câblage (d'après ton branchement réel) :
    Écran GND -> GND
    Écran VCC -> 3V3
    Écran RES -> TX  (GPIO1)   -> déplacé depuis D3 : D3=GPIO0 sert au boot de l'ESP8266
    Écran DC  -> D4  (GPIO2)
    Écran CS  -> D8  (GPIO15)
    Écran BLK -> D6  (GPIO12)   -> rétroéclairage (déplacé depuis D5)
    Écran SCL -> D5  (GPIO14)   -> horloge SPI MATÉRIELLE (déplacé depuis D6)
    Écran SDA -> D7  (GPIO13)   -> données SPI matérielle (inchangé)
    (Le SPI logiciel était trop lent pour une image 128x160 : la boucle
     bloquait trop longtemps sans "yield", ce qui déclenchait un reset
     watchdog de l'ESP8266 -> image tronquée + flash blanc en boucle.
     Le SPI matériel de l'ESP8266 est fixé sur D5(SCLK)/D7(MOSI), d'où le
     besoin de libérer D5 en déplaçant le rétroéclairage sur D6.)

    Bouton 1 (MANGER)  -> D0 (GPIO16) -> 3V3  *câblage inversé, voir remarque D0*
    Bouton 2 (DORMIR)  -> D1 (GPIO5)  -> GND
    Bouton 3 (TRAVAIL) -> D2 (GPIO4)  -> GND
    Buzzer (+)         -> RX (GPIO3)
    Buzzer (-)         -> GND

  /!\ Remarque sur le buzzer branché sur RX (GPIO3) :
    RX sert normalement à la liaison série (USB). Comme ce pin est réutilisé
    en sortie numérique pour le buzzer, le code n'utilise PAS Serial.begin() /
    Serial.print() : les deux sont incompatibles en même temps. Si tu as
    besoin du moniteur série pour déboguer, débranche temporairement le
    buzzer, ou passe-le sur un autre pin libre (ex. A0 avec un transistor,
    ou TX/GPIO1).

  /!\ A propos du changement RES : D3 = GPIO0 = pin utilisé par l'ESP8266 pour
    choisir son mode au démarrage (flash vs exécution normale). Y brancher le
    reset de l'écran empêchait l'upload automatique (erreur "Timed out waiting
    for packet header"). RES est donc passé sur TX (GPIO1), libre.

  /!\ Remarque importante sur D0 (GPIO16) :
    Ce pin ne possède PAS de résistance de pull-up interne (contrairement aux
    autres GPIO de l'ESP8266) — d'où les bips intempestifs si le bouton reste
    câblé comme les autres. En revanche GPIO16 a un pull-DOWN interne
    spécifique (INPUT_PULLDOWN_16). Le bouton 1 est donc câblé à l'envers
    des deux autres : entre D0 et 3V3 (pas GND), et se lit à l'état HAUT
    quand il est pressé (au lieu de BAS pour les boutons 2 et 3).

  Adaptez les pins ci-dessous à votre câblage réel si besoin.
  =========================================================
*/

#include <Adafruit_GFX.h>
#include <Adafruit_ST7735.h>
#include <SPI.h>
#include "images.h"   // contient img_dors, img_idle, img_mange, img_travaille

// ---------- Pins écran ----------
#define TFT_CS    15   // D8
#define TFT_RST    1   // TX (déplacé depuis D3/GPIO0 qui bloquait l'upload)
#define TFT_DC     2   // D4
#define TFT_BLK   12   // D6 (rétroéclairage, déplacé depuis D5)
// SCL(D5/GPIO14) et SDA(D7/GPIO13) sont fixés par le SPI matériel de l'ESP8266,
// pas besoin de les définir : la lib les pilote automatiquement.

// ---------- Pins boutons ----------
#define BTN_MANGER  16   // D0 - câblé vers 3V3, pull-down interne (voir remarque ci-dessus)
#define BTN_DORMIR   5   // D1
#define BTN_TRAVAIL  4   // D2

// ---------- Pin buzzer ----------
#define BUZZER_PIN   3   // RX - voir remarque ci-dessus (pas de Serial en même temps)

// Constructeur en SPI matériel (rapide) : cs, dc, rst. MOSI/SCLK sont fixés
// automatiquement par le hardware de l'ESP8266 (D7/D5).
Adafruit_ST7735 tft = Adafruit_ST7735(TFT_CS, TFT_DC, TFT_RST);

// ---------- États du Tamagotchi ----------
enum EtatMrLarbin {
  ETAT_IDLE,
  ETAT_DORT,
  ETAT_MANGE,
  ETAT_TRAVAILLE
};

EtatMrLarbin etatActuel = ETAT_IDLE;
EtatMrLarbin dernierEtatAffiche = ETAT_IDLE; // pour ne redessiner que si ça change

// ---------- Statistiques (0 à 100) ----------
int faim    = 80;   // descend avec le temps, remonte quand il mange
int energie = 80;   // descend avec le temps, remonte quand il dort
int travail = 0;    // monte quand il travaille (score / argent gagné)

// ---------- Timers ----------
unsigned long dernierTickStats   = 0;
const unsigned long INTERVALLE_STATS = 5000;   // décrément des stats toutes les 5s

unsigned long debutActionTemporaire = 0;
const unsigned long DUREE_MANGE    = 4000;     // 4s de mange
const unsigned long DUREE_TRAVAIL  = 4000;     // 4s de travail
bool actionEnCours = false;

// anti-rebond simple
unsigned long dernierAppuiBouton = 0;
const unsigned long DEBOUNCE = 200;

// Indique si l'utilisateur a demandé le sommeil manuellement (bouton),
// pour ne pas le réveiller automatiquement dans ce cas.
bool dormirManuel = false;

void setup() {
  // Pas de Serial.begin() ici : RX (GPIO3) est réutilisé pour le buzzer (voir en-tête).

  // D0 (GPIO16) : pull-down interne spécifique, bouton câblé vers 3V3 (voir en-tête)
  pinMode(BTN_MANGER,  INPUT_PULLDOWN_16);
  pinMode(BTN_DORMIR,  INPUT_PULLUP);
  pinMode(BTN_TRAVAIL, INPUT_PULLUP);

  pinMode(BUZZER_PIN, OUTPUT);
  digitalWrite(BUZZER_PIN, LOW);

  pinMode(TFT_BLK, OUTPUT);
  digitalWrite(TFT_BLK, HIGH);  // allume le rétroéclairage

  SPI.begin();

  tft.initR(INITR_BLACKTAB);   // adaptez si votre écran a un tab différent (GREENTAB, REDTAB...)
  tft.setRotation(0);          // 0 ou 2 selon l'orientation souhaitée (portrait 128x160)
  tft.fillScreen(ST77XX_BLACK);

  afficherEtat(etatActuel, true);
}

void loop() {
  unsigned long maintenant = millis();

  lireBoutons(maintenant);

  // Décrément périodique des stats (sauf pendant une action temporaire)
  if (!actionEnCours && maintenant - dernierTickStats >= INTERVALLE_STATS) {
    dernierTickStats = maintenant;
    if (etatActuel != ETAT_DORT) {
      energie = max(0, energie - 2);
    } else {
      energie = min(100, energie + 5); // il récupère de l'énergie en dormant
    }
    faim = max(0, faim - 3);
  }

  // Fin d'une action temporaire (manger / travailler)
  if (actionEnCours && maintenant - debutActionTemporaire >= (etatActuel == ETAT_MANGE ? DUREE_MANGE : DUREE_TRAVAIL)) {
    actionEnCours = false;
    etatActuel = ETAT_IDLE;
  }

  // Si plus d'énergie, il s'endort automatiquement
  if (energie <= 0 && etatActuel != ETAT_DORT) {
    etatActuel = ETAT_DORT;
    actionEnCours = false;
  }

  // Si l'énergie est remontée à fond pendant le sommeil auto, on se réveille
  if (etatActuel == ETAT_DORT && energie >= 100 && !dormirManuel) {
    etatActuel = ETAT_IDLE;
  }

  afficherEtat(etatActuel, false);

  delay(20);
}

void lireBoutons(unsigned long maintenant) {
  if (maintenant - dernierAppuiBouton < DEBOUNCE) return;

  // BTN_MANGER est câblé vers 3V3 (pull-down interne) -> actif à l'état HAUT,
  // contrairement aux deux autres boutons (câblés vers GND, actifs à l'état BAS)
  if (digitalRead(BTN_MANGER) == HIGH) {
    dernierAppuiBouton = maintenant;
    beep();
    etatActuel = ETAT_MANGE;
    actionEnCours = true;
    debutActionTemporaire = maintenant;
    faim = min(100, faim + 30);
    dormirManuel = false;
  }
  else if (digitalRead(BTN_DORMIR) == LOW) {
    dernierAppuiBouton = maintenant;
    beep();
    if (etatActuel == ETAT_DORT) {
      // Réveil manuel
      etatActuel = ETAT_IDLE;
      dormirManuel = false;
    } else {
      etatActuel = ETAT_DORT;
      actionEnCours = false;
      dormirManuel = true;
    }
  }
  else if (digitalRead(BTN_TRAVAIL) == LOW) {
    dernierAppuiBouton = maintenant;
    beep();
    etatActuel = ETAT_TRAVAILLE;
    actionEnCours = true;
    debutActionTemporaire = maintenant;
    travail = min(100, travail + 10);
    dormirManuel = false;
  }
}

// Petit bip non bloquant (utilise le timer matériel via tone(), donc ne
// ralentit pas la boucle principale). Fonctionne avec un buzzer passif.
// Si vous avez un buzzer ACTIF (2 pattes, pas de "+"/"-" marqué mais bip
// tout seul dès qu'il est alimenté), remplacez le corps de cette fonction
// par : digitalWrite(BUZZER_PIN, HIGH); delay(80); digitalWrite(BUZZER_PIN, LOW);
void beep() {
  tone(BUZZER_PIN, 2000, 80);  // 2000 Hz pendant 80 ms
}

void afficherEtat(EtatMrLarbin etat, bool forcer) {
  if (etat == dernierEtatAffiche && !forcer) return; // évite de redessiner inutilement
  dernierEtatAffiche = etat;

  const uint16_t* image = img_idle;
  switch (etat) {
    case ETAT_IDLE:      image = img_idle;      break;
    case ETAT_DORT:      image = img_dors;      break;
    case ETAT_MANGE:     image = img_mange;     break;
    case ETAT_TRAVAILLE: image = img_travaille; break;
  }

  tft.drawRGBBitmap(0, 0, image, IMG_WIDTH, IMG_HEIGHT);
}

PARTIE PORTAL BOX
