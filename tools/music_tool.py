import yt_dlp
import pygame
import os
import glob
import random
import threading
import time
import difflib
from config import logger
from langchain_core.tools import tool

class MusicTool:
    def __init__(self):
        if not pygame.mixer.get_init():
            pygame.mixer.init()
        self.download_path = "music_cache"
        if not os.path.exists(self.download_path):
            os.makedirs(self.download_path)
            
        self._playlist = []
        self._current_index = 0
        self._stop_event = False
        self._playlist_thread = None

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
        logger.info("[MusicTool] Thread playlist terminato.")

    def _play_current_file(self):
        """Carica e suona il brano all'indice corrente della playlist."""
        if 0 <= self._current_index < len(self._playlist):
            filename = self._playlist[self._current_index]
            filepath = os.path.join(self.download_path, filename)
            pygame.mixer.music.load(filepath)
            pygame.mixer.music.play()
            logger.info(f"In riproduzione dalla cache: {filename}")
            return filename
        return None

    def play_all_from_cache(self, shuffle=True):
        """Avvia la riproduzione di tutti i brani in cache via Thread."""
        self.stop() # Ferma tutto il precedente
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

    def play_from_cache(self, query):
        """Cerca e riproduce un singolo brano dalla cache."""
        logger.debug(f"Ricerca '{query}' in cache...")
        self.stop()
        songs = self.get_cached_songs()
        if not songs: return None, "Cache vuota."

        target_file = None
        try:
            index = int(query) - 1
            if 0 <= index < len(songs): target_file = songs[index]
        except ValueError:
            matches = difflib.get_close_matches(query, songs, n=1, cutoff=0.3)
            if matches: target_file = matches[0]

        if target_file:
            filepath = os.path.join(self.download_path, target_file)
            pygame.mixer.music.load(filepath)
            pygame.mixer.music.play()
            return target_file, f"In riproduzione dalla cache: {target_file}"
        return None, "Non trovato in cache."

    def play_download(self, query):
        """Scarica da YouTube e riproduce (interrompe playlist se attiva)."""
        logger.debug(f"Scaricamento di '{query}'...")
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
                'default_search': 'ytsearch1',
                'quiet': True,
                'no_overwrites': True
            }
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(query, download=True)
                video_info = info['entries'][0]
                logger.debug(f"Video info: {video_info}")
                filename = ydl.prepare_filename(video_info).rsplit('.', 1)[0] + ".mp3"
                
                pygame.mixer.music.load(filename)
                pygame.mixer.music.play()
                return f"Scaricato e in riproduzione: {video_info['title']}"
        except Exception as e:
            return f"Errore download: {str(e)}"

    def play_any(self, query):
        """Cerca in cache, se fallisce scarica."""
        logger.debug(f"Ricerca '{query}' in cache...")
        title, msg = self.play_from_cache(query)
        if title:
            return msg
        return self.play_download(query)

    # --- CONTROLLO ---

    def stop(self):
        """Ferma musica e interrompe il thread della playlist."""
        self._stop_event = True # Segnala al thread di uscire
        pygame.mixer.music.stop()
        pygame.mixer.music.unload()
        
        if self._playlist_thread and self._playlist_thread.is_alive():
            # Non usiamo join(timeout) qui per evitare di bloccare il bot 
            # Il thread uscirà al prossimo 'sleep' grazie allo stop_event
            pass 
            
        self._playlist = []
        self._current_index = 0
        return "Musica e playlist fermate."

    def is_playing(self):
        return pygame.mixer.music.get_busy()

_music_instance = MusicTool()
@tool
def play_music(query):
    """Riproduce musica cercando su YouTube"""
    return _music_instance.play_any(query)

@tool
def stop_music():
    """Ferma la riproduzione musicale"""
    return _music_instance.stop()

@tool
def play_cached_music(shuffle: bool = True):
    """Riproduce musica già presente nella cache, già ascoltata in precedenza."""
    return _music_instance.play_all_from_cache(shuffle)