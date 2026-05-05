import config
import sys
from stt.stt_manager import SpeechToTextManager
from tts.tts_manager import TextToSpeechManager
from display.robot_face import RobotFaceManager, Expression
import utils
import time

logger = config.logger

robot_face = None

def on_transcription(text: str) -> None:
    """Callback invocata ad ogni trascrizione completata."""
    logger.info(f"📝 Trascrizione ricevuta: {text}")
    if robot_face:
        robot_face.set_expression(Expression.NEUTRAL)
    # TODO: qui puoi inoltrare il testo all'agente LLM

def on_wake(text: str) -> None:
    """Callback invocata quando viene rilevata una parola di risveglio."""
    if robot_face:
        robot_face.set_expression(Expression.THOUGHTFUL)
    logger.info(f" Ron OS is awake!")

if __name__ == "__main__":
    logger.info("Ron OS starting...")
    if "--no-face" not in sys.argv:
        robot_face = RobotFaceManager(fullscreen="--windowed" not in sys.argv, bg_color=(10, 10, 20))
        robot_face.start()


    stt = SpeechToTextManager(
        config,
        on_transcription=on_transcription,
        on_wake=on_wake,
        model_size="small",
        language="it",
        vad_aggressiveness=1,
        save_audio="--save-audio" in sys.argv
    )

    tts = TextToSpeechManager()
    

    try:
        stt.start()
        tts.speak("ciao")
        #utils.play_audio(config.SOUNDS["startup"], 0.4)
        logger.info("Ron OS started")
        stt.wait()  # Blocca finché non viene interrotto con CTRL+C
    except KeyboardInterrupt:
        pass
    finally:
        stt.stop()
        if robot_face:
            robot_face.stop()
        logger.info("Ron OS shut down.")
