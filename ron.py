import config
import sys
from stt.stt_manager import SpeechToTextManager
from tts.tts_manager import TextToSpeechManager
from display.robot_face import RobotFaceManager, Expression
import utils
import time
import threading
from agents.main_agent import MainAgent
from agents.memory_agent import MemoryAgent
from integrations.telegram_bot import TelegramBot
from integrations.rest_listener import RestListener
from event_manager import EventManager
import asyncio
from jobs import JobScheduler, JobScheduleError
from tools.school_tool import axios_sync, axios_rank_sync
from tools.meteo_tool import run_sync_weekly_meteo
from tools.music_tool import stop_music_external, get_currently_playing,get_music_progress,get_current_lyrics_text
from status import get_global_status, State, StateMachine

logger = config.logger

robot_face = None
assistant = None
tts = None

def status_monitor():
    while True:
        try:
            if utils.is_playing_music() and get_global_status().get_state() != State.DANCING:
                get_global_status().set_state(State.DANCING, reason="Musica in riproduzione")
                if robot_face:
                    robot_face.set_expression(Expression.DANCING)
            
            #Aggiorna la canzone corrente
            if utils.is_playing_music() and get_global_status().get_state() == State.DANCING:
                current_song = get_currently_playing()
                music_progress = get_music_progress()
                
                robot_face.set_progress(music_progress['elapsed_seconds'], music_progress['total_seconds'])
                
                music_lyrics =  get_current_lyrics_text()
                robot_face.set_sub_text(music_lyrics)
                logger.debug(f"Currently playing: {current_song} [{music_progress['elapsed_seconds']:.0f}/{music_progress['total_seconds']:.0f} sec]")
                if robot_face and current_song:
                    robot_face.set_text(current_song)
                
            
            logger.debug(f"Wi-Fi Link Quality: {utils.get_wifi_strength()}%")
            if robot_face:
                robot_face.set_wifi_level(utils.get_wifi_strength())

            logger.debug(f"CPU Temperature: {utils.get_cpu_temp()}°C")
            if robot_face:
                robot_face.set_cpu_temp(utils.get_cpu_temp())

            logger.debug(f"Current Voice Volume: {utils.get_current_voice_volume()}")
            logger.debug(f"Current Music Volume: {utils.get_current_music_volume()}")
            time.sleep(0.1)
        except Exception as e:
            logger.error(f"Errore nel monitoraggio dello stato: {e}")
            time.sleep(5)  # Attende prima di riprovare in caso di errore

def on_transcription(text: str) -> None:
    """Callback invocata ad ogni trascrizione completata."""
    logger.info(f"📝 Trascrizione ricevuta: {text}")
    if robot_face:
        robot_face.set_expression(Expression.LOADING)
        robot_face.set_text(text)
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
            if expression.upper() == "SLEEPING":
                utils.shutdown()
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
        robot_face.set_text(data["message"])
    elif robot_face:
        robot_face.set_expression(Expression.NEUTRAL)
        robot_face.set_text("")

def music_handler(data: dict) -> None:
    if data["started"] and robot_face:
        robot_face.set_expression(Expression.DANCING)
        robot_face.set_text(data["message"])
    elif robot_face:
        robot_face.set_expression(Expression.NEUTRAL)
        robot_face.set_text("")

def downloading_handler(data: dict) -> None:
    logger.info(f"Downloading handler: {data}")
    if data["started"] and robot_face:
        robot_face.set_expression(Expression.DOWNLOADING)
        robot_face.set_text(data["message"])
    elif robot_face:
        robot_face.set_expression(Expression.NEUTRAL)
        robot_face.set_text("")

def message_handler(data: dict) -> None:
    """Handler per eventi di tipo 'message' (es. da REST API)."""
    text = data.get("text")
    if text:
        logger.info(f"📩 Messaggio da evento: {text}")
        response = process_message(text)
        if response:
            tts.speak(response)

