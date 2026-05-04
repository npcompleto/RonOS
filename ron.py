import config
from stt.stt_manager import SpeechToTextManager

logger = config.logger


def on_transcription(text: str) -> None:
    """Callback invocata ad ogni trascrizione completata."""
    logger.info(f"📝 Trascrizione ricevuta: {text}")
    # TODO: qui puoi inoltrare il testo all'agente LLM

def on_wake(text: str) -> None:
    """Callback invocata quando viene rilevata una parola di risveglio."""
    logger.info(f" Ron OS is awake!")

if __name__ == "__main__":
    logger.info("Ron OS starting...")

    stt = SpeechToTextManager(
        config,
        on_transcription=on_transcription,
        on_wake=on_wake,
        model_size="small",
        language="it",
        vad_aggressiveness=1,
    )

    try:
        stt.start()
        logger.info("Ron OS started")
        stt.wait()  # Blocca finché non viene interrotto con CTRL+C
    except KeyboardInterrupt:
        pass
    finally:
        stt.stop()
        logger.info("Ron OS shut down.")
