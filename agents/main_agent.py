from agents.base_agent import BaseAgent
from agents.interpreter import InterpreterAgent
from langchain_core.tools import tool


interpreter = InterpreterAgent()

@tool("interpreter", description="Correggi possibili errori dovuto al riconoscimento vocale")
def call_interpreter_agent(query: str):
    result = interpreter.agent.run(query)
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
                "Chiudi sempre con [[NEUTRAL]]",
                "Ad esempio: Ciao! [[HAPPY]] Sono Ron, felicissimo di conoscerti! [[NEUTRAL]]"
            ],
            tools=[call_interpreter_agent],
            enable_memory=True
        )
