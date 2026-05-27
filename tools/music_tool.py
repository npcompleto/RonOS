import yt_dlp
import pygame
import os
import glob
import random
import threading
import time
import difflib
from config import logger, MUSIC_CACHE_DIR
from langchain_core.tools import tool
from event_manager import EventManager
from status import get_global_status, State
from mutagen.mp3 import MP3


class MusicTool:
    def __init__(self):
        if not pygame.mixer.get_init():
            pygame.mixer.init()
        self.download_path = MUSIC_CACHE_DIR
        if not os.path.exists(self.download_path):
            os.makedirs(self.download_path)
            
        self._playlist = []
        self._current_index = 0
        self._stop_event = False
        self._playlist_thread = None
        self._currently_playing = None

    def get_cached_songs(self):
        """Restituisce la lista dei file MP3 in cache."""
        files = glob.glob(os.path.join(self.download_path, "*.mp3"))
        logger.debug(f"Cache: {files}")
        return sorted([os.path.basename(f) for f in files])

    # --- LOGICA THREADING & PLAYLIST ---

    def _playlist_worker(self):
        """Monitora la fine del brano e passa al successivo."""
        while not self._stop_event:
            # Se la musica non sta suonando, passa alla prossima canzone
            if not pygame.mixer.music.get_busy():
                self._current_index += 1
                if self._current_index < len(self._playlist):
                    self._play_current_file()
                else:
                    break # Playlist finita
            time.sleep(1)
        em = EventManager()
        em.publish("music", {"message": None, "started": False})
        logger.info("[MusicTool] Thread playlist terminato.")
        if get_global_status().get_state() == State.DANCING:
            get_global_status().set_state(State.IDLE, reason="Playlist terminata")

    def _play_current_file(self):
        """Carica e suona il brano all'indice corrente della playlist."""
        if 0 <= self._current_index < len(self._playlist):
            filename = self._playlist[self._current_index]
            filepath = os.path.join(self.download_path, filename)
            pygame.mixer.music.load(filepath)
            em = EventManager()
            if get_global_status().set_state(State.DANCING, reason="Riproduzione musicale (_play_current_file)"):
                em.publish("music", {"message": filename, "started": True})
                self._currently_playing = filename
                pygame.mixer.music.play()
                logger.info(f"In riproduzione dalla cache: {filename}")
                return filename
            else:
                logger.warning("Impossibile riprodurre la musica, stato attuale non permette la transizione a DANCING.")
                return None
        return None

    def _get_playlist_songs(self, playlist_name):
        """Legge un file di playlist e restituisce la lista dei brani."""
        playlist_path = os.path.join(self.download_path, f"{playlist_name}_playlist.txt")
        if os.path.exists(playlist_path):
            with open(playlist_path, "r") as f:
                songs = [line.strip() for line in f.readlines() if line.strip()]
            return songs
        return None

    def play_all_from_cache(self, shuffle=True, playlist_name: str = None):
        """Avvia la riproduzione di tutti i brani in cache via Thread."""
        self.stop() # Ferma tutto il precedente
        if playlist_name:
            logger.debug(f"Caricamento playlist '{playlist_name}'...")
            songs = self._get_playlist_songs(playlist_name)
            if songs:
                self._playlist = songs
            else:
                logger.warning(f"Playlist '{playlist_name}' non trovata. Carico tutta la cache.")
        else:
            self._playlist = self.get_cached_songs()
        logger.debug(f"Playlist: {self._playlist}")
        if not self._playlist:
            return "Cache vuota."
        if shuffle:
            random.shuffle(self._playlist)
        
        self._current_index = 0
        self._stop_event = False
        title = self._play_current_file()
        
        self._playlist_thread = threading.Thread(target=self._playlist_worker, daemon=True)
        self._playlist_thread.start()
        return f"Playlist avviata ({len(self._playlist)} brani). In riproduzione: {title}"

    # --- LOGICA RICERCA E DOWNLOAD ---

    def play_from_cache(self, url):
        """Cerca e riproduce un singolo brano dalla cache."""
        if not url.startswith(self.download_path):
            print(f"URL '{url}' non è nella cache.")
            return None, f"URL '{url}' non è nella cache."

        print(f"Ricerca '{url}' in cache...")
        target_file = os.path.basename(url)
        print(f"Target file: {target_file}")
        if target_file:
            filepath = os.path.join(self.download_path, target_file)
            print(f"Filepath: {filepath}")
            pygame.mixer.music.load(filepath)
            pygame.mixer.music.play()
            self._currently_playing = target_file
            return target_file, f"In riproduzione dalla cache: {target_file}"
        return None, "Non trovato in cache."

    def play_download(self, url):
        """Scarica da un URL diretto e riproduce (interrompe playlist se attiva)."""
        logger.debug(f"Scaricamento diretto di '{url}'...")
        em = EventManager()
        
        self.stop()
        try:
            ydl_opts = {
                'format': 'bestaudio/best',
                'outtmpl': f'{self.download_path}/%(title)s.%(ext)s',
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': '192',
                }],
                'quiet': True,
                'no_overwrites': True
                # 'default_search' rimosso per forzare l'interpretazione come URL
            }
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                em.publish("downloading", {"message": f"Sto scaricando da {url}", "started": True})
                
                # Scarica direttamente
                info = ydl.extract_info(url, download=True)
                
                # Se è un singolo video, info è il dizionario del video stesso
                video_info = info
                
                filename = ydl.prepare_filename(video_info).rsplit('.', 1)[0] + ".mp3"
                em.publish("downloading", {"message": None, "started": False})
                
                pygame.mixer.music.load(filename)
                
                if get_global_status().set_state(State.DANCING, reason="Riproduzione musicale"):
                    em.publish("music", {"message": None, "started": True})
                    self._currently_playing = filename
                    pygame.mixer.music.play()
                    return f"Scaricato e in riproduzione: {video_info.get('title', 'Video')}"
                else:
                    logger.warning("Impossibile riprodurre la musica.")
                    return "Musica scaricata ma non posso riprodurla in questo momento."
                    
        except Exception as e:
            em.publish("loading", {"message": f"Errore download: {str(e)}", "started": False})
            self._currently_playing = None
            return f"Errore download: {str(e)}"

    def list_cached_songs(self):
        """Restituisce i titoli dei brani in cache che corrispondono alla query."""
        songs = self.get_cached_songs()
        return songs if songs else "Cache vuota."

    def play_any(self, url):
        """Cerca in cache, se fallisce scarica."""
        logger.debug(f"Ricerca '{url}' in cache...")
        title, msg = self.play_from_cache(url)
        if title:
            return msg
        return self.play_download(url)

    # --- CONTROLLO ---

    def stop(self):
        """Ferma musica e interrompe il thread della playlist."""
        self._stop_event = True # Segnala al thread di uscire
        em = EventManager()
        em.publish("music", {"message": None, "started": False})
        self._currently_playing = None
        pygame.mixer.music.stop()
        pygame.mixer.music.unload()
        
        if self._playlist_thread and self._playlist_thread.is_alive():
            # Non usiamo join(timeout) qui per evitare di bloccare il bot 
            # Il thread uscirà al prossimo 'sleep' grazie allo stop_event
            pass 
            
        self._playlist = []
        self._current_index = 0
        #get_global_status().set_state(State.IDLE, reason="Musica fermata")
        return "Musica e playlist fermate."

    def is_playing(self):
        return pygame.mixer.music.get_busy()

    def search_any(self, query, max_results=20, only_cache=False):
        combined_results = []
        # 1. CERCA NELLA CACHE LOCALE
        try:
            cached_songs = self.get_cached_songs() or []
            for songFilename in cached_songs:
                # Recupera in modo sicuro i dati dal dizionario locale
                title = songFilename.rsplit('.', 1)[0] if '.' in songFilename else songFilename
                url = os.path.join(self.download_path, songFilename)  # In questo contesto, l'URL è rappresentato dal nome del file nella cache
                
                local_path = title
                if title and local_path:
          
                    combined_results.append({
                        'title': title,
                        'url': url
                    })
        except Exception as e:
            print(f"Errore nella lettura della cache: {str(e)}")
        
        if not only_cache:
            online_results = self.search_online(query, max_results)
            combined_results.extend(online_results)
        return combined_results
    
    def search_online(self, query, max_results=20):
        """Cerca musica su YouTube e restituisce una lista di dict con titolo e URL corretti."""
        try:
            ydl_opts = {
                'quiet': True,
                'extract_flat': True,            # Ottiene solo i metadati di base (velocissimo)
                'skip_download': True,           # Impedisce l'avvio del download dei file
            }
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                search_query = f"ytsearch{max_results}:{query}"
                info = ydl.extract_info(search_query, download=False)
                
                if info and 'entries' in info:
                    results = []
                    for video in info['entries']:
                        if video and 'title' in video:
                            # 1. Tenta di prendere l'URL standard pre-generato da yt-dlp
                            video_url = video.get('webpage_url') or video.get('url')
                            
                            # 2. Se ha estratto solo l'ID (es. 'abc123xyz'), ricostruisce l'URL completo
                            if video_url and not video_url.startswith('http'):
                                video_url = f"https://www.youtube.com/watch?v={video_url}"
                            elif not video_url and video.get('id'):
                                video_url = f"https://www.youtube.com/watch?v={video.get('id')}"
                            
                            if video_url:
                                results.append({
                                    'title': video['title'],
                                    'url': video_url
                                })
                    return results
                
                return []
                
        except Exception as e:
            return f"Errore nella ricerca: {str(e)}"
    def get_song_duration(self, filename):
        """Restituisce la durata totale del file in secondi."""
        filepath = os.path.join(self.download_path, filename)
        try:
            audio = MP3(filepath)
            return audio.info.length
        except Exception as e:
            logger.error(f"Errore lettura durata: {e}")
            return 0

    def get_playback_status(self):
        """Restituisce (durata_totale, tempo_trascorso) in secondi."""
        if not self._currently_playing or not self.is_playing():
            return 0, 0
        
        total = self.get_song_duration(self._currently_playing)
        # pygame.mixer.music.get_pos() restituisce i millisecondi
        elapsed = pygame.mixer.music.get_pos() / 1000
        
        return total, elapsed

