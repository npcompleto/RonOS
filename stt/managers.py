import config
import queue
import time
import sounddevice as sd
import numpy as np
import scipy

"""
Whisper
"""
from faster_whisper import WhisperModel


class SpeechToTextManager:
    def __init__(self):
        self.model = WhisperModel("small", device="cpu", compute_type="int8")
        self.audio_queue = queue.Queue()
        self.sample_rate = config.SAMPLE_RATE
        self.stream = None
    
    def listen(self):
        config.logger.info("Listening...")
        config.logger.info("Inizio ascolto realtime con Whisper...")
        
        # Svuota la coda audio esistente
        while not self.audio_queue.empty():
            try: self.audio_queue.get_nowait()
            except queue.Empty: break

        # Avvia lo stream audio se non è attivo
        if self.stream is None:
            self.stream = sd.InputStream(
                samplerate=self.sample_rate,
                channels=1,
                dtype='int16',
                device=config.AUDIO_DEVICE_INDEX,
                callback=self._audio_callback
            )
            self.stream.start()
        
        audio_buffer = []
        start_time = time.time()
        last_speech_time = time.time()
        is_speaking = False
        full_text = ""
        config.logger.info(f"Stream audio avviato: sample_rate={self.sample_rate}, device={config.AUDIO_DEVICE_INDEX}")
        config.logger.info(f"Inizio ciclo di ascolto continuo...")

        try:
            while time.time() - start_time < 60:  # Ascolta per 60 secondi come test
                while self.audio_queue.empty():
                    time.sleep(0.1)

                audio_chunk = self.audio_queue.get()
                audio_buffer.append(audio_chunk)
                current_time = time.time()

                # Rileva la presenza di segnale audio
                audio_rms = np.sqrt(np.mean(audio_chunk**2))
                if audio_rms > config.VAD_THRESHOLD:
                    if not is_speaking:
                        is_speaking = True
                        last_speech_time = current_time
                        config.logger.debug("Voce rilevata...")
                else:
                    if is_speaking and (current_time - last_speech_time > config.SILENCE_DURATION_SECONDS):
                        is_speaking = False
                        config.logger.debug("Fine del parlato rilevata.")

                        # Trascrivi il segmento di audiobuffered
                        if len(audio_buffer) > 0:
                            full_audio = np.concatenate(audio_buffer)
                            
                            # Salva temporaneamente per debug
                            #temp_audio_path = f"debug_audio_{int(start_time)}.wav"
                            #scipy.io.wavfile.write(temp_audio_path, self.sample_rate, full_audio.astype(np.int16))

                            # Esegui la trascrizione
                            transcript = self._transcribe_segment(full_audio)
                            if transcript and transcript.strip():
                                full_text += " " + transcript
                                config.logger.info(f"Trascrizione: {transcript}")

                            audio_buffer = []
                # await asyncio.sleep(0)  
        except Exception as e:
            config.logger.error(f"Errore durante l'ascolto: {e}")
        finally:
            if self.stream:
                self.stream.stop()
                self.stream.close()
                self.stream = None
            
            config.logger.info(f"Ascolto terminato. Testo totale: {full_text}")
            return full_text
        

        
    def _transcribe_segment(self, audio_data):
        config.logger.debug("Transcribing...")
        
        # Converte int16 in float32 normalizzato tra -1.0 e 1.0
        if audio_data.dtype == np.int16:
            audio_data = audio_data.astype(np.float32) / 32768.0

        segments, info = self.model.transcribe(
            audio_data,  # Ora è 1D e float32
            vad_filter=True,
            vad_parameters=dict(
                min_silence_duration_ms=1000,
            ),
            language="it"
        )

        for seg in segments:
            config.logger.debug("[%s] %s" % (seg.start, seg.text))

        # 4. Unire le trascrizioni e pulire l'output
        full_text = " ".join([seg.text for seg in segments])
        return full_text
        

    def _audio_callback(self, indata, frames, time, status):
        """Callback per il flusso audio di sounddevice."""
        if status:
            config.logger.warning(f"Status Audio: {status}")
        # Usa .flatten() per trasformare (N, 1) in (N,)
        self.audio_queue.put(indata.copy().flatten())