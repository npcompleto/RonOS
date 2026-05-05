import os
import queue
import threading
import hashlib
import requests
from piper import PiperVoice
import config
from utils import play_audio
import re
import wave


class TextToSpeechManager:
    def __init__(self, cache_dir="./speech_cache"):
        self.model_path = config.PIPER_MODEL_PATH
        self.model_url = config.PIPER_MODEL_URL
        self.config_path = f"{self.model_path}.json"
        self.cache_dir = cache_dir
        
        self.queue = queue.Queue()
        self.stop_event = threading.Event()
        
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

    def speak(self, text, filename="speech_chunk.wav", play=True):
        if not isinstance(text, str):
            text = str(text)
        
        # Pulizia testo
        text = re.sub(r'[^\w\s\d.,!?;:()\'\"-/]', '', text)
        text = text.replace("**", "")
        sentences = [s.strip() for s in re.split(r'(?<=[!.;?])\s+', text) if s.strip()]
        
        if not sentences:
            return

        config.logger.info(f"Ron dice: '{text}' (in {len(sentences)} pezzi)")
        
        try:
            for i, sentence in enumerate(sentences):
                config.logger.info(f"Sintesi pezzo {i+1}/{len(sentences)}: '{sentence}'")
        
                # Apri come file binario normale, NON con wave.open
                with wave.open(filename, "wb") as wav_file:
                   for j, audio_chunk in enumerate(self.voice.synthesize(sentence)):
                        if j == 0:
                            wav_file.setnchannels(audio_chunk.sample_channels)
                            wav_file.setsampwidth(audio_chunk.sample_width)
                            wav_file.setframerate(audio_chunk.sample_rate)

                        wav_file.writeframes(audio_chunk.audio_int16_bytes)
                
                if play:
                    play_audio(filename)
                    
        except Exception as e:
            config.logger.error(f"Errore durante la sintesi vocale: {e}")