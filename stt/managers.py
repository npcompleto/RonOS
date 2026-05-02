import queue
import time
import numpy as np
import sounddevice as sd
import torch
from faster_whisper import WhisperModel


class AlexaLikeSTT:

    def __init__(self, config):

        self.config = config
        self.sample_rate = config.SAMPLE_RATE

        # Whisper
        self.model = WhisperModel(
            "small",
            device="cpu",
            compute_type="int8"
        )

        # Audio queue
        self.audio_queue = queue.Queue()

        # Stream
        self.stream = None

        # Silero VAD
        self.vad_model, self.utils = torch.hub.load(
            repo_or_dir="snakers4/silero-vad",
            model="silero_vad",
            force_reload=False
        )

        self.get_speech_timestamps = self.utils[0]

        # buffers
        self.audio_buffer = []
        self.preroll_buffer = []
        self.is_speaking = False
        self.last_voice_time = 0

        # tuning
        self.preroll_size = 5  # ~500ms se chunk=100ms
        self.silence_timeout = config.SILENCE_DURATION_SECONDS

    # -------------------------
    # AUDIO CALLBACK
    # -------------------------
    def _callback(self, indata, frames, time_info, status):
        if status:
            self.config.logger.warning(status)

        self.audio_queue.put(indata.copy().flatten())

    # -------------------------
    # SILERO VAD CHECK
    # -------------------------
    def _extract_speech(self, audio_np):

        tensor = torch.from_numpy(audio_np)

        speech_ts = self.get_speech_timestamps(
            tensor,
            self.vad_model,
            sampling_rate=self.sample_rate
        )

        if not speech_ts:
            return None

        segments = [
            audio_np[ts["start"]:ts["end"]]
            for ts in speech_ts
        ]

        return np.concatenate(segments)

    # -------------------------
    # TRANSCRIBE
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

        self.config.logger.info("Alexa-like STT avviato...")

        blocksize = int(self.sample_rate * 0.1)  # 100ms

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
                    # PRE-ROLL BUFFER SEMPRE
                    # -------------------------
                    self.preroll_buffer.append(chunk)
                    if len(self.preroll_buffer) > self.preroll_size:
                        self.preroll_buffer.pop(0)

                    self.audio_buffer.append(chunk)

                    # -------------------------
                    # DETECT VOICE VIA ENERGY (FAST GATE)
                    # -------------------------
                    rms = np.sqrt(np.mean(chunk ** 2))

                    if rms > self.config.VAD_THRESHOLD:

                        if not self.is_speaking:
                            self.config.logger.debug("🎤 voce iniziata")
                            self.is_speaking = True

                        self.last_voice_time = now

                    # -------------------------
                    # END OF SPEECH
                    # -------------------------
                    if self.is_speaking and (
                        now - self.last_voice_time > self.silence_timeout
                    ):

                        self.is_speaking = False
                        self.config.logger.debug("🛑 fine frase")

                        raw_audio = np.concatenate(self.audio_buffer)

                        # reset buffer
                        self.audio_buffer = []
                        self.preroll_buffer = []

                        # -------------------------
                        # SILERO CLEANUP
                        # -------------------------
                        speech_audio = self._extract_speech(raw_audio)

                        if speech_audio is None:
                            continue

                        # -------------------------
                        # TRANSCRIBE
                        # -------------------------
                        text = self._transcribe(speech_audio)

                        if text:
                            self.config.logger.info(f"📝 {text}")
                            full_text += " " + text

            except KeyboardInterrupt:
                self.config.logger.info("Stop manuale")

        return full_text