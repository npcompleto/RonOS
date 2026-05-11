import threading
import uvicorn
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from event_manager import EventManager
from config import logger

app = FastAPI(title="Ron REST Listener")
event_manager = EventManager()

class MessageRequest(BaseModel):
    message: str

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
