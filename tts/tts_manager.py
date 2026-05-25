import os
import queue
import threading
import hashlib
import requests
from piper import PiperVoice
import config
from utils import play_audio, stop_audio  # <-- Importiamo anche stop_audio
import re
import wave
from status import get_global_status, State


class TextToSpeechManager:
    def __init__(self, cache_dir="./speech_cache", expression_callback=None, start_speaking_callback=None, stop_speaking_callback=None):
        self.model_path = config.PIPER_MODEL_PATH
        self.model_url = config.PIPER_MODEL_URL
        self.config_path = f"{self.model_path}.json"
        self.cache_dir = cache_dir
        self.expression_callback = expression_callback
        self.start_speaking_callback = start_speaking_callback
        self.stop_speaking_callback = stop_speaking_callback
        
        self.queue = queue.Queue()
        self.stop_event = threading.Event()
        
        # Evento per interrompere la sintesi e la riproduzione in corso
        self._abort_speaking = threading.Event()
        
        if not os.path.exists(self.cache_dir):
            os.makedirs(self.cache_dir)

        # Scarica il modello se mancante
        self._ensure_model_exists()

        # Inizializza la voce Piper
        self.voice = PiperVoice.load(self.model_path, config_path=self.config_path)

    def _ensure_model_exists(self):
        """Scarica i file .onnx e .json se non sono presenti."""
        for path, url in [(self.model_path, self.model_url), 
                          (self.config_path, self.model_url + ".json")]:
            if not os.path.exists(path):
                print(f"Download in corso: {os.path.basename(path)}...")
                r = requests.get(url, stream=True)
                r.raise_for_status()
                with open(path, 'wb') as f:
                    for chunk in r.iter_content(chunk_size=8192):
                        f.write(chunk)

    def _get_hash_name(self, text):
        """Genera un percorso file unico basato sull'hash del testo."""
        clean_text = text.lower().strip()
        hash_digest = hashlib.md5(clean_text.encode()).hexdigest()
        return os.path.join(self.cache_dir, f"{hash_digest}.wav")

    def _generate_wav(self, text, output_path):
        """Usa Piper per generare un file WAV."""
        with open(output_path, "wb") as wav_file:
            self.voice.synthesize(text, wav_file)

    def _split_text_and_tags(self, text):
        pattern = r'(\[\[.*?\]\])|([^\[]+?([.!?]+|(?=\[\[)|\Z))'
        matches = [m.group().strip() for m in re.finditer(pattern, text)]
        return [m for m in matches if m]

    def speak(self, text, filename="speech_chunk.wav", play=True):
        if not isinstance(text, str):
            text = str(text)
        
        text = text.replace("**", "")
        sentences = self._split_text_and_tags(text)
        config.logger.info(f"Sentences: {sentences}")
        
        if not sentences:
            return

        if not get_global_status().set_state(State.SPEAKING, reason="Inizio sintesi vocale"):
            config.logger.warning("Impossibile iniziare a parlare, stato attuale non permette la transizione a SPEAKING.")
            return
        config.logger.info(f"Ron dice: '{text}' (in {len(sentences)} pezzi)")
        
        # Reset del flag di interruzione all'inizio di ogni sessione di parlato
        self._abort_speaking.clear()
        
        try:
            for i, sentence in enumerate(sentences):
                # Controllo di sicurezza: se è stato richiesto lo stop, interrompi subito il ciclo
                if self._abort_speaking.is_set():
                    config.logger.info("Sintesi interrotta prima di elaborare il pezzo successivo.")
                    break

                config.logger.info(f"Sintesi pezzo {i+1}/{len(sentences)}: '{sentence}'")
                if sentence.startswith("[[") and sentence.endswith("]]"):
                    if self.expression_callback:
                        self.expression_callback(sentence[2:-2])
                    continue
                else:
                    with wave.open(filename, "wb") as wav_file:
                        has_alnum = any(char.isalnum() for char in sentence)
                        if not has_alnum:
                            config.logger.warning(f"Nessun dato alfanumerico in '{sentence}', salto la sintesi")
                            continue
                        
                        for j, audio_chunk in enumerate(self.voice.synthesize(sentence)):
                            # Ulteriore controllo granulare durante la generazione di Piper
                            if self._abort_speaking.is_set():
                                break
                            
                            if j == 0:
                                wav_file.setnchannels(audio_chunk.sample_channels)
                                wav_file.setsampwidth(audio_chunk.sample_width)
                                wav_file.setframerate(audio_chunk.sample_rate)

                            wav_file.writeframes(audio_chunk.audio_int16_bytes)
                        
                        # Se l'interruzione è avvenuta durante la generazione del file, esci dal ciclo
                        if self._abort_speaking.is_set():
                            break

                        if self.start_speaking_callback:
                            self.start_speaking_callback()
                        
                        if play:
                            # Nota: play_audio è bloccante, ma se stop_speaking() viene chiamato da un altro 
                            # thread, stop_audio() sbloccherà immediatamente l'attesa all'interno di play_audio.
                            play_audio(filename, volume=0.5)
                        
                        if self.stop_speaking_callback:
                            self.stop_speaking_callback()
                    
        except Exception as e:
            config.logger.error(f"Errore durante la sintesi vocale: {e}")
        finally:
            get_global_status().set_state(State.IDLE, reason="Sintesi terminata")
            # Pulizia finale dello stato se interrotto
            if self._abort_speaking.is_set():
                if self.stop_speaking_callback:
                    self.stop_speaking_callback()
                config.logger.info("Pipeline TTS resettata dopo interruzione.")

    def stop_speaking(self):
        """
        Interrompe immediatamente la sintesi e la riproduzione dell'audio in corso.
        Sicuro da chiamare da thread esterni (es. thread VAD/Wake Word).
        """
        config.logger.info("🛑 Richiesta interruzione riproduzione vocale...")
        
        # 1. Attiva il flag per bloccare i cicli interni di speak()
        self._abort_speaking.set()
        
        # 2. Interrompe immediatamente l'audio a livello hardware tramite Pygame (Canale 0)
        stop_audio()
        if get_global_status()._state == State.SPEAKING:
            get_global_status().set_state(State.IDLE, reason="Interruzione parlato")