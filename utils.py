import pygame
import os
import config
import time
import psutil
# Canale dedicato per la riproduzione della voce/risposte del robot
# Inizializzato a None, verrà assegnato dopo il mixer.init()
_voice_channel = None

def get_voice_channel():
    """Restituisce il canale dedicato, inizializzandolo se necessario."""
    global _voice_channel
    if not pygame.mixer.get_init():
        # Parametri ottimizzati per Raspberry Pi
        pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=1048)
    
    if _voice_channel is None:
        # Prende un canale specifico (es. il canale 0) per avere il controllo assoluto
        _voice_channel = pygame.mixer.Channel(0)
    return _voice_channel

def is_robot_speaking():
    """
    Utility da usare anche nel codice STT.
    Ritorna True se il canale della voce sta riproducendo audio.
    """
    if not pygame.mixer.get_init():
        return False
    return get_voice_channel().get_busy()

def wake_up_audio():
    """Invia un segnale minimo per forzare l'attivazione della scheda audio."""
    sample_rate = 44100
    duration = 0.1 
    buf = bytearray([128 if i % 2 == 0 else 127 for i in range(int(sample_rate * duration))])
    
    wake_sound = pygame.mixer.Sound(buffer=buf)
    wake_sound.set_volume(0.01)
    
    # Usiamo un canale generico per il wake-up per non disturbare il canale principale
    ch = wake_sound.play()
    if ch:
        while ch.get_busy():
            pygame.time.delay(10)
    time.sleep(0.3)

def play_audio(filepath, volume=0.8):
    """
    Riproduce un file audio (WAV o MP3) come Sound su un canale dedicato.
    
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
        # Ottieni il canale dedicato (gestisce internamente l'init del mixer)
        channel = get_voice_channel()

        # Se il robot sta già parlando, evitiamo di sovrapporre l'audio
        if channel.get_busy():
            config.logger.warning("Il canale audio è già occupato.")
            return False

        wake_up_audio()

        # Carica il file come Sound (Pygame 2.+ supporta nativamente anche gli MP3 qui)
        sound = pygame.mixer.Sound(filepath)
        sound.set_volume(volume)
        
        config.logger.info(f"Riproduzione in corso (Channel 0): {filepath} (Volume: {int(volume*100)}%)")
        
        # Riproduce il suono specificatamente sul nostro canale dedicato
        channel.play(sound)

        # Attendi la fine del brano (bloccante) interrogando il canale
        while channel.get_busy():
            pygame.time.Clock().tick(10) # Riduce il carico sulla CPU nel loop
            
        time.sleep(0.3)
        return True

    except Exception as e:
        config.logger.error(f"Errore durante la riproduzione con pygame.mixer.Sound: {e}")
        return False

def stop_audio():
    """Ferma immediatamente la riproduzione sul canale dedicato."""
    if pygame.mixer.get_init():
        get_voice_channel().stop()

def is_playing_music():
    """
    Ritorna True se pygame.mixer.music sta riproducendo la musica.
    """
    if not pygame.mixer.get_init():
        return False
    return pygame.mixer.music.get_busy()

def shutdown():
    """
    Spegne il sistema.
    """
    config.logger.info("Spegnimento Ron OS e PWA in corso...")
    os.system("sudo shutdown now")

def get_wifi_strength():
    try:
        with open("/proc/net/wireless", "r") as f:
            lines = f.readlines()
            
        # The data starts on the 3rd line of the file
        for line in lines[2:]:
            details = line.split()
            if len(details) > 2:
                # Link quality is usually the 3rd column (index 2)
                # It strips the trailing dot if present
                link_quality = float(details[2].replace('.', ''))
                return link_quality
    except FileNotFoundError:
        print("Could not read wireless stats. Are you on Linux/Raspberry Pi?")
    return 0.0



def get_cpu_temp():
    # Verifica se il sistema espone i sensori di temperatura
    if hasattr(psutil, "sensors_temperatures"):
        temps = psutil.sensors_temperatures()
        
        # 'coretemp' è comune su Linux/Intel, ma può variare
        if not temps:
            return None
            
        # Alcuni sistemi hanno più sensori (package, core, ecc.)
        # Qui prendiamo il primo sensore disponibile
        for name, entries in temps.items():
            for entry in entries:
                return entry.current
    return None

def get_current_voice_volume():
    """
    Ritorna il volume corrente del canale vocale (0.0-1.0).
    """
    if not pygame.mixer.get_init():
        return 0.0
    return get_voice_channel().get_volume()

def increase_voice_volume():
    if not pygame.mixer.get_init():
        return
    current_volume = get_voice_channel().get_volume()
    new_volume = min(current_volume + 0.1, 1.0)
    get_voice_channel().set_volume(new_volume)

def decrease_voice_volume():
    if not pygame.mixer.get_init():
        return
    current_volume = get_voice_channel().get_volume()
    new_volume = max(current_volume - 0.1, 0.0)
    get_voice_channel().set_volume(new_volume)

def get_current_music_volume():
    """
    Ritorna il volume corrente di pygame.mixer.music (0.0-1.0).
    """
    if not pygame.mixer.get_init():
        return 0.0
    return pygame.mixer.music.get_volume()

def increase_music_volume():
    """
    Incrementa il volume di pygame.mixer.music (0.0-1.0).
    """
    if not pygame.mixer.get_init():
        return
    current_volume = pygame.mixer.music.get_volume()
    new_volume = min(current_volume + 0.1, 1.0)
    pygame.mixer.music.set_volume(new_volume)

def decrease_music_volume():
    """
    Decrementa il volume di pygame.mixer.music (0.0-1.0).
    """
    if not pygame.mixer.get_init():
        return
    current_volume = pygame.mixer.music.get_volume()
    new_volume = max(current_volume - 0.1, 0.0)
    pygame.mixer.music.set_volume(new_volume)