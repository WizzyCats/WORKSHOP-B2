#!/usr/bin/env python3
"""
WorkshopB2 - Portail
Serveur web Flask pour Raspberry Pi 4 basculant un GIF à l'écran via un bouton GPIO.
"""

import os
from flask import Flask, jsonify, send_from_directory, Response
from gpiozero import Button

# Configuration
BOUTON_PIN = 17       # Broche GPIO en numérotation BCM
BOUNCE_TIME = 0.05    # Anti-rebond (50ms)
GIF_FILENAME = "portail.gif"

# Emplacements des fichiers
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "static")

# Initialisation Flask et état global
app = Flask(__name__)
afficher_gif = False

# Configuration du bouton physique
bouton = Button(BOUTON_PIN, pull_up=True, bounce_time=BOUNCE_TIME)

def basculer():
    """Inverse l'état d'affichage du GIF."""
    global afficher_gif
    afficher_gif = not afficher_gif
        
bouton.when_pressed = basculer

# Interface Web (HTML/CSS/JS)
PAGE_HTML = """
<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>WorkshopB2 Portail</title>
  <style>
    html, body {
      margin: 0; padding: 0;
      width: 100%; height: 100%;
      background: #000;
      overflow: hidden;
    }
    #screen {
      width: 100vw; height: 100vh;
      display: flex;
      align-items: center;
      justify-content: center;
      background: #000;
      position: relative;
    }
    #gif {
      max-width: 100%;
      max-height: 100%;
      display: none;
    }
  </style>
</head>
<body>
  <div id="screen">
    <img id="gif" src="/static/PLACEHOLDER_GIF" alt="portail">
  </div>

  <script>
    const gifEl = document.getElementById('gif');
    let etatAffiche = false;

    // Polling du statut du serveur toutes les 300ms
    async function verifierEtat() {
      try {
        const rep = await fetch('/status');
        const data = await rep.json();

        if (data.actif !== etatAffiche) {
          etatAffiche = data.actif;
          if (etatAffiche) {
            // Astuce anti-cache pour relancer l'animation GIF à zéro
            gifEl.src = '/static/PLACEHOLDER_GIF?t=' + Date.now();
            gifEl.style.display = 'block';
          } else {
            gifEl.style.display = 'none';
          }
        }
      } catch (e) {
        // Ignorer les micro-coupures réseau
      }
    }

    setInterval(verifierEtat, 300);
  </script>
</body>
</html>
""".replace("PLACEHOLDER_GIF", GIF_FILENAME)

# Routes Flask
@app.route("/")
def racine():
    return Response(PAGE_HTML, mimetype="text/html")

@app.route("/status")
def status():
    return jsonify(actif=afficher_gif)

@app.route("/static/<path:nom_fichier>")
def fichiers_statiques(nom_fichier):
    return send_from_directory(STATIC_DIR, nom_fichier)

# Lancement du serveur (Port 80 nécessite sudo)
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=80, debug=False)