_music_instance = MusicTool()
@tool
def play_music(url):
    """Riproduce musica cercando su YouTube"""
    return _music_instance.play_any(url)

@tool
def stop_music():
    """Ferma la riproduzione musicale"""

    return _music_instance.stop()

@tool
def play_cached_music(shuffle: bool = True, playlist_name: str = None):
    """Riproduce musica già presente nella cache, già ascoltata in precedenza."""
    return _music_instance.play_all_from_cache(shuffle, playlist_name)

@tool
def list_cached_music():
    """Restituisce la lista dei brani presenti nella cache."""
    songs = _music_instance.list_cached_songs()
    if isinstance(songs, list):
        return "\n".join(f"{idx+1}. {song}" for idx, song in enumerate(songs))
    return songs

@tool
def search_music(query, max_results: int = 20, only_cache: bool = False):
    """
    Cerca musica su YouTube.
    Restituisce una lista con i titoli dei primi risultati senza scaricare nulla.
     - query: stringa di ricerca (es. titolo, artista, album)
     - max_results: numero massimo di risultati da restituire (default 20)
     - only_cache: se True, cerca solo nella cache locale senza accedere a online (default False)
     -return: lista di stringhe con i titoli dei brani trovati o messaggio di errore
    """
    results = _music_instance.search_any(query, max_results, only_cache)
    print(f"Risultati ricerca per '{query}' (only_cache={only_cache}): {results}")
    return results