def joystick_handler(data: dict) -> None:
    logger.debug(f"Joystick event received: {data}")
    if data["action"]=='click':
        if utils.is_playing_music():
            stop_music_external()
        
        if get_global_status().get_state() == State.DANCING:
            get_global_status().set_state(State.IDLE, reason="Musica fermata da Joystick")
        tts.stop_speaking()
    if data["action"]=='mouse_move':
        logger.debug(f"Mouse moved: {data['direction']}")
        if data['direction'] == 'up':
            utils.increase_music_volume()
        elif data['direction'] == 'down':
            utils.decrease_music_volume()
            

# Definiamo la funzione di callback per elaborare il messaggio
def process_message(user_message: str) -> str:
    logger.info(f"Messaggio ricevuto: {user_message}")
    if not get_global_status().set_state(State.THINKING, reason="Elaborazione messaggio"):
        logger.warning("Impossibile elaborare il messaggio, stato attuale non permette la transizione a THINKING.")
        return "Non posso rispondere in questo momento."

    response = assistant.agent.run(user_message)
    return response.content

def process_telegram_message(user_message: str) -> str:
    logger.info(f"Messaggio ricevuto da Telegram: {user_message}")
    response = assistant.agent.run(user_message)
    return response.content

def status_handler(old_state: State, new_state: State, reason: str) -> None:
    logger.info(f"Stato aggiornato: {old_state} -> {new_state} (Reason: {reason})")
    if new_state == State.IDLE and robot_face:
        robot_face.set_expression(Expression.NEUTRAL)
        robot_face.set_text("")
        robot_face.set_progress(0, 0)
        robot_face.set_sub_text("")
    elif new_state == State.DANCING and robot_face:
        robot_face.set_expression(Expression.DANCING)
        robot_face.set_text("🎶")

def dreaming_job() -> None:
    logger.info(f"Ron is dreaming....")
    memory_agent = MemoryAgent()
    memory_agent.agent.run("Consolida la memoria")

async def post_init_telegram_bot(app):
    logger.info("Telegram bot pronto")
    telegram_bot.send_message("Eccomi pronto, Capo!")

if __name__ == "__main__":
   
    logger.info("Ron OS starting...")
    em = EventManager()
    em.subscribe("loading", loading_handler)
    em.subscribe("music", music_handler)
    em.subscribe("message", message_handler)
    em.subscribe("joystick", joystick_handler)
    em.subscribe("downloading", downloading_handler)

    get_global_status().subscribe(status_handler)

    if "--no-face" not in sys.argv:
        robot_face = RobotFaceManager(fullscreen="--windowed" not in sys.argv, bg_color=(10, 10, 20))
        robot_face.start()

    status_monitor_thread=threading.Thread(target=status_monitor, daemon=True)
    status_monitor_thread.start()

    scheduler = JobScheduler()

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
        telegram_bot = TelegramBot(agent_callback=process_telegram_message, post_init_callback=post_init_telegram_bot)
    else:
        telegram_bot = None
    


    try:
        stt.start()
        tts.speak("[[HAPPY]]Ciao, Bella Fra! [[NEUTRAL]]")
        #utils.play_audio(config.SOUNDS["startup"], 0.4)
        logger.info("Ron OS started")

        # Avvia il listener REST
        rest_listener = RestListener()
        rest_listener.start()

        scheduler.add_job("axios_sync", axios_sync, interval="4h", run_immediately=True)
        scheduler.add_job("axios_rank_sync", axios_rank_sync, interval="1h", run_immediately=True)
        scheduler.add_job("sync_weekly_meteo", run_sync_weekly_meteo, interval="1d", run_immediately=True)
        #scheduler.add_job("dreaming", dreaming_job, interval="2h", run_immediately=True)
        scheduler.start()

        if telegram_bot:
            telegram_thread = threading.Thread(
                target=telegram_bot.run,
                daemon=False
            )
            telegram_thread.start()

        stt.wait()  # Blocca finché non viene interrotto con CTRL+C
    except KeyboardInterrupt:
        pass
    finally:
        stt.stop()
        if robot_face:
            robot_face.stop()
        logger.info("Ron OS shut down.")
