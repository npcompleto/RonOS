import os
import subprocess
import logging
from datetime import datetime

def play_audio2(filepath):
    """Riproduce un file audio specificato. Ritorna il codice di uscita del processo."""
    if os.path.exists(filepath):
        try:
            process = subprocess.run(["ffplay", "-nodisp", "-autoexit", filepath], 
                           stderr=subprocess.DEVNULL, 
                           stdout=subprocess.DEVNULL)
            return process.returncode
        except Exception as e:
            logging.error(f"Errore durante la riproduzione di {filepath}: {e}")
            return -1
    else:
        logging.error(f"File audio non trovato: {filepath}")
        return -1

def play_audio(filepath):
    """Riproduce un file audio usando mpg123 (più leggero per MP3)."""
    if os.path.exists(filepath):
        try:
            # mpg123 è nativo per MP3 e molto affidabile su RPi
            process = subprocess.run(["mpg123", "-q", filepath], 
                           stderr=subprocess.DEVNULL, 
                           stdout=subprocess.DEVNULL)
            return process.returncode
        except Exception as e:
            logging.error(f"Errore durante la riproduzione con mpg123: {e}")
            return -1
    else:
        logging.error(f"File audio non trovato: {filepath}")
        return -1