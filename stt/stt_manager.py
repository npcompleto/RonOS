"""
SpeechToTextManager - Gestore STT per Raspberry Pi (sample rate 44100 Hz)

Gestisce l'intero pipeline Speech-to-Text:
  1. Cattura audio dal microfono a 44100 Hz (nativo del device)
  2. Resampling con filtro anti-aliasing a 16000 Hz (richiesto da Whisper/VAD)
  3. Voice Activity Detection (WebRTC VAD)
  4. Trascrizione con Faster Whisper

Uso:
    from stt.stt_manager import SpeechToTextManager
    import config

    def on_transcription(text):
        print(f"Trascritto: {text}")

    stt = SpeechToTextManager(config, on_transcription=on_transcription)
    stt.start()
    # ...
    stt.stop()
"""

import time
import threading
import logging
import queue
from typing import Callable, Optional

import numpy as np
import sounddevice as sd
import webrtcvad
from scipy.signal import lfilter, firwin

from stt.models.whispher import Transcriber

from vosk import Model, KaldiRecognizer
import json
import config

logger = logging.getLogger(__name__)


class SpeechToTextManager:
    """
    Gestore Speech-to-Text ottimizzato per Raspberry Pi.

    Progettato per dispositivi con sample rate nativo 44100 Hz.
    Esegue resampling a 16000 Hz con filtro anti-aliasing per
    compatibilità con Whisper e WebRTC VAD.

    Args:
        config: Oggetto di configurazione con i seguenti attributi:
            - SAMPLE_RATE (int): Sample rate del dispositivo (default 44100)
            - AUDIO_DEVICE_INDEX (int|None): Indice del dispositivo audio
            - SILENCE_DURATION_SECONDS (float): Secondi di silenzio per chiudere una frase
            - logger: Logger dell'applicazione
        on_transcription (Callable[[str], None]): Callback invocata ad ogni trascrizione
        model_size (str): Dimensione del modello Whisper (default "small")
        language (str): Lingua per la trascrizione (default "it")
        vad_aggressiveness (int): Aggressività VAD da 0 (permissivo) a 3 (aggressivo)
    """

    # --- Costanti ---
    TARGET_SAMPLE_RATE = 16000       # Whisper e WebRTC VAD richiedono 16 kHz
    VAD_FRAME_DURATION_MS = 30       # Durata frame VAD (10, 20, o 30 ms)
    VAD_FRAME_SAMPLES = TARGET_SAMPLE_RATE * VAD_FRAME_DURATION_MS // 1000  # 480 campioni
    AUDIO_QUEUE_MAXSIZE = 150        # Limite coda audio grezza (previene OOM)
    TRANSCRIPTION_QUEUE_MAXSIZE = 10 # Limite coda trascrizioni pendenti
    MIN_SPEECH_DURATION_S = 0.8      # Durata minima parlato per trascrivere (in secondi)

    def __init__(
        self,
        config,
        on_transcription: Optional[Callable[[str], None]] = None,
        on_wake: Optional[Callable[[str], None]] = None,
        model_size: str = "small",
        language: str = "it",
        vad_aggressiveness: int = 1,
    ):
        self._config = config
        self._on_transcription = on_transcription
        self._on_wake = on_wake
        self._language = language
        self._is_awake = False

        # Parametri hardware
        self._input_sr: int = getattr(config, "SAMPLE_RATE", 44100)
        self._device_index = getattr(config, "AUDIO_DEVICE_INDEX", None)
        self._silence_timeout: float = float(
            getattr(config, "SILENCE_DURATION_SECONDS", 0.6)
        )

        # Resampling: necessario solo se input_sr != target_sr
        self._needs_resampling = (self._input_sr != self.TARGET_SAMPLE_RATE)

        if self._needs_resampling:
            self._resample_ratio = self.TARGET_SAMPLE_RATE / self._input_sr

            # Filtro anti-aliasing leggero (FIR a 31 tap)
            # Cutoff a Nyquist della frequenza target (8000 Hz)
            nyquist = self._input_sr / 2.0
            cutoff = self.TARGET_SAMPLE_RATE / 2.0
            self._aa_filter = firwin(31, cutoff / nyquist)
            self._aa_state = np.zeros(len(self._aa_filter) - 1)

            logger.info(
                f"Resampling: {self._input_sr} Hz → {self.TARGET_SAMPLE_RATE} Hz "
                f"(ratio={self._resample_ratio:.4f}, AA filter={len(self._aa_filter)} tap)"
            )
        else:
            logger.info(
                f"Sample rate nativo {self._input_sr} Hz = target, "
                f"resampling non necessario."
            )

        self._transcriber = Transcriber(model_size, language)

        # WebRTC VAD
        self._vad = webrtcvad.Vad(vad_aggressiveness)

        # Code inter-thread
        self._raw_queue: queue.Queue[np.ndarray] = queue.Queue(
            maxsize=self.AUDIO_QUEUE_MAXSIZE
        )
        self._transcription_queue: queue.Queue[np.ndarray] = queue.Queue(
            maxsize=self.TRANSCRIPTION_QUEUE_MAXSIZE
        )

        # Stato
        self._running = threading.Event()
        self._is_speaking = False
        self._stream: Optional[sd.InputStream] = None
        self._threads: list[threading.Thread] = []

        lista_parole = config.WAKE_WORDS + ["uhm", "ehm", "mmm", "ok", "allora", "ecco", "[unk]"]

        # Converti la lista in una stringa JSON
        stringa_grammar = json.dumps(lista_parole)

        voskmodel = Model(model_name=f"vosk-model-small-{self._language}-0.22")
        self._wakeword_recognizer = KaldiRecognizer(voskmodel, self.TARGET_SAMPLE_RATE, stringa_grammar)
        self._wakeword_recognizer.SetWords(False)
        self._wakeword_recognizer.SetPartialWords(False)

    # ------------------------------------------------------------------ #
    #                        LIFECYCLE PUBBLICO                           #
    # ------------------------------------------------------------------ #

    def start(self) -> None:
        """Avvia la pipeline STT (cattura audio, VAD, trascrizione)."""
        if self._running.is_set():
            logger.warning("SpeechToTextManager è già in esecuzione.")
            return

        self._running.set()
        self._is_speaking = False

        # Svuota le code
        self._flush_queue(self._raw_queue)
        self._flush_queue(self._transcription_queue)

        # Avvia i worker thread
        t_vad = threading.Thread(
            target=self._vad_loop, name="stt-vad", daemon=True
        )
        t_whisper = threading.Thread(
            target=self._transcription_worker, name="stt-whisper", daemon=True
        )
        self._threads = [t_vad, t_whisper]
        t_vad.start()
        t_whisper.start()

        # Apri lo stream audio
        try:
            self._stream = sd.InputStream(
                samplerate=self._input_sr,
                channels=1,
                dtype="float32",
                blocksize=0,  # Lascia al driver la scelta ottimale
                device=self._device_index,
                callback=self._audio_callback,
                latency="high",  # Più latenza = meno overflow su RPi
            )
            self._stream.start()
            logger.info(
                f"🚀 STT avviato — dispositivo [{self._device_index}] "
                f"@ {self._input_sr} Hz"
            )
        except Exception as e:
            logger.error(f"Errore apertura stream audio: {e}")
            self.stop()
            raise

    def stop(self) -> None:
        """Ferma la pipeline STT in modo pulito."""
        if not self._running.is_set():
            return

        logger.info("🛑 Arresto STT in corso...")
        self._running.clear()

        # Chiudi lo stream audio
        if self._stream is not None:
            try:
                self._stream.stop()
                self._stream.close()
            except Exception as e:
                logger.warning(f"Errore chiusura stream: {e}")
            finally:
                self._stream = None

        # Attendi i thread (con timeout per non bloccare indefinitamente)
        for t in self._threads:
            t.join(timeout=3.0)
        self._threads.clear()

        logger.info("STT arrestato.")

    def restart(self) -> None:
        """Riavvia la pipeline STT."""
        logger.info("🔄 Riavvio STT...")
        self.stop()
        time.sleep(0.5)
        self.start()

    @property
    def is_running(self) -> bool:
        """Restituisce True se la pipeline è attiva."""
        return self._running.is_set()

    def wait(self) -> None:
        """Blocca il thread corrente finché la pipeline è attiva."""
        try:
            while self._running.is_set():
                time.sleep(0.1)
        except KeyboardInterrupt:
            self.stop()

    # ------------------------------------------------------------------ #
    #                        CALLBACK AUDIO                               #
    # ------------------------------------------------------------------ #

    def _audio_callback(self, indata: np.ndarray, frames: int, time_info, status) -> None:
        """
        Callback chiamata da sounddevice ad ogni blocco audio.
        Deve essere il più veloce possibile — nessuna elaborazione qui.
        """
        if status and "overflow" not in str(status):
            logger.warning(f"Audio status: {status}")
        try:
            self._raw_queue.put_nowait(indata[:, 0].copy())
        except queue.Full:
            # Scarta pacchetti vecchi se la pipeline non riesce a stare al passo
            pass

    # ------------------------------------------------------------------ #
    #                     VAD + RESAMPLING LOOP                           #
    # ------------------------------------------------------------------ #

    def _resample_chunk(self, chunk: np.ndarray) -> np.ndarray:
        """
        Resampling veloce: filtro anti-aliasing (FIR) + interpolazione lineare.
        Se il sample rate è già 16 kHz, restituisce il chunk così com'è.
        """
        if not self._needs_resampling:
            return chunk.astype(np.float32)

        # 1. Filtro anti-aliasing (mantiene stato tra chunk per evitare artefatti)
        filtered, self._aa_state = lfilter(
            self._aa_filter, 1.0, chunk, zi=self._aa_state
        )

        # 2. Decimazione con interpolazione lineare (velocissima su ARM)
        num_out = int(len(filtered) * self._resample_ratio)
        if num_out == 0:
            return np.array([], dtype=np.float32)

        resampled = np.interp(
            np.linspace(0, 1, num_out),
            np.linspace(0, 1, len(filtered)),
            filtered,
        ).astype(np.float32)

        return resampled

    def _vad_loop(self) -> None:
        """
        Thread VAD: preleva audio grezzo dalla coda, esegue resampling
        con filtro anti-aliasing, e usa WebRTC VAD per segmentare il parlato.
        """
        speech_buffer: list[np.ndarray] = []
        last_voice_time: float = 0.0
        accumulator = np.array([], dtype=np.float32)
        frames_processed = 0

        while self._running.is_set():
            try:
                chunk_raw = self._raw_queue.get(timeout=0.5)
            except queue.Empty:
                continue

            if not self._is_awake:
                pcm16 = (np.clip(chunk_raw, -1.0, 1.0) * 32767).astype(np.int16)
                result_json = self._wakeword_recognizer.AcceptWaveform(pcm16.tobytes())
                if result_json:
                    result = json.loads(self._wakeword_recognizer.Result())
                    text = result.get("text", "").lower().strip()
                    if text:
                        config.logger.debug(f"Vosk ha sentito: {text}")
                        if text in config.WAKE_WORDS:
                            self._is_awake = True
                            self._on_wake(text)
                            
                continue

            # --- Resampling veloce (filtro AA + np.interp) ---
            chunk_16k = self._resample_chunk(chunk_raw)
            if len(chunk_16k) == 0:
                continue

            accumulator = np.concatenate([accumulator, chunk_16k])

            # Elabora frame da 30ms (480 campioni a 16 kHz)
            while len(accumulator) >= self.VAD_FRAME_SAMPLES:
                frame = accumulator[: self.VAD_FRAME_SAMPLES]
                accumulator = accumulator[self.VAD_FRAME_SAMPLES :]

                # Conversione a PCM16 per WebRTC VAD
                pcm16 = (np.clip(frame, -1.0, 1.0) * 32767).astype(np.int16)

                try:
                    is_speech = self._vad.is_speech(
                        pcm16.tobytes(), self.TARGET_SAMPLE_RATE
                    )
                except Exception:
                    # WebRTC VAD può fallire su frame corrotti
                    continue

                frames_processed += 1
                now = time.time()

                if is_speech:
                    if not self._is_speaking:
                        self._is_speaking = True
                        logger.info("🎤 Parlato rilevato...")
                        speech_buffer = []
                    speech_buffer.append(frame)
                    last_voice_time = now
                elif self._is_speaking:
                    speech_buffer.append(frame)
                    if now - last_voice_time > self._silence_timeout:
                        self._is_speaking = False
                        full_audio = np.concatenate(speech_buffer)
                        duration = len(full_audio) / self.TARGET_SAMPLE_RATE

                        # Ignora segmenti troppo corti (rumore, click, ecc.)
                        if duration < self.MIN_SPEECH_DURATION_S:
                            logger.debug(
                                f"Segmento troppo corto ({duration:.2f}s < "
                                f"{self.MIN_SPEECH_DURATION_S}s), ignorato."
                            )
                            speech_buffer = []
                            continue

                        logger.info(
                            f"🛑 Fine parlato — {duration:.1f}s di audio catturato"
                        )
                        try:
                            self._transcription_queue.put_nowait(full_audio)
                            # TODO usare qui VOSK se ancora non è stata rilevata la wake word
                        except queue.Full:
                            logger.warning(
                                "Coda trascrizioni piena, segmento scartato."
                            )
                        speech_buffer = []

                # Log diagnostico periodico (ogni ~10 secondi di audio)
                if frames_processed % 333 == 0:
                    qsize = self._raw_queue.qsize()
                    rms = float(np.sqrt(np.mean(frame ** 2)))
                    logger.debug(
                        f"VAD alive — {frames_processed} frames, "
                        f"raw_queue={qsize}/{self.AUDIO_QUEUE_MAXSIZE}, "
                        f"speaking={self._is_speaking}, rms={rms:.6f}"
                    )

        logger.debug("VAD loop terminato.")

    # ------------------------------------------------------------------ #
    #                    WHISPER TRANSCRIPTION WORKER                     #
    # ------------------------------------------------------------------ #

    def _transcription_worker(self) -> None:
        """
        Thread Whisper: preleva segmenti di audio dalla coda di trascrizione
        e li trascrive usando Faster Whisper.
        """
        while self._running.is_set():
            try:
                audio_segment = self._transcription_queue.get(timeout=1.0)
            except queue.Empty:
                continue

            try:
                duration = len(audio_segment) / self.TARGET_SAMPLE_RATE
                logger.info(f"📡 Trascrizione in corso ({duration:.1f}s)...")
                segments, info = self._transcriber.transcribe(audio_segment)
                text = "".join(seg.text for seg in segments).strip()

                if text and "sottotitoli" not in text.lower() and "buon appetito!" not in text.lower():
                    logger.info(f"✅ Trascrizione: \"{text}\"")
                    if self._on_transcription:
                        try:
                            self._on_transcription(text)
                            self._is_awake = False
                        except Exception as cb_err:
                            logger.error(
                                f"Errore nel callback di trascrizione: {cb_err}"
                            )
                else:
                    logger.debug("Trascrizione vuota (solo rumore?).")

            except Exception as e:
                logger.error(f"Errore durante la trascrizione: {e}", exc_info=True)
            finally:
                self._transcription_queue.task_done()

        logger.debug("Transcription worker terminato.")

    # ------------------------------------------------------------------ #
    #                           UTILITY                                   #
    # ------------------------------------------------------------------ #

    @staticmethod
    def _flush_queue(q: queue.Queue) -> None:
        """Svuota una coda in modo sicuro."""
        while True:
            try:
                q.get_nowait()
            except queue.Empty:
                break
