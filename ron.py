import config
import sys
from stt.stt_manager import SpeechToTextManager
from tts.tts_manager import TextToSpeechManager
from display.robot_face import RobotFaceManager, Expression
import utils
import time
from agents.main_agent import MainAgent
from integrations.telegram_bot import TelegramBot
from integrations.rest_listener import RestListener
from event_manager import EventManager

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
        #utils.play_audio(config.SOUNDS["wake"])
    logger.info(f" Ron OS is awake!")


def on_expression(expression: str) -> None:
    try:
        """Callback per cambiare l'espressione del robot."""
        logger.info(f"Cambio espressione: {expression}")
        if robot_face:
            # Mappa i nomi delle espressioni a quelle della classe RobotFaceManager
            # Se hai bisogno di espressioni custom, devi aggiungerle nel file 
            # display/robot_face.py e nel config.py
            if expression.upper()=="NOD":
                robot_face.nod()
                return
            expr_map = {
                "NEUTRAL": Expression.NEUTRAL,
                "THOUGHTFUL": Expression.THOUGHTFUL,
                "ANGRY": Expression.ANGRY,
                "HAPPY": Expression.HAPPY,
                "IN_LOVE": Expression.IN_LOVE,
                "SLEEPING": Expression.SLEEPING,
                "SAD": Expression.SAD,
                "DANCING": Expression.DANCING
                
            }
            expr = expr_map.get(expression.upper(), Expression.NEUTRAL)
            logger.info(f"Espressione: {expression} -> {expr}")
            robot_face.set_expression(expr)
    except Exception as e:
        logger.error(f"Errore durante il cambio espressione: {e}")
    
def on_start_speaking() -> None:
    logger.info("Ron is speaking....")
    if robot_face:
        robot_face.set_speaking(True)

def on_stop_speaking() -> None:
    logger.info("Ron stopped speaking....")
    if robot_face:
        robot_face.set_speaking(False)

def loading_handler(data: dict) -> None:
    if data["started"] and robot_face:
        robot_face.set_expression(Expression.LOADING)
    elif robot_face:
        robot_face.set_expression(Expression.NEUTRAL)
    
    if data["message"]:
        tts.speak(data["message"])

def music_handler(data: dict) -> None:
    if data["started"] and robot_face:
        robot_face.set_expression(Expression.DANCING)
    elif robot_face:
        robot_face.set_expression(Expression.NEUTRAL)

def message_handler(data: dict) -> None:
    """Handler per eventi di tipo 'message' (es. da REST API)."""
    text = data.get("text")
    if text:
        logger.info(f"📩 Messaggio da evento: {text}")
        response = process_message(text)
        if response:
            tts.speak(response)

# Definiamo la funzione di callback per elaborare il messaggio
def process_message(user_message: str) -> str:
    logger.info(f"Messaggio ricevuto: {user_message}")
    response = assistant.agent.run(user_message)
    return response.content
    

if __name__ == "__main__":
   
    logger.info("Ron OS starting...")
    em = EventManager()
    em.subscribe("loading", loading_handler)
    em.subscribe("music", music_handler)
    em.subscribe("message", message_handler)
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
    
    # Inizializza e avvia il bot Telegram
    if "--no-telegram" not in sys.argv:
        telegram_bot = TelegramBot(agent_callback=process_message)
    else:
        telegram_bot = None
    


    try:
        stt.start()
        tts.speak("[[HAPPY]]Salve, sono pronto per assisterti.[[NEUTRAL]]")
        #utils.play_audio(config.SOUNDS["startup"], 0.4)
        logger.info("Ron OS started")
        # Avvia il listener REST
        rest_listener = RestListener()
        rest_listener.start()

        if telegram_bot:
            telegram_bot.run()

        stt.wait()  # Blocca finché non viene interrotto con CTRL+C
    except KeyboardInterrupt:
        pass
    finally:
        stt.stop()
        if robot_face:
            robot_face.stop()
        logger.info("Ron OS shut down.")
