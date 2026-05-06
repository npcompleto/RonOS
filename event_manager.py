import threading
from config import logger

class EventManager:
    """
    Gestore di eventi centralizzato (Singleton consigliato) 
    per comunicazioni Broadcast tra i vari moduli.
    """
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        # Implementazione Singleton per avere un unico bus in tutta l'app
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(EventManager, cls).__new__(cls)
                cls._instance._subscribers = {}
        return cls._instance

    def subscribe(self, event_type: str, callback):
        """
        Registra un subscriber per un determinato tipo di evento.
        :param event_type: Stringa identificativa (es. 'music_started')
        :param callback: Funzione da chiamare quando l'evento viene scatenato
        """
        if event_type not in self._subscribers:
            self._subscribers[event_type] = []
        
        if callback not in self._subscribers[event_type]:
            self._subscribers[event_type].append(callback)
            logger.debug(f"[Events] Nuovo subscriber per: {event_type}")

    def unsubscribe(self, event_type: str, callback):
        """Rimuove un subscriber."""
        if event_type in self._subscribers:
            try:
                self._subscribers[event_type].remove(callback)
            except ValueError:
                pass

    def publish(self, event_type: str, data=None):
        """
        Invia un evento a tutti i subscriber registrati.
        :param event_type: Il tipo di evento
        :param data: Dati opzionali da passare (dict, string, etc.)
        """
        if event_type not in self._subscribers:
            return

        logger.debug(f"[Events] Publish {event_type} con dati: {data}")
        
        # Iteriamo su una copia della lista per evitare errori se 
        # un subscriber si disiscrive durante l'esecuzione
        for callback in self._subscribers[event_type][:]:
            try:
                # Eseguiamo la callback in un thread separato per non bloccare il publisher
                threading.Thread(
                    target=callback, 
                    args=(data,), 
                    daemon=True
                ).start()
            except Exception as e:
                logger.error(f"[Events] Errore nella callback di {event_type}: {e}")