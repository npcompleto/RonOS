import logging
import sys
import os
import sounddevice as sd
from dotenv import load_dotenv

# Carica le variabili d'ambiente dal file .env (questo è fondamentale!)
load_dotenv()

# Configurazione logging immediata (prima degli altri import)
logging.basicConfig(
    level=os.getenv("LOG_LEVEL") or logging.INFO,
    format='[%(module)s][%(funcName)s] %(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("ron.log"),
        logging.StreamHandler(sys.stdout)
    ],
    force=True  # Obbliga l'uso di questa configurazione
)

logging.getLogger("faster_whisper").setLevel(logging.WARNING)
logging.getLogger("httpx").setLevel(logging.WARNING)
logger = logging.getLogger("config")

# --- Configurazione Audio ---
AUDIO_DEVICE_INDEX = os.getenv("AUDIO_DEVICE_INDEX")
if AUDIO_DEVICE_INDEX:
    try:
        AUDIO_DEVICE_INDEX = int(AUDIO_DEVICE_INDEX)
    except ValueError:
        AUDIO_DEVICE_INDEX = None
# Rilevamento automatico del dispositivo di input e SAMPLE_RATE
def find_input_device(requested_index):
    devices = []
    try:
        host_apis = sd.query_hostapis()
        logger.info("--- Host APIs Rilevate ---")
        for i, api in enumerate(host_apis):
            logger.info(f"[{i}] {api['name']} (Default Input: {api['default_input_device']}, Default Output: {api['default_output_device']})")
        
        devices = sd.query_devices()
        logger.info("--- Elenco Dispositivi Audio Rilevati ---")
        for i, d in enumerate(devices):
            logger.info(f"[{i}] {d['name']} - HostAPI: {d['hostapi']}, Input: {d['max_input_channels']}, Output: {d['max_output_channels']}")
        logger.info("-----------------------------------------")
    except Exception as e:
        logger.error(f"Impossibile elencare i dispositivi audio: {e}")

    # 1. Prova l'indice richiesto
    if requested_index is not None:
        try:
            info = sd.query_devices(requested_index, 'input')
            return requested_index, int(info['default_samplerate']), info['name']
        except Exception as e:
            logging.error(f"Errore query su indice {requested_index}: {e}")

    # 2. Prova a cercare per nome esplicito
    AUDIO_DEVICE_NAME_CONTAINS = os.getenv("AUDIO_DEVICE_NAME_CONTAINS")
    if AUDIO_DEVICE_NAME_CONTAINS:
        wanted = AUDIO_DEVICE_NAME_CONTAINS.lower().strip()

        for i, d in enumerate(devices):
            if d['max_input_channels'] > 0:
                if wanted in d['name'].lower():
                    logger.info(
                        f"Dispositivo richiesto trovato per nome: "
                        f"{d['name']} all'indice {i}"
                    )
                    return i, int(d['default_samplerate']), d['name']

        logger.warning(
            f"Nessun dispositivo contiene il nome richiesto: "
            f"{AUDIO_DEVICE_NAME_CONTAINS}"
        )

    # 3. Prova a cercare per nome in modo più aggressivo
    for i, d in enumerate(devices):
        if d['max_input_channels'] > 0:
            lower_name = d['name'].lower()
            if any(x in lower_name for x in ["usb", "micro", "hw:", "input"]):
                logger.info(f"Dispositivo compatibile trovato per nome: {d['name']} all'indice {i}")
                return i, int(d['default_samplerate']), d['name']

    # 4. Prova il default di sistema
    try:
        info = sd.query_devices(None, 'input')
        return None, int(info['default_samplerate']), info['name']
    except Exception:
        # 5. Ultimo tentativo: il primo con input > 0
        for i, d in enumerate(devices):
            if d['max_input_channels'] > 0:
                return i, int(d['default_samplerate']), d['name']

    return None, 16000, "Default/Fallback"

AUDIO_DEVICE_INDEX, SAMPLE_RATE, AUDIO_DEVICE_NAME = find_input_device(AUDIO_DEVICE_INDEX)
logger.info(f"Audio device FINAL: [{AUDIO_DEVICE_INDEX}] {AUDIO_DEVICE_NAME} at {SAMPLE_RATE} Hz")

VAD_THRESHOLD = os.getenv("VAD_THRESHOLD") or 0.005  # Soglia di rilevamento voce (0.001-0.01)
SILENCE_DURATION_SECONDS = os.getenv("SILENCE_DURATION_SECONDS") or 0.6  # Silenzio dopo il parlato per interrompere la trascrizione

VOSK_WAKE_WORDS = ["ciao"]

#WAKEWORD_HANDLER = "vosk"
# oppure
WAKEWORD_HANDLER = os.getenv("WAKEWORD_HANDLER") or "openwakeword"

SOUNDS = { "wake" : "sounds/bubblepop_in.mp3", "ack" : "sounds/bubblepop_out.mp3", "startup": "sounds/startup.mp3"} 

PIPER_MODEL_DIR = "tts/models/piper"
PIPER_MODEL_NAME = "it_IT-paola-medium.onnx"
#PIPER_MODEL_NAME = "it_IT_RON.onnx"
PIPER_MODEL_PATH = os.path.join(PIPER_MODEL_DIR, PIPER_MODEL_NAME)
PIPER_CONFIG_PATH = PIPER_MODEL_PATH + ".json"
PIPER_MODEL_URL = f"https://huggingface.co/rhasspy/piper-voices/resolve/main/it/it_IT/paola/medium/{PIPER_MODEL_NAME}?download=true"
PIPER_CONFIG_URL = f"https://huggingface.co/rhasspy/piper-voices/resolve/main/it/it_IT/paola/medium/{PIPER_MODEL_NAME}.json?download=true"

MUSIC_CACHE_DIR = os.getenv("MUSIC_CACHE_DIR") or "music_cache"
