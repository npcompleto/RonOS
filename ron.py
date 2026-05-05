import config
import sys
from stt.stt_manager import SpeechToTextManager
from tts.tts_manager import TextToSpeechManager
from display.robot_face import RobotFaceManager, Expression
import utils
import time
from agents.main_agent import MainAgent

logger = config.logger

robot_face = None
assistant = None
tts = None

def on_transcription(text: str) -> None:
    """Callback invocata ad ogni trascrizione completata."""
    logger.info(f"📝 Trascrizione ricevuta: {text}")
    if robot_face:
        robot_face.set_expression(Expression.NEUTRAL)
    utils.play_audio(config.SOUNDS["ack"])
    response = process_message(text)
    if response:
        tts.speak(response)

def on_wake(text: str) -> None:
    """Callback invocata quando viene rilevata una parola di risveglio."""
    if robot_face:
        robot_face.set_expression(Expression.THOUGHTFUL)
        utils.play_audio(config.SOUNDS["wake"])
    logger.info(f" Ron OS is awake!")


def on_expression(expression: str) -> None:
    try:
        """Callback per cambiare l'espressione del robot."""
        logger.info(f"Cambio espressione: {expression}")
        if robot_face:
            # Mappa i nomi delle espressioni a quelle della classe RobotFaceManager
            # Se hai bisogno di espressioni custom, devi aggiungerle nel file 
            # display/robot_face.py e nel config.py
            expr_map = {
                "NEUTRAL": Expression.NEUTRAL,
                "THOUGHTFUL": Expression.THOUGHTFUL,
                "ANGRY": Expression.ANGRY,
                "HAPPY": Expression.HAPPY
            }
            expr = expr_map.get(expression.upper(), Expression.NEUTRAL)
            logger.info(f"Espressione: {expression} -> {expr}")
            robot_face.set_expression(expr)
    except Exception as e:
        logger.error(f"Errore durante il cambio espressione: {e}")
    
def on_start_speaking() -> None:
    if robot_face:
        robot_face.set_speaking(True)

def on_stop_speaking() -> None:
    if robot_face:
        robot_face.set_speaking(False)
        

# Definiamo la funzione di callback per elaborare il messaggio
def process_message(user_message: str) -> str:
    logger.info(f"Messaggio ricevuto: {user_message}")
    response = assistant.agent.run(user_message)
    return response.content

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

    tts = TextToSpeechManager(
        expression_callback=on_expression, 
        start_speaking_callback=on_start_speaking,
        stop_speaking_callback=on_stop_speaking)

    # Inizializza l'agente principale
    assistant = MainAgent()
    


    try:
        stt.start()
        tts.speak(process_message("Sei stato appena attivato. Salutami brevemente (massimo 10 parole). In modo simpatico."))
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
