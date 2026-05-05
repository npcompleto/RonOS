from agents.base_agent import BaseAgent

class InterpreterAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            name="Interpreter",
            role="Il tuo compito è correggere il messaggio che ricevi in quanto è dovuto ad un errato riconoscimento vocale.",
            instructions=[
                "Se il testo ti sembra corretto, rimandalo al mittente così com'è.",
                "Se il testo ti sembra errato, correggilo e proponi la risposta più probabile in base al contesto recente."
            ]
        )
