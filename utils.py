import pygame
import os
import config
import time

def wake_up_audio():
    """Invia un segnale minimo per forzare l'attivazione della scheda audio."""
    # Creiamo un suono brevissimo (0.1 secondi) con un valore minimo per 'muovere' i driver
    # Invece di zero assoluto, usiamo un'alternanza minima
    sample_rate = 44100
    duration = 0.1 
    # Genera un'onda quadra a volume quasi zero
    buf = bytearray([128 if i % 2 == 0 else 127 for i in range(int(sample_rate * duration))])
    
    wake_sound = pygame.mixer.Sound(buffer=buf)
    wake_sound.set_volume(0.01) # Volume quasi nullo
    ch = wake_sound.play()
    while ch.get_busy():
        pygame.time.delay(10)
    
    # IMPORTANTE: Piccolo stop per dare tempo al driver di stabilizzarsi
    time.sleep(0.3)



def play_audio(filepath, volume=0.8):
    """
    Riproduce un file audio (MP3 o WAV) utilizzando pygame.
    
    Args:
        filepath (str): Percorso del file audio.
        volume (float): Volume da 0.0 a 1.0. Default 0.8.
    
    Returns:
        bool: True se la riproduzione è riuscita, False altrimenti.
    """
    if not os.path.exists(filepath):
        config.logger.error(f"File audio non trovato: {filepath}")
        return False

    try:
        # Inizializza il mixer se non è già attivo
        if not pygame.mixer.get_init():
            # Parametri ottimizzati per Raspberry Pi
            pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=1048)
        if pygame.mixer.music.get_busy():
            return False
        wake_up_audio()
        # Carica il file (supporta MP3 e WAV)
        pygame.mixer.music.load(filepath)
        
        # Imposta il volume
        pygame.mixer.music.set_volume(volume)
        
        config.logger.info(f"Riproduzione in corso: {filepath} (Volume: {int(volume*100)}%)")
        
        # Avvia la riproduzione
        pygame.mixer.music.play()

        # Attendi la fine del brano (bloccante)
        while pygame.mixer.music.get_busy():
            pygame.time.Clock().tick(10) # Riduce il carico sulla CPU nel loop
            
        # Attesa aggiuntiva per assicurare il rilascio completo del device
        time.sleep(0.3)
            
        return True

    except Exception as e:
        config.logger.error(f"Errore durante la riproduzione con pygame: {e}")
        return False