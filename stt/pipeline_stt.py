import queue
import time
import numpy as np
import sounddevice as sd
import webrtcvad
from faster_whisper import WhisperModel
import collections
import scipy.io.wavfile as wav


class WebRTCAlexaSTT:

    def __init__(self, config):

        self.config = config
        self.sample_rate = config.SAMPLE_RATE

        # Whisper (CPU optimized)
        self.model = WhisperModel(
            "small",
            device="cpu",
            compute_type="int8"
        )

        # WebRTC VAD (0-3 aggressiveness)
        self.vad = webrtcvad.Vad(2)

        # Audio queue
        self.audio_queue = queue.Queue()

        self.stream = None

        # frame settings (WebRTC richiede frame fissi)
        self.frame_ms = 30  # 10/20/30 ms solo valori validi
        self.frame_size = int(self.sample_rate * self.frame_ms / 1000)

        # buffers
        self.ring_buffer = collections.deque(maxlen=10)  # pre-roll
        self.speech_buffer = []

        self.is_speaking = False
        self.last_voice_time = 0

    # -------------------------
    # AUDIO CALLBACK
    # -------------------------
    def _callback(self, indata, frames, time_info, status):
        if status:
            self.config.logger.warning(status)

        self.audio_queue.put(indata.copy().flatten())

    # -------------------------
    # VAD CHECK (WebRTC richiede PCM16 bytes)
    # -------------------------
    def _is_speech(self, audio_float):

        pcm16 = (audio_float * 32767).astype(np.int16)

        return self.vad.is_speech(
            pcm16.tobytes(),
            self.sample_rate
        )

    # -------------------------
    # WHISPER
    # -------------------------
    def _transcribe(self, audio):

        segments, _ = self.model.transcribe(
            audio,
            language="it",
            beam_size=1,
            vad_filter=False
        )

        return "".join(s.text for s in segments).strip()

    # -------------------------
    # MAIN LOOP
    # -------------------------
    def listen(self):

        self.config.logger.info("WebRTC Alexa-like STT avviato...")

        blocksize = self.frame_size

        self.stream = sd.InputStream(
            samplerate=self.sample_rate,
            channels=1,
            dtype="float32",
            blocksize=blocksize,
            device=self.config.AUDIO_DEVICE_INDEX,
            callback=self._callback
        )

        full_text = ""

        with self.stream:

            try:
                while True:

                    try:
                        chunk = self.audio_queue.get(timeout=1.0)
                    except queue.Empty:
                        continue

                    now = time.time()

                    # -------------------------
                    # VAD CHECK
                    # -------------------------
                    is_speech = self._is_speech(chunk)

                    # -------------------------
                    # PRE-ROLL BUFFER SEMPRE
                    # -------------------------
                    self.ring_buffer.append(chunk)

                    if is_speech:

                        if not self.is_speaking:
                            self.config.logger.debug("🎤 speech start")
                            self.is_speaking = True

                            # includi pre-roll
                            self.speech_buffer = list(self.ring_buffer)

                        self.speech_buffer.append(chunk)
                        self.last_voice_time = now

                    else:

                        if self.is_speaking:
                            self.speech_buffer.append(chunk)

                            # fine frase
                            if now - self.last_voice_time > self.config.SILENCE_DURATION_SECONDS:

                                self.is_speaking = False
                                self.config.logger.debug("🛑 speech end")

                                audio = np.concatenate(self.speech_buffer)

                                self.speech_buffer = []
                                self.ring_buffer.clear()

                                # salva debug wav
                                pcm = (audio * 32767).astype(np.int16)
                                wav.write(
                                    f"debug_{int(now)}.wav",
                                    self.sample_rate,
                                    pcm
                                )

                                # whisper
                                text = self._transcribe(audio)

                                if text:
                                    self.config.logger.info(f"📝 {text}")
                                    full_text += " " + text

            except KeyboardInterrupt:
                self.config.logger.info("Stop manuale")

        return full_text