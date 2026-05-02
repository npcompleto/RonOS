import config
from stt.managers import AlexaLikeSTT

logger = config.logger



if __name__ == "__main__":
    stt_manager = AlexaLikeSTT(config)
    logger.info("Ron OS started")
    text = stt_manager.listen()
    logger.info(f"Trascrizione: {text}")
