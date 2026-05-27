import threading
import uvicorn
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from event_manager import EventManager
from config import logger, MUSIC_CACHE_DIR
from tools.music_tool import get_playlists_external, get_cache_songs, download_music_external

from fastapi.middleware.cors import CORSMiddleware
import os
import json
from datetime import datetime

app = FastAPI(title="Ron REST Listener")
event_manager = EventManager()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class MessageRequest(BaseModel):
    message: str

class PlaylistRequest(BaseModel):
    name: str

class LogRequest(BaseModel):
    level: str  # DEBUG, INFO, WARNING, ERROR
    message: str
    timestamp: str = None

@app.post("/send_message")
async def send_message(request: MessageRequest):
    """
    Riceve un messaggio via REST e scatena un evento 'message' nel sistema.
    """
    if not request.message.strip():
        raise HTTPException(status_code=400, detail="Messaggio vuoto")
    
    logger.info(f"[REST] Ricevuto messaggio: {request.message}")
    
    # Pubblichiamo l'evento 'message' che verrà catturato da ron.py
    event_manager.publish("message", {"text": request.message})
    
    return {"status": "success", "message": "Evento inviato correttamente"}

@app.get("/health")
async def health():
    return {"status": "ok"}

@app.get("/api/quizzes")
async def list_quizzes():
    knowledge_dir = "agents/knowledge"
    if not os.path.exists(knowledge_dir):
        return {"quizzes": []}
    
    quizzes = []
    for file in os.listdir(knowledge_dir):
        if file.endswith(".json") and "test" in file:
            quizzes.append(file)
    return {"quizzes": quizzes}

@app.get("/api/quizzes/{filename}")
async def get_quiz(filename: str):
    if not filename.endswith(".json") or ".." in filename:
        raise HTTPException(status_code=400, detail="Invalid filename")
        
    filepath = os.path.join("agents/knowledge", filename)
    if not os.path.exists(filepath):
        raise HTTPException(status_code=404, detail="Quiz not found")
        
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/cache_songs")
async def list_cache_songs():
    """Restituisce la lista dei brani presenti nella cache."""
    songs = get_cache_songs()
    return {"songs": songs if songs else []}

@app.get("/api/playlists")
async def list_playlists():
    playlists_dir = MUSIC_CACHE_DIR
    if not os.path.exists(playlists_dir):
        os.makedirs(playlists_dir, exist_ok=True)
        return {"playlists": []}
    
    playlists = get_playlists_external()
    # Ordina per nome
    playlists_sorted = sorted(playlists, key=lambda x: x.get('name', '').lower())
    logger.debug(f"Playlists trovate: {playlists_sorted}")
    return {"playlists": playlists_sorted}

@app.post("/api/playlists")
async def create_playlist(request: PlaylistRequest):
    if not request.name.strip():
        raise HTTPException(status_code=400, detail="Playlist name cannot be empty")
    
    playlists_dir = MUSIC_CACHE_DIR
    os.makedirs(playlists_dir, exist_ok=True)
    
    # Sanitize filename
    safe_name = "".join(c for c in request.name if c.isalnum() or c in (' ', '-', '_')).strip()
    if not safe_name:
        raise HTTPException(status_code=400, detail="Invalid playlist name")
    
    txt_filepath = os.path.join(playlists_dir, f"{safe_name}_playlist.txt")
    
    # Check if already exists
    if os.path.exists(txt_filepath):
        raise HTTPException(status_code=409, detail="Playlist already exists")
    
    try:
        # Create JSON metadata file
        playlist_data = {
            "name": request.name,
            "songs": []
        }
        
        # Create empty TXT file with song list (one filename per line)
        with open(txt_filepath, "w", encoding="utf-8") as f:
            f.write("")
        
        return {"status": "success", "playlist": safe_name}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/playlists/{name}")
