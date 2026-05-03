import time
import threading
import numpy as np
import sounddevice as sd
import webrtcvad
import queue
from faster_whisper import WhisperModel

class WebRTCAlexaSTT:
    def __init__(self, config):
        self.config = config

        # Parametri Hardware
        self.input_sr = config.SAMPLE_RATE 
        self.target_sr = 16000
        
        # Carichiamo Whisper
        self.model = WhisperModel("small", device="cpu", compute_type="int8")
        self.vad = webrtcvad.Vad(1)

        # Usiamo una coda con dimensione massima per evitare accumuli infiniti in RAM
        self.raw_audio_queue = queue.Queue(maxsize=100)
        self.transcript_queue = queue.Queue()
        
        self.running = False
        self.is_speaking = False

    def _callback(self, indata, frames, time_info, status):
        """Callback critica: deve essere la più veloce possibile."""
        if status:
            # Stampiamo solo se non è un semplice overflow (che gestiremo col buffer)
            if 'overflow' in str(status):
                pass 
        try:
            # Mettiamo nella coda senza bloccare (block=False)
            self.raw_audio_queue.put_nowait(indata[:, 0].copy())
        except queue.Full:
            # Se la coda è piena, scartiamo il pacchetto vecchio per far spazio al nuovo
            pass

    def _transcription_worker(self):
        """Thread Whisper: elabora l'audio quando il parlato finisce."""
        while self.running:
            try:
                audio_data = self.transcript_queue.get(timeout=1)
                self.config.logger.info("📡 Trascrizione in corso...")
                segments, _ = self.model.transcribe(audio_data, language="it")
                text = "".join(s.text for s in segments).strip()
                if text:
                    print(f"\n>> {text}\n")
                self.transcript_queue.task_done()
            except queue.Empty:
                continue

    def _process_loop(self):
        """Thread VAD: Gestisce il resampling e la logica Alexa."""
        speech_buffer = []
        last_voice_time = 0
        silence_timeout = self.config.SILENCE_DURATION_SECONDS
        
        # Buffer interno per accumulare frame da 30ms (480 campioni a 16kHz)
        accumulator = np.array([], dtype=np.float32)

        while self.running:
            try:
                # Recupera i dati a 44100Hz
                chunk_44k = self.raw_audio_queue.get(timeout=1)
                
                # Resampling iper-veloce (Decimazione approssimata)
                # Da 44.1 a 16k il fattore è circa 2.75. Prendiamo un campione ogni 2 o 3 alternati.
                # Per semplicità e velocità, usiamo l'interpolazione lineare su scala ridotta
                num_samples_target = int(len(chunk_44k) * self.target_sr / self.input_sr)
                chunk_16k = np.interp(
                    np.linspace(0, 1, num_samples_target),
                    np.linspace(0, 1, len(chunk_44k)),
                    chunk_44k
                ).astype(np.float32)

                accumulator = np.concatenate([accumulator, chunk_16k])

                # WebRTCVAD vuole frame da 30ms (480 campioni)
                while len(accumulator) >= 480:
                    frame = accumulator[:480]
                    accumulator = accumulator[480:]

                    # Conversione PCM16
                    pcm16 = (np.clip(frame, -1, 1) * 32767).astype(np.int16)
                    
                    is_speech = self.vad.is_speech(pcm16.tobytes(), self.target_sr)
                    now = time.time()

                    if is_speech:
                        if not self.is_speaking:
                            self.is_speaking = True
                            self.config.logger.info("🎤 Rilevato parlato...")
                            speech_buffer = []
                        speech_buffer.append(frame)
                        last_voice_time = now
                    elif self.is_speaking:
                        speech_buffer.append(frame)
                        if now - last_voice_time > silence_timeout:
                            self.is_speaking = False
                            self.config.logger.info("🛑 Analisi frase...")
                            self.transcript_queue.put(np.concatenate(speech_buffer))
                            speech_buffer = []

            except queue.Empty:
                continue

    def listen(self):
        self.running = True
        t_vad = threading.Thread(target=self._process_loop, daemon=True)
        t_whisper = threading.Thread(target=self._transcription_worker, daemon=True)
        t_vad.start()
        t_whisper.start()

        # Configurazione "Safe Mode" per SoundDevice
        try:
            with sd.InputStream(
                samplerate=self.input_sr,
                channels=1,
                dtype="float32",
                # blocksize=0 permette al sistema di ottimizzare il carico
                blocksize=0, 
                device=self.config.AUDIO_DEVICE_INDEX,
                callback=self._callback,
                # 'high' aggiunge latenza ma elimina i crash per overflow
                latency='high' 
            ):
                self.config.logger.info("🚀 STT Avviato correttamente.")
                while self.running:
                    time.sleep(0.1)
        except KeyboardInterrupt:
            self.running = False