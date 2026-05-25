from agents.base_agent import BaseAgent
from tools.music_tool import play_music, stop_music, play_cached_music, list_cached_music,search_music
from typing import Optional, Callable

class MusicAgent(BaseAgent):
    def __init__(self, music_end_callback: Optional[Callable[[str], None]] = None):
        super().__init__(
            name="Music Agent",
            role="Il tuo compito è cercare brani e gestire la riproduzione di musica.",
            instructions=[
                "Se l'utente ti dice di mettere un brano usa il prima il tool search_music per cercare il brano e poi usa play_music con 'url' del risultato che ritieni più pertinente."
                "Se l'utente ti dice di fermare la musica, usa stop_music.",
                "Se l'utente ti chiede di riprodurre un brano già scaricato, usa search_music con only_cache=True per cercare nella cache e poi play_any con 'url' del risultato che ritieni più pertinente.",
                "Se l'utente ti chiede di elencare i brani scaricati, usa list_cached_music."
                "Se l'utente ti chiede di mettere la sua playlist o la sua musica o la musica locale, usa play_cached_music."
            ],
            tools=[play_music, stop_music, play_cached_music, list_cached_music, search_music]
        )
        self._music_end_callback = music_end_callback
