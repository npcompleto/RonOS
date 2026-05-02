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
        # Ottimizzazione: beam_size=1 e cpu_threads riducono il tempo di calcolo su CPU
        self.model = WhisperModel("small", device="cpu", compute_type="int8", cpu_threads=4)
        self.audio_queue = queue.Queue()
        self.sample_rate = config.SAMPLE_RATE
        self.stream = None
        config.logger.debug(f"Device Audio: {config.AUDIO_DEVICE_INDEX}")
        config.logger.debug(f"Sample Rate: {config.SAMPLE_RATE}")
        config.logger.debug(f"VAD Threshold: {config.VAD_THRESHOLD}")
        config.logger.debug(f"Silence Duration Seconds: {config.SILENCE_DURATION_SECONDS}")

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

                    if rms > float(config.VAD_THRESHOLD):
                        if not is_speaking:
                            is_speaking = True
                            audio_buffer = []   # reset qui
                            config.logger.debug("Voce rilevata...")

                        audio_buffer.append(audio_chunk)
                        last_speech_time = current_time

                    elif is_speaking:
                        audio_buffer.append(audio_chunk)

                        if current_time - last_speech_time > config.SILENCE_DURATION_SECONDS:
                            is_speaking = False
                            config.logger.debug("Fine frase, trascrivo...")
                            
                            # Concatenazione e trascrizione immediata
                            segment_audio = np.concatenate(audio_buffer)
                            transcript = self._transcribe_segment(segment_audio)
                            config.logger.debug(
                                f"segment max={np.max(segment_audio):.4f}, "
                                f"min={np.min(segment_audio):.4f}"
                            )

                            pcm_audio = np.clip(segment_audio, -1.0, 1.0)
                            pcm_audio = (pcm_audio * 32767).astype(np.int16)

                            temp_audio_path = f"debug_audio_{int(current_time)}.wav"
                            scipy.io.wavfile.write(temp_audio_path, self.sample_rate, pcm_audio)
                            
                            stripped_transcript = transcript.strip()
                            if stripped_transcript and stripped_transcript != 'Sottotitoli e revisione a cura di QTSS':
                                full_text += " " + stripped_transcript
                                config.logger.info(f"Trascrizione: {stripped_transcript}")
                            else:
                                config.logger.debug("Nessuna trascrizione valida ricevuta.")
                            audio_buffer = [] # Reset buffer per la prossima frase
            except Exception as e:
                config.logger.error(f"Errore: {e}")
            except KeyboardInterrupt:
                config.logger.info("Stop manuale ricevuto.")
            finally:
                config.logger.info(f"Testo totale: {full_text}")
                return full_text

    def _transcribe_segment(self, audio_data):
        segments, info = self.model.transcribe(
            audio_data,
            language="it",
            beam_size=1,
            vad_filter=False
        )

        texts = [seg.text for seg in segments]
        config.logger.debug(f"Detected language: {info.language}, prob={info.language_probability}")
        config.logger.debug(f"Segments raw: {texts}")

        return "".join(texts)