@tool
def get_playlists():
    """
        Restituisce la lista delle playlist disponibili
            - Restituisce una lista di oggetti {"name": nome_playlist, "path": path_completo, "songs": [lista_brani]}
    """

    #list files txt in dir MusicCacheDir e restituisci una lista di oggetti {"name": nome_file_senza_estensione, "path": path_completo} ordinata per nome
    files = os.listdir(MUSIC_CACHE_DIR)
    playlists = []
    for filename in files:
        logger.debug(f"Controllo file: {filename}")
        if filename.endswith(".txt"):
            logger.info(f"File playlist trovato: {filename}")
            with open(os.path.join(MUSIC_CACHE_DIR, filename), "r") as f:
                songs = [line.strip() for line in f.readlines() if line.strip()]
            playlists.append({"name": filename[:-4].replace("_playlist", ""), "path": os.path.join(MUSIC_CACHE_DIR, filename), "songs": songs})

    return playlists
    

# Funzioni esterne per controllo da joystick o altri moduli
def stop_music_external():
    """Funzione esterna per fermare la musica (es. da joystick)."""
    return _music_instance.stop()

def get_currently_playing():
    """Restituisce il titolo del brano attualmente in riproduzione, se disponibile."""
    return _music_instance._currently_playing

def get_music_progress():
    """Restituisce lo stato della riproduzione attuale (durata totale e tempo trascorso)."""
    total, elapsed = _music_instance.get_playback_status()
    return {"total_seconds": total, "elapsed_seconds": elapsed}