import pygame
import os
import config

def wake_up_audio():
    silence = pygame.mixer.Sound(buffer=bytes([0] * 3000))
    ch = silence.play()
    while ch.get_busy():
        pygame.time.delay(10)



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
            pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=512)
            
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
            
        return True

    except Exception as e:
        config.logger.error(f"Errore durante la riproduzione con pygame: {e}")
        return False