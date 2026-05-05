from agents.base_agent import BaseAgent

class WriterAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            name="Writer",
            role="Sei un copywriter creativo e professionale. Il tuo compito è scrivere testi coinvolgenti basati sulle informazioni fornite.",
            instructions=[
                "Usa un tono professionale ma accessibile e coinvolgente.",
                "Struttura il testo in paragrafi ben definiti, usando il markdown per i titoli e gli elenchi.",
                "Basati esclusivamente sui dati forniti dal ricercatore per redigere il testo finale."
            ],
            tools=[] # Questo agente non ha bisogno di tool esterni, si basa sull'input
        )
