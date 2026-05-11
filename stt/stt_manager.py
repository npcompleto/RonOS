import time
import threading
import logging
import queue
import os
import wave
import json
from typing import Callable, Optional
from datetime import datetime
import utils

import numpy as np
import sounddevice as sd
import webrtcvad
from scipy.signal import lfilter, firwin

from stt.models.whispher import Transcriber
from vosk import Model, KaldiRecognizer

from event_manager import EventManager

import openwakeword
from openwakeword.model import Model as OpenWakeWordModel

logger = logging.getLogger(__name__)

#FIXME bruttino
import pygame

class SpeechToTextManager:
    """
    Gestore Speech-to-Text ottimizzato per Raspberry Pi con supporto Debug Audio.
    """

    # --- Costanti ---
    TARGET_SAMPLE_RATE = 16000       
    VAD_FRAME_DURATION_MS = 30       
    VAD_FRAME_SAMPLES = TARGET_SAMPLE_RATE * VAD_FRAME_DURATION_MS // 1000  
    AUDIO_QUEUE_MAXSIZE = 150        
    TRANSCRIPTION_QUEUE_MAXSIZE = 10 
    MIN_SPEECH_DURATION_S = 0.8      

    def __init__(
        self,
        config,
        on_transcription: Optional[Callable[[str], None]] = None,
        on_wake: Optional[Callable[[str], None]] = None,
        model_size: str = "small",
        language: str = "it",
        vad_aggressiveness: int = 1,
        save_audio: bool = False,
    ):
        self._config = config
        self._on_transcription = on_transcription
        self._on_wake = on_wake
        self._language = language
        self._is_awake = False
        self._save_audio = save_audio
        self._wakeword_handler = getattr(config, "WAKEWORD_HANDLER", "vosk")

        # Configurazione salvataggio debug
        if self._save_audio:
            self._debug_dir = "debug_audio"
            os.makedirs(self._debug_dir, exist_ok=True)
            logger.info(f"💾 Modalità debug audio attiva. File salvati in: {self._debug_dir}")

        # Parametri hardware
        self._input_sr: int = getattr(config, "SAMPLE_RATE", 44100)
        self._device_index = getattr(config, "AUDIO_DEVICE_INDEX", None)
        self._silence_timeout: float = float(
            getattr(config, "SILENCE_DURATION_SECONDS", 0.6)
        )

        # Resampling logic
        self._needs_resampling = (self._input_sr != self.TARGET_SAMPLE_RATE)
        if self._needs_resampling:
            self._resample_ratio = self.TARGET_SAMPLE_RATE / self._input_sr
            nyquist = self._input_sr / 2.0
            cutoff = self.TARGET_SAMPLE_RATE / 2.0
            self._aa_filter = firwin(31, cutoff / nyquist)
            self._aa_state = np.zeros(len(self._aa_filter) - 1)
        
        # Modelli
        self._transcriber = Transcriber(model_size, language)
        self._vad = webrtcvad.Vad(vad_aggressiveness)

        # Vosk Wake Word setup
        lista_parole = config.VOSK_WAKE_WORDS + ["uhm", "ehm", "mmm", "ok", "allora", "ecco", "[unk]"]
        stringa_grammar = json.dumps(lista_parole)
        voskmodel = Model(model_name=f"vosk-model-small-{self._language}-0.22")
        self._wakeword_recognizer = KaldiRecognizer(voskmodel, self.TARGET_SAMPLE_RATE, stringa_grammar)

        # OpenWakeWord setup
        wakeword_model_path = os.path.join(os.path.dirname(__file__), 'models/Ok_Ron.onnx')
        if not os.path.exists(wakeword_model_path):
            raise FileNotFoundError(f"Il file del modello non esiste in: {wakeword_model_path}")
        openwakeword.utils.download_models()
        self._wakeword_model = OpenWakeWordModel(wakeword_models=[wakeword_model_path], inference_framework="onnx")

        # Code e Stato
        self._raw_queue = queue.Queue(maxsize=self.AUDIO_QUEUE_MAXSIZE)
        self._transcription_queue = queue.Queue(maxsize=self.TRANSCRIPTION_QUEUE_MAXSIZE)
        self._running = threading.Event()
        self._is_speaking = False
        self._stream: Optional[sd.InputStream] = None
        self._threads: list[threading.Thread] = []

    # ------------------------------------------------------------------ #
    #                          UTILITY SALVATAGGIO                       #
    # ------------------------------------------------------------------ #

    def _save_wav(self, audio_data: np.ndarray, prefix: str) -> None:
        """Salva l'audio post-elaborato in formato WAV per debug."""
        if not self._save_audio:
            return
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        filename = os.path.join(self._debug_dir, f"{prefix}_{timestamp}.wav")
        
        pcm_data = (np.clip(audio_data, -1.0, 1.0) * 32767).astype(np.int16)
        
        try:
            with wave.open(filename, 'wb') as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(self.TARGET_SAMPLE_RATE)
                wf.writeframes(pcm_data.tobytes())
            logger.debug(f"Audio salvato correttamente: {filename}")
        except Exception as e:
            logger.error(f"Errore durante il salvataggio WAV: {e}")
        return filename

    # ------------------------------------------------------------------ #
    #                        LIFECYCLE PUBBLICO                           #
    # ------------------------------------------------------------------ #

    def start(self) -> None:
        if self._running.is_set(): return
        self._running.set()
        self._is_speaking = False
        self._flush_queue(self._raw_queue)
        self._flush_queue(self._transcription_queue)

        t_vad = threading.Thread(target=self._vad_loop, name="stt-vad", daemon=True)
        t_whisper = threading.Thread(target=self._transcription_worker, name="stt-whisper", daemon=True)
        self._threads = [t_vad, t_whisper]
        for t in self._threads: t.start()

        try:
            self._stream = sd.InputStream(
                samplerate=self._input_sr,
                channels=1,
                dtype="float32",
                device=self._device_index,
                callback=self._audio_callback,
                latency="high",
            )
            self._stream.start()
            logger.info(f"🚀 STT avviato @ {self._input_sr} Hz (Debug Audio: {self._save_audio})")
        except Exception as e:
            logger.error(f"Errore apertura stream: {e}")
            self.stop()

    def stop(self) -> None:
        """Ferma la pipeline STT in modo pulito."""
        if not self._running.is_set(): return
        self._running.clear()
        if self._stream:
            try:
                self._stream.stop()
                self._stream.close()
            except: pass
        for t in self._threads: t.join(timeout=2.0)
        logger.info("STT arrestato.")

    def wait(self) -> None:
        """Blocca il thread principale finché la pipeline è attiva."""
        try:
            while self._running.is_set():
                time.sleep(0.1)
        except KeyboardInterrupt:
            logger.info("Interruzione rilevata (CTRL+C)...")
            self.stop()

    # ------------------------------------------------------------------ #
    #                            PROCESSING                              #
    # ------------------------------------------------------------------ #

    def _audio_callback(self, indata, frames, time_info, status):
        if status and "overflow" not in str(status):
            logger.warning(f"Audio status: {status}")
        try:
            self._raw_queue.put_nowait(indata[:, 0].copy())
        except queue.Full:
            pass

    def _resample_chunk(self, chunk: np.ndarray) -> np.ndarray:
        if not self._needs_resampling: return chunk.astype(np.float32)
        filtered, self._aa_state = lfilter(self._aa_filter, 1.0, chunk, zi=self._aa_state)
        num_out = int(len(filtered) * self._resample_ratio)
        if num_out == 0: return np.array([], dtype=np.float32)
        return np.interp(np.linspace(0, 1, num_out), np.linspace(0, 1, len(filtered)), filtered).astype(np.float32)

    def _vad_loop(self) -> None:
        speech_buffer: list[np.ndarray] = []
        last_voice_time: float = 0.0
        accumulator = np.array([], dtype=np.float32)
        oww_accumulator = np.array([], dtype=np.float32)
        stop_listening_logged = False
        while self._running.is_set():
            try:
                chunk_raw = self._raw_queue.get(timeout=0.5)
            except queue.Empty:
                continue

            chunk_16k = self._resample_chunk(chunk_raw)
            if len(chunk_16k) == 0: continue

            if not pygame.mixer.get_init() or pygame.mixer.music.get_busy():
                if not stop_listening_logged: logger.info("Audio is playing, skipping STT")
                stop_listening_logged = True
                continue
            else:
                stop_listening_logged = False
                em = EventManager()
                em.publish("music", {"message": None, "started": False})
                logger.debug("Sono in ascolto!")

            if not self._is_awake:

                if self._wakeword_handler == "vosk":
                    pcm16 = (np.clip(chunk_16k, -1.0, 1.0) * 32767).astype(np.int16)

                    if self._wakeword_recognizer.AcceptWaveform(pcm16.tobytes()):
                        result = json.loads(self._wakeword_recognizer.Result())
                        text = result.get("text", "").lower().strip()

                        if any(word in text for word in getattr(self._config, "VOSK_WAKE_WORDS", [])):
                            logger.info(f"✨ Wake Word Vosk rilevata: {text}")

                            if self._save_audio:
                                self._save_wav(chunk_16k, "wake_trigger_vosk")

                            self._is_awake = True

                            if self._on_wake:
                                self._on_wake(text)

                    continue

                elif self._wakeword_handler == "openwakeword":
                    # accumuliamo il chunk già resamplato a 16k
                    oww_accumulator = np.concatenate([oww_accumulator, chunk_16k])

                    # openWakeWord vuole frame da 1280 campioni
                    while len(oww_accumulator) >= 1280:
                        oww_frame = oww_accumulator[:1280]
                        oww_accumulator = oww_accumulator[1280:]

                        pcm16_oww = (np.clip(oww_frame, -1.0, 1.0) * 32767).astype(np.int16)

                        prediction = self._wakeword_model.predict(pcm16_oww)

                        threshold = 0.5

                        if self._save_audio:
                            self._save_wav(oww_frame, "wake_trigger_openword")

                        for wakeword_name, score in prediction.items():
                            logger.debug(f"Wake word: {wakeword_name}, score={score}")

                            if score > threshold:
                                logger.info(
                                    f"✨ Wake Word OpenWakeWord rilevata: "
                                    f"{wakeword_name} (score={score})"
                                )

                                self._is_awake = True
                                oww_accumulator = np.array([], dtype=np.float32)

                                if self._on_wake:
                                    self._on_wake(wakeword_name)

                                break

                        if self._is_awake:
                            break

                    continue

                else:
                    logger.warning(
                        f"Wakeword handler sconosciuto: {self._wakeword_handler}"
                    )
                    continue
                

            accumulator = np.concatenate([accumulator, chunk_16k])
            while len(accumulator) >= self.VAD_FRAME_SAMPLES:
                frame = accumulator[: self.VAD_FRAME_SAMPLES]
                accumulator = accumulator[self.VAD_FRAME_SAMPLES :]
                pcm16_vad = (np.clip(frame, -1.0, 1.0) * 32767).astype(np.int16)

                try:
                    is_speech = self._vad.is_speech(pcm16_vad.tobytes(), self.TARGET_SAMPLE_RATE)
                except: continue

                now = time.time()
                if is_speech:
                    if not self._is_speaking:
                        self._is_speaking = True
                        speech_buffer = []
                    speech_buffer.append(frame)
                    last_voice_time = now
                elif self._is_speaking:
                    speech_buffer.append(frame)
                    if now - last_voice_time > self._silence_timeout:
                        self._is_speaking = False
                        full_audio = np.concatenate(speech_buffer)
                        duration = len(full_audio) / self.TARGET_SAMPLE_RATE

                        if duration >= self.MIN_SPEECH_DURATION_S:
                            if self._save_audio:
                                filename = self._save_wav(full_audio, "whisper_segment")
                                utils.play_audio(filename)
                            
                            try:
                                self._transcription_queue.put_nowait(full_audio)
                            except queue.Full:
                                logger.warning("Coda trascrizioni piena.")
                        speech_buffer = []

    def _transcription_worker(self) -> None:
        while self._running.is_set():
            try:
                audio_segment = self._transcription_queue.get(timeout=1.0)
            except queue.Empty: continue

            try:
                segments, _ = self._transcriber.transcribe(audio_segment)
                text = "".join(seg.text for seg in segments).strip()
                
                hallucinations = ["sottotitoli", "buon appetito", "alla prossima", "grazie per la visione","..."]
                is_hallucination = any(h in text.lower() for h in hallucinations)

                if text and not is_hallucination:
                    logger.info(f"✅ Trascrizione: \"{text}\"")
                    if self._on_transcription:
                        self._on_transcription(text)
                        self._is_awake = False 
                else:
                    logger.debug("Trascrizione ignorata (vuota o allucinazione).")
            except Exception as e:
                logger.error(f"Errore Whisper: {e}")
            finally:
                self._transcription_queue.task_done()

    @staticmethod
    def _flush_queue(q: queue.Queue) -> None:
        while not q.empty():
            try: q.get_nowait()
            except queue.Empty: break