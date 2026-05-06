from agents.base_agent import BaseAgent
from agents.interpreter_agent import InterpreterAgent
from agents.school_agent import SchoolAgent
from agents.music_agent import MusicAgent
from langchain_core.tools import tool
from tools.system import shutdown


interpreter = InterpreterAgent()
@tool("interpreter", description="Correggi possibili errori dovuto al riconoscimento vocale")
def call_interpreter_agent(query: str):
    result = interpreter.agent.run(query)
    return result.content

school_agent = SchoolAgent()
@tool("school_agent", description="Utilizza questo tool quando devi rispondere a domande o richieste che riguardano la scuola. Ad esempio: compiti, interrogazioni, verifiche, orari, voti, professori, ecc.")
def call_school_agent(query: str):
    result = school_agent.agent.run(query)
    return result.content

music_agent = MusicAgent()
@tool("music_agent", description="Utilizza questo tool quando l'utente chiede di riprodurre musica, playlist o canzoni o fermare la riproduzione")
def call_music_agent(query: str):
    result = music_agent.agent.run(query)
    return result.content

class MainAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            name="Ron",
            role="Sei l'agente principale del sistema. Rispondi all'utente in modo utile e amichevole. Hai a disposizione un team di agenti se necessario.",
            instructions=[
                "Rispondi direttamente alle domande semplici.",
                "Limita al massimo le informazioni non importanti. Tipo: evita di dire Che tu stia riposando o semplicemente prendendo una pausa, sono sempre a tua disposizione"
                "Intervalla la risposta con stringhe di sentimento racchiuse tra doppie parentesi quadre. I valori che hai a disposizione sono:",
                "[[NEUTRAL]],[[HAPPY]],[[SAD]],[[ANGRY]],[[THOUGHTFUL]],[[IN_LOVE]],[[SLEEPING]],[[NOD]]",
                "Usa [[NOD]] quando vuoi esprimere accordo"
                "Chiudi sempre con [[NEUTRAL]]",
                "Ad esempio: Ciao! [[HAPPY]] Sono Ron, felicissimo di conoscerti! [[NEUTRAL]]",
                "Quando devi rispondere usando un tool, esegui prima il tool e poi rispondi all'utente",
                "Quando l'utente chiede di ascoltare o fermare la musica o playlist, usa il tool music_agent",
                "Quando l'utente chiede di ascoltare musica, dopo aver eseguito il tool, rispondi con '[[DANCING]] Ok.', Importante! In questo caso non chiudere con [[NEUTRAL]]",
                "Non usare mai EMOJI!"

            ],
            tools=[call_interpreter_agent, call_school_agent, call_music_agent, shutdown],
            enable_memory=True
        )
