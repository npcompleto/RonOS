from agents.base_agent import BaseAgent
from tools.music_tool import play_music, stop_music, play_cached_music
from typing import Optional, Callable

class MusicAgent(BaseAgent):
    def __init__(self, music_end_callback: Optional[Callable[[str], None]] = None):
        super().__init__(
            name="Music Agent",
            role="Il tuo compito è cercare brani e gestire la riproduzione di musica.",
            instructions=[
                "Usa il tool 'play_music' per cercare e riprodurre musica",
                "Usa il tool 'stop_music' per fermare la musica",
                "Usa il tool 'play_cached_music' per riprodurre musica già presente nella cache, già ascoltata o se ti chiede di riprodurre la sua playlist"
            ],
            tools=[play_music, stop_music, play_cached_music]
        )
        self._music_end_callback = music_end_callback
