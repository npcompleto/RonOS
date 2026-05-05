import yt_dlp
import pygame
import os
import config
import glob
import difflib
from langchain_core.tools import tool

class MusicTool:
    def __init__(self):
        if not pygame.mixer.get_init():
            pygame.mixer.init()
        self.download_path = "music_cache"
        if not os.path.exists(self.download_path):
            os.makedirs(self.download_path)

    def get_cached_songs(self):
        """Restituisce la lista dei nomi dei file MP3 in cache."""
        files = glob.glob(os.path.join(self.download_path, "*.mp3"))
        return [os.path.basename(f) for f in files]

    def play_from_cache(self, query):
        """
        Cerca una canzone in cache tramite indice numerico o stringa.
        Se la trova, la riproduce e restituisce il titolo.
        """
        songs = self.get_cached_songs()
        if not songs:
            return None, "La cache è vuota."

        target_file = None

        # 1. Prova a vedere se l'utente ha inserito un numero
        try:
            index = int(query) - 1
            if 0 <= index < len(songs):
                target_file = songs[index]
        except ValueError:
            # 2. Se non è un numero, cerca il match testuale più vicino
            matches = difflib.get_close_matches(query, songs, n=1, cutoff=0.3)
            if matches:
                target_file = matches[0]

        if target_file:
            filepath = os.path.join(self.download_path, target_file)
            pygame.mixer.music.load(filepath)
            pygame.mixer.music.play()
            return target_file, f"Riproduzione dalla cache: {target_file}"
        
        return None, "Canzone non trovata nella cache."

    def play_any(self, query):
        """
        Logica ibrida: prima cerca in cache, se fallisce scarica da YouTube.
        """
        # Prova prima in cache (ricerca testuale)
        cached_name, msg = self.play_from_cache(query)
        if cached_name:
            return msg
        
        # Se non trovata, scarica
        return self.play_download(query)

    def play_download(self, query):
        """Scarica e riproduce da YouTube."""
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
                filename = ydl.prepare_filename(video_info).rsplit('.', 1)[0] + ".mp3"
                
                pygame.mixer.music.load(filename)
                pygame.mixer.music.play()
                return f"Scaricato e in riproduzione: {video_info['title']}"
        except Exception as e:
            return f"Errore: {str(e)}"

    def stop(self):
        pygame.mixer.music.stop()
        return "Musica fermata."

@tool
def play_music(query):
    """Riproduce musica cercando su YouTube"""
    return MusicTool().play_any(query)

@tool
def stop_music():
    """Ferma la riproduzione musicale"""
    return MusicTool().stop()

@tool
def play_cached_music(query):
    """Riproduce musica già presente nella cache, già ascoltata in precedenza."""
    return MusicTool().play_from_cache(query)