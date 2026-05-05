from agents.base_agent import BaseAgent
from tools.search_tool import search_information

class ResearchAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            name="Researcher",
            role="Sei un ricercatore esperto. Il tuo compito è trovare, analizzare e sintetizzare informazioni utili.",
            instructions=[
                "Cerca informazioni accurate e aggiornate sull'argomento richiesto.",
                "Riassumi i punti chiave in modo chiaro e conciso.",
                "Utilizza lo strumento di ricerca a tua disposizione per trovare i dati necessari."
            ],
            tools=[search_information]
        )
