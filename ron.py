import config
from stt.managers import SpeechToTextManager

logger = config.logger



if __name__ == "__main__":
    stt_manager = SpeechToTextManager()
    logger.info("Ron OS started")
    text = stt_manager.listen()
    logger.info(f"Trascrizione: {text}")