async def delete_playlist(name: str):
    if ".." in name or "/" in name:
        raise HTTPException(status_code=400, detail="Invalid playlist name")
    
    playlists_dir = MUSIC_CACHE_DIR
    filepath = os.path.join(playlists_dir, f"{name}_playlist.txt")
    
    if not os.path.exists(filepath):
        raise HTTPException(status_code=404, detail="Playlist not found")
    
    try:
        os.remove(filepath)
        return {"status": "success", "message": "Playlist deleted"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/playlists/{playlist_name}/songs/{song_name}")
async def remove_song_from_playlist(playlist_name: str, song_name: str):
    """Rimuove una canzone da una playlist (non cancella il file MP3)."""
    if ".." in playlist_name or "/" in playlist_name:
        raise HTTPException(status_code=400, detail="Invalid playlist name")
    
    playlists_dir = MUSIC_CACHE_DIR
    filepath = os.path.join(playlists_dir, f"{playlist_name}_playlist.txt")
    
    if not os.path.exists(filepath):
        raise HTTPException(status_code=404, detail="Playlist not found")
    
    try:
        # Leggi il file
        with open(filepath, "r", encoding="utf-8") as f:
            songs = [line.strip() for line in f.readlines() if line.strip()]
        
        # Rimuovi la canzone (decodifica il nome se è URL encoded)
        decoded_song = os.path.basename(song_name)
        songs = [s for s in songs if s != decoded_song]
        
        # Riscrivi il file
        with open(filepath, "w", encoding="utf-8") as f:
            for song in songs:
                f.write(f"{song}\n")
        
        return {"status": "success", "message": "Song removed from playlist"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

class AddSongToPlaylistRequest(BaseModel):
    song_name: str
    playlist_name: str

@app.post("/api/playlists/add_song")
async def add_song_to_playlist(request: AddSongToPlaylistRequest):
    """Aggiunge una canzone a una playlist."""
    if not request.song_name.strip() or not request.playlist_name.strip():
        raise HTTPException(status_code=400, detail="Song name and playlist name cannot be empty")
    
    if ".." in request.playlist_name or "/" in request.playlist_name:
        raise HTTPException(status_code=400, detail="Invalid playlist name")
    
    playlists_dir = MUSIC_CACHE_DIR
    filepath = os.path.join(playlists_dir, f"{request.playlist_name}_playlist.txt")
    
    if not os.path.exists(filepath):
        raise HTTPException(status_code=404, detail="Playlist not found")
    
    try:
        # Leggi il file
        with open(filepath, "r", encoding="utf-8") as f:
            songs = [line.strip() for line in f.readlines() if line.strip()]
        
        # Controlla se la canzone è già nella playlist
        if request.song_name in songs:
            raise HTTPException(status_code=409, detail="Song already in playlist")
        
        # Aggiungi la canzone
        songs.append(request.song_name)
        
        # Riscrivi il file
        with open(filepath, "w", encoding="utf-8") as f:
            for song in songs:
                f.write(f"{song}\n")
        
        return {"status": "success", "message": "Song added to playlist"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/cache_songs/{song_name}")
async def delete_cache_song(song_name: str):
    """Cancella un file MP3 dalla cache."""
    if ".." in song_name or "/" in song_name:
        raise HTTPException(status_code=400, detail="Invalid song name")
    
    playlists_dir = MUSIC_CACHE_DIR
    filepath = os.path.join(playlists_dir, song_name)
    
    # Verifica che il file sia un MP3
    if not filepath.endswith(".mp3"):
        raise HTTPException(status_code=400, detail="Only MP3 files can be deleted")
    
    if not os.path.exists(filepath):
        raise HTTPException(status_code=404, detail="Song not found")
    
    try:
        os.remove(filepath)
        return {"status": "success", "message": "Song deleted from cache"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

class DownloadCacheSongRequest(BaseModel):
    url: str

@app.post("/api/cache_songs/download")
async def download_cache_song(request: DownloadCacheSongRequest):
    """Scarica un URL nella cache locale usando download_music_external."""
    if not request.url.strip():
        raise HTTPException(status_code=400, detail="URL cannot be empty")

    try:
        filename = download_music_external(request.url)
        if not filename:
            raise HTTPException(status_code=500, detail="Download failed")
        return {"status": "success", "filename": filename}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/logs")
async def log_from_pwa(request: LogRequest):
    """Riceve log dalla PWA e li scrive nel file ron_pwa.log"""
    try:
        log_file = "ron_pwa.log"
        timestamp = request.timestamp or datetime.now().isoformat()
        log_line = f"[{timestamp}] [{request.level}] {request.message}\n"
        
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(log_line)
        
        return {"status": "success"}
    except Exception as e:
        logger.error(f"Errore nella scrittura del log PWA: {e}")
        raise HTTPException(status_code=500, detail=str(e))

class RestListener:
    def __init__(self, host="0.0.0.0", port=8001):
        self.host = host
        self.port = port
        self.thread = None

    def start(self):
        """Avvia il server in un thread separato."""
        def run():
            logger.info(f"Avvio REST Listener su {self.host}:{self.port}")
            uvicorn.run(app, host=self.host, port=self.port, log_level="warning")
        
        self.thread = threading.Thread(target=run, daemon=True)
        self.thread.start()

    def stop(self):
        # Uvicorn non ha un modo semplice per essere fermato da un thread esterno
        # in modo pulito senza segnali, ma essendo un thread daemon si chiuderà con l'app.
        logger.info("REST Listener in fase di chiusura...")
