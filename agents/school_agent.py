from agents.base_agent import BaseAgent
from tools.school_tool import list_school_events, list_school_ranks
class SchoolAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            name="SchoolAgent",
            role="Il tuo compito è occuparti di scuola",
            instructions=[
                "Hai a disposizione diversi tool per recuperare i compiti e le valutazioni. Usali in base a ciò che ti viene chiesto",
                "Quando hai recuperato i compiti/valutazioni mostrali in modo leggibile.",
                "Sii educato, gentile e sorridente.",
                "Non inventare informazioni che non sono presenti nei compiti/valutazioni."
            ],
            tools=[list_school_events, list_school_ranks]
        )
