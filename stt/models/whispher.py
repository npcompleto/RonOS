import config
import os

logger = config.logger

try:
    import hailo_platform
    from hailo_platform import VDevice, HEF
    # Tentiamo di usare l'API GenAI introdotta in HailoRT 5.0+ per una gestione più semplice di Whisper
    try:
        from hailo_platform.genai import Speech2Text, Speech2TextTask
        GENAI_AVAILABLE = True
    except ImportError:
        GENAI_AVAILABLE = False
    
    HAILO_AVAILABLE = True
    logger.info(f"hailo_platform version {hailo_platform.__version__} detected.")
except ImportError:
    logger.error("hailo_platform not found. Ensure HailoRT is installed.")
    from faster_whisper import WhisperModel
    HAILO_AVAILABLE = False
    GENAI_AVAILABLE = False


class Transcriber:
    def __init__(self, model_size, language):
        self._model_size = model_size
        self.mode = None
        
        if HAILO_AVAILABLE and GENAI_AVAILABLE:
            self.hef_path =os.path.join("models", f"whisper_{model_size}.hef")

            logger.info(f"Initializing Hailo Whisper model using hailo_platform ({self.hef_path})...")
        
            try:
                logger.info("Creazione VDevice Hailo...")
                self.vdevice = VDevice()
                logger.info("VDevice creato con successo.")
            except Exception as e:
                logger.error(f"Errore durante la creazione del VDevice Hailo: {e}")
                raise
            try:
                logger.info(f"Caricamento modello HEF ({self.hef_path}) tramite Speech2Text (GenAI)...")
                self.model = Speech2Text(self.vdevice, self.hef_path)
                self.mode = "genai"
                logger.info("Modello Hailo caricato e pronto.")
            except Exception as e:
                logger.error(f"Errore durante il caricamento del modello GenAI: {e}")
                raise
        else:
            logger.error("hailo_platform.genai not available. Please ensure HailoRT 5.3+ is installed for best experience.")
            # Modello Whisper (caricamento eager: meglio fallire subito)
            logger.info(f"Caricamento modello Whisper '{model_size}' (compute_type=int8)...")
            self._model = WhisperModel(model_size, device="cpu", compute_type="int8")
            logger.info("Modello Whisper caricato.")
            self._language = language
    
    def transcribe(self, audio):
        if self.mode == "genai":
            # L'API GenAI di Hailo accetta audio 16kHz, mono, float32 [-1, 1]
            # stt_manager.py passa già l'audio in questo formato.
            text = self.model.generate_all_text(
                audio_data=audio,
                task=Speech2TextTask.TRANSCRIBE,
                language=language
            )
            # Create a dummy segment object to match faster-whisper API expected by stt_manager.py
            class Segment:
                def __init__(self, text):
                    self.text = text
            
            segments = [Segment(text)]
            info = None
            
            return segments, info
        else:
            return self._model.transcribe(audio, language=self._language)