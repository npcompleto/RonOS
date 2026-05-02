import config
import queue
import time
import sounddevice as sd
import numpy as np
"""
Whisper
"""
from faster_whisper import WhisperModel


class SpeechToTextManager:
    def __init__(self):
        # Ottimizzazione: beam_size=1 e cpu_threads riducono il tempo di calcolo su CPU
        self.model = WhisperModel("small", device="cpu", compute_type="int8", cpu_threads=4)
        self.audio_queue = queue.Queue()
        self.sample_rate = config.SAMPLE_RATE
        self.stream = None

    def _audio_callback(self, indata, frames, time, status):
        if status:
            config.logger.warning(f"Status Audio: {status}")
        # Mettiamo i dati nella coda (già pronti in float32 per evitare conversioni dopo)
        self.audio_queue.put(indata.copy().flatten())

    def listen(self):
        config.logger.info("Inizio ascolto realtime...")
        
        # Setup stream: usiamo float32 direttamente per saltare la conversione 32768.0
        self.stream = sd.InputStream(
            samplerate=self.sample_rate,
            channels=1,
            dtype='float32', 
            device=config.AUDIO_DEVICE_INDEX,
            callback=self._audio_callback,
            blocksize=int(self.sample_rate * 0.5) # Processa blocchi da 0.5 secondi
        )
        
        audio_buffer = []
        full_text = ""
        is_speaking = False
        last_speech_time = time.time()

        with self.stream:
            try:
                while True: # Ciclo infinito per realtime vero
                    try:
                        # Timeout breve per non bloccare il loop
                        audio_chunk = self.audio_queue.get(timeout=1.0)
                    except queue.Empty:
                        continue

                    audio_buffer.append(audio_chunk)
                    
                    # Calcolo RMS veloce
                    rms = np.sqrt(np.mean(audio_chunk**2))
                    current_time = time.time()

                    if rms > config.VAD_THRESHOLD:
                        if not is_speaking:
                            is_speaking = True
                            config.logger.debug("Voce rilevata...")
                        last_speech_time = current_time
                    else:
                        # Se c'è silenzio e avevamo iniziato a parlare...
                        if is_speaking and (current_time - last_speech_time > config.SILENCE_DURATION_SECONDS):
                            is_speaking = False
                            config.logger.debug("Fine frase, trascrivo...")
                            
                            # Concatenazione e trascrizione immediata
                            segment_audio = np.concatenate(audio_buffer)
                            transcript = self._transcribe_segment(segment_audio)
                            
                            if transcript.strip():
                                full_text += " " + transcript
                                config.logger.info(f"Trascrizione: {transcript}")
                            
                            audio_buffer = [] # Reset buffer per la prossima frase

            except KeyboardInterrupt:
                config.logger.info("Stop manuale ricevuto.")
            finally:
                config.logger.info(f"Testo totale: {full_text}")
                return full_text

    def _transcribe_segment(self, audio_data):
        # Parametri ottimizzati per velocità:
        # beam_size=1 è molto più veloce del default 5
        segments, _ = self.model.transcribe(
            audio_data,
            language="it",
            beam_size=1, 
            vad_filter=True,
            vad_parameters=dict(min_silence_duration_ms=500)
        )
        return "".join([seg.text for seg in segments])
