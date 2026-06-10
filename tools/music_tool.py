from logging import info
import yt_dlp
import pygame
import os
import glob
import random
import threading
import time
import json
from config import logger, MUSIC_CACHE_DIR
from langchain_core.tools import tool
from event_manager import EventManager
from status import get_global_status, State
from mutagen.mp3 import MP3
from mutagen.id3 import ID3
import re

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
        self._lyrics_events = None

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
        self._lyrics_events = None #reset le lyrics di eventuali vecchi brani
        if 0 <= self._current_index < len(self._playlist):
            filename = self._playlist[self._current_index]
            filepath = os.path.join(self.download_path, filename)
            pygame.mixer.music.load(filepath)
            em = EventManager()
            if get_global_status().set_state(State.DANCING, reason="Riproduzione musicale (_play_current_file)"):
                em.publish("music", {"message": filename, "started": True})
                self._currently_playing = filename
                self._lyrics_events = None #reset le lyrics di eventuali vecchi brani
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
        self._lyrics_events = None #reset le lyrics di eventuali vecchi brani
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

    def _clear_filename(self, title):
        # 2. Prende il titolo originale
        titolo_originale = title
        
        # 3. Rimuove parentesi tonde e quadre con tutto il loro contenuto
        titolo_pulito = re.sub(r'\[.*?\]|\(.*?\)', '', titolo_originale)
        
        # 4. Rimuove caratteri speciali (tiene solo lettere, numeri, spazi, trattini e underscore)
        titolo_pulito = re.sub(r'[^a-zA-Z0-9\s\-_]', '', titolo_pulito)
        
        # 5. Rimuove spazi multipli consecutivi e spazi vuoti a inizio/fine
        titolo_pulito = re.sub(r'\s+', ' ', titolo_pulito).strip()
        
        return titolo_pulito.title() #Rende maiuscolo la prima lettera di ogni parola
    
    # --- LOGICA RICERCA E DOWNLOAD ---

    def play_song_by_name(self, song_name: str):
        """Riproduce un brano dalla cache dato il suo nome."""
        self.stop()  # Ferma la riproduzione precedente
        self._lyrics_events = None  # Reset lyrics
        
        logger.debug(f"Ricerca canzone '{song_name}' in cache...")
        
        # Se il nome contiene .mp3, usalo direttamente
        if song_name.lower().endswith('.mp3'):
            target_file = song_name
        else:
            # Aggiungi .mp3 se non presente
            target_file = song_name if song_name.lower().endswith('.mp3') else f"{song_name}.mp3"
        
        filepath = os.path.join(self.download_path, target_file)
        
        if not os.path.exists(filepath):
            logger.error(f"File non trovato: {filepath}")
            return False, f"Canzone '{song_name}' non trovata nella cache"
        
        try:
            pygame.mixer.music.load(filepath)
            em = EventManager()
            if get_global_status().set_state(State.DANCING, reason="Riproduzione musicale (play_song_by_name)"):
                em.publish("music", {"message": target_file, "started": True})
                self._currently_playing = target_file
                pygame.mixer.music.play()
                logger.info(f"In riproduzione: {target_file}")
                return True, f"In riproduzione: {target_file}"
            else:
                logger.warning("Impossibile riprodurre la musica, stato attuale non permette la transizione a DANCING.")
                return False, "Impossibile riprodurre la musica in questo momento"
        except Exception as e:
            logger.error(f"Errore nella riproduzione: {e}")
            return False, f"Errore: {str(e)}"

    def play_from_cache(self, url):
        """Cerca e riproduce un singolo brano dalla cache."""
        if not url.startswith(self.download_path):
            print(f"URL '{url}' non è nella cache.")
            return None, f"URL '{url}' non è nella cache."

        print(f"Ricerca '{url}' in cache...")
        target_file = os.path.basename(url)
        print(f"Target file: {target_file}")
        self._lyrics_events = None #reset le lyrics di eventuali vecchi brani
        if target_file:
            filepath = os.path.join(self.download_path, target_file)
            print(f"Filepath: {filepath}")
            pygame.mixer.music.load(filepath)
            pygame.mixer.music.play()
            self._set_currently_playing(target_file)
            return target_file, f"In riproduzione dalla cache: {target_file}"
        return None, "Non trovato in cache."

    def play_download(self, url, only_download=False, download_lyrics=False):
        """Scarica da un URL diretto e riproduce (interrompe playlist se attiva)."""
        logger.debug(f"Scaricamento diretto di '{url}'...")
        em = EventManager()
        
        if not only_download: self.stop()
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
                'no_overwrites': True,
                'writeautomaticsub': True,    # sottotitoli automatici
                'writesubtitles': True,
                #'subtitleslangs': ['it'], 
                #'subtitlesformat': "vtt",
                "cookiefile": "cookies.txt",
                # 'default_search' rimosso per forzare l'interpretazione come URL
            }

            language = None
            caption_formats = []
            filesize = 0
            selected_format = None
            original_title = None

            try:
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    #Recuperiamo le informazione sul download
                    info = ydl.extract_info(url, download=False)
                    logger.info(info.keys())
                    filesize = info.get("filesize")
                    language = info.get("language")
                    original_title = info.get("title")
                    captions = info.get("automatic_captions").get(language)
                    caption_formats = [c.get("ext") for c in captions]
                    logger.info(f"{language}-{filesize}-{caption_formats}")
                
                
                priority = [
                    'json3',
                    'srv3',
                    'srv2',
                    'srv1',
                    'vtt',
                    'ttml',
                    'srt'
                ]

                selected_format = next(
                    (fmt for fmt in priority if fmt in caption_formats),
                    None
                )
            except Exception as e:
                logger.error(e)


            ydl_opts = {
                'format': 'bestaudio/best',
                'outtmpl': f'{self.download_path}/{self._clear_filename(original_title)}.%(ext)s',
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': '192',
                }],
                'quiet': False,
                'no_overwrites': True,
                "cookiefile": "cookies.txt"
            }
            
            if download_lyrics and selected_format:
                ydl_opts['writeautomaticsub']=True
                ydl_opts['writesubtitles']=True
                ydl_opts['subtitleslangs']=[language]
                ydl_opts['subtitlesformat']=selected_format
                logger.info(f"Trovate lyrics {language} with format {selected_format}")
            else:
                logger.warning(f"Non scarico i sottotitoli: download_lyrics: {download_lyrics} - selected_format: {selected_format}")

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                if not only_download: em.publish("downloading", {"message": f"Sto scaricando da {url}", "started": True})

                # Scarica direttamente
                info = ydl.extract_info(url, download=True)
                
                # Se è un singolo video, info è il dizionario del video stesso
                video_info = info
                
                filename = ydl.prepare_filename(video_info).rsplit('.', 1)[0] + ".mp3"
                if not only_download: em.publish("downloading", {"message": None, "started": False})
                
                if not only_download: pygame.mixer.music.load(filename)
                if not only_download: 
                    if get_global_status().set_state(State.DANCING, reason="Riproduzione musicale"):
                        em.publish("music", {"message": None, "started": True})
                        self._set_currently_playing(filename)
                        pygame.mixer.music.play()
                        return f"Scaricato e in riproduzione: {video_info.get('title', 'Video')}"
                    else:
                        logger.warning("Impossibile riprodurre la musica.")
                        return "Musica scaricata ma non posso riprodurla in questo momento."
                else:
                    logger.info(f"Scaricato: {video_info.get('title')}")
                    return f"Scaricato: {video_info.get('title')}" 
                    
        except Exception as e:
            if not only_download: em.publish("loading", {"message": f"Errore download: {str(e)}", "started": False})
            if not only_download: self._set_currently_playing(None)
            logger.error(e)
            return f"Errore download: {str(e)}"

    def _set_currently_playing(self, filename):
        """Imposta il nome del file del brano attualmente in riproduzione."""
        logger.info(f"Impostazione currently_playing: {filename}")
        self._currently_playing = filename

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
        self._lyrics_events = None
        pygame.mixer.music.stop()
        pygame.mixer.music.unload()
        
        if self._playlist_thread and self._playlist_thread.is_alive():
            # Non usiamo join(timeout) qui per evitare di bloccare il bot 
            # Il thread uscirà al prossimo 'sleep' grazie allo stop_event
            pass 
            
        self._playlist = []
        self._current_index = 0
        self._set_currently_playing(None)
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
                search_query = f"ytsearch{max_results}:{query} lyrics"
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
            try:
                audio = MP3(filename)
                return audio.info.length
            except Exception as e2:
                logger.error(f"Errore lettura durata: {e2}")
                return 0

    def get_playback_status(self):
        """Restituisce (durata_totale, tempo_trascorso) in secondi."""
        if not self._currently_playing or not self.is_playing():
            return 0, 0
        
        total = self.get_song_duration(self._currently_playing)
        # pygame.mixer.music.get_pos() restituisce i millisecondi
        elapsed = pygame.mixer.music.get_pos() / 1000
        
        return total, elapsed

    def _parse_lrc_timestamp(self, timestamp_str):
        """Converte un timestamp LRC [mm:ss.xx] in millisecondi."""
        try:
            # Formato: mm:ss.xx oppure mm:ss
            parts = timestamp_str.split(':')
            minutes = int(parts[0])
            seconds_parts = parts[1].split('.')
            seconds = int(seconds_parts[0])
            centiseconds = int(seconds_parts[1]) if len(seconds_parts) > 1 else 0
            # Se il valore dopo il punto ha 3 cifre è già in ms, altrimenti sono centesimi
            if len(seconds_parts) > 1 and len(seconds_parts[1]) == 3:
                ms = centiseconds
            else:
                ms = centiseconds * 10
            return (minutes * 60 + seconds) * 1000 + ms
        except Exception as e:
            logger.error(f"Errore nel parsing del timestamp LRC '{timestamp_str}': {e}")
            return 0

    def _load_lrc_file(self, filepath):
        """Carica un file .lrc e restituisce una lista di (start_ms, testo) ordinata per tempo."""
        events = []
        lrc_pattern = re.compile(r'\[(\d+:\d+(?:\.\d+)?)\](.*)')
        with open(filepath, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                match = lrc_pattern.match(line)
                if match:
                    start_ms = self._parse_lrc_timestamp(match.group(1))
                    text = match.group(2).strip()
                    if text:  # Ignora righe vuote
                        events.append({"start_ms": start_ms, "text": text})
        events.sort(key=lambda e: e["start_ms"])
        logger.info(f"Caricati {len(events)} eventi LRC da {filepath}")
        return events

    def get_current_text(self):
        filename = None
        if not self._currently_playing:
            logger.info("Nessuna canzone in riproduzione")
            return None

        # Cerca il file .lrc corrispondente alla canzone in riproduzione
        if not self._lyrics_events:
            lrc_path = os.path.join(self.download_path, f"{self._currently_playing.replace('.mp3', '')}.lrc")
            if os.path.exists(lrc_path):
                self._lyrics_events = self._load_lrc_file(lrc_path)

        if not self._lyrics_events:
            return None

        current_ms = self.get_playback_status()[1] * 1000

        # Trova la riga corrente: l'ultima riga il cui timestamp è <= current_ms
        current_text = None
        for i, event in enumerate(self._lyrics_events):
            if event["start_ms"] <= current_ms:
                current_text = event["text"]
            else:
                break

        return current_text

    def add_lyrics(self, song_filename:str, lrc_text: str):
        lrc_filename = song_filename.replace('.mp3', '') + ".lrc"
        #save lrc file 
        with open(os.path.join(self.download_path, lrc_filename), "w", encoding="utf-8") as f:
            f.write(lrc_text)
        logger.info(f"Lyrics saved to {os.path.join(self.download_path, lrc_filename)}")

            
        

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

def get_playlists_external():
    return get_playlists.invoke({})

def stop_music_external():
    """Funzione esterna per fermare la musica (es. da joystick)."""
    return _music_instance.stop()

def get_currently_playing():
    """Restituisce il titolo del brano attualmente in riproduzione, se disponibile.
    prendi solo il nome del file senza estensione e senza path e senza stringhe tra () o [] o {} e restituiscilo come titolo
     - Esempio: "Canzone (feat. Artista) [Live].mp3" -> "Canzone"
    """    
    if _music_instance._currently_playing:
        filename = os.path.basename(_music_instance._currently_playing)
        title = filename.rsplit('.', 1)[0] if '.' in filename else filename
        # Rimuove stringhe tra parentesi
        title = re.sub(r"[\(\[\{].*?[\)\]\}]", "", title).strip()
        return title
    return _music_instance._currently_playing

def get_music_progress():
    """Restituisce lo stato della riproduzione attuale (durata totale e tempo trascorso)."""
    total, elapsed = _music_instance.get_playback_status()
    return {"total_seconds": total, "elapsed_seconds": elapsed}

def get_cache_songs():
    """Restituisce la lista dei brani presenti nella cache (funzione esterna)."""
    return _music_instance.get_cached_songs()
def download_music_external(url):
    """Funzione esterna per scaricare musica da URL diretto senza riprodurre (es. da joystick)."""
    return _music_instance.play_download(url, only_download=True, download_lyrics=False)

def get_current_lyrics_text():
    return _music_instance.get_current_text()

def add_lyrics_external(song_filename:str, lrc_text: str):
    _music_instance.add_lyrics(song_filename, lrc_text)

def play_song_from_cache_external(song_name: str):
    """Funzione esterna per avviare la riproduzione di una canzone dalla cache."""
    return _music_instance.play_song_by_name(song_name)