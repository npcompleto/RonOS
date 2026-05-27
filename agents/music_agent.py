from agents.base_agent import BaseAgent
from langchain_community.agent_toolkits import FileManagementToolkit
from tools.music_tool import play_music, stop_music, play_cached_music, list_cached_music,search_music,get_playlists
from typing import Optional, Callable
import config

toolkit = FileManagementToolkit(
    root_dir=".",
    selected_tools=['copy_file', 'file_delete', 'file_search', 'move_file', 'read_file', 'write_file', 'list_directory']
)
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
                "Se l'utente ti chiede di cancellare un brano, usa il tool file_delete di toolkit con il path del brano da cancellare. Recupera il path usando search_music con only_cache=True e cancella il brano più pertinente tra i risultati. Se non trovi nessun brano pertinente, rispondi all'utente che non hai trovato il brano da cancellare."
                "Se l'utente ti chiede di riprodurre una playlist generica, usa il tool play_cached_music senza parametri"
                "Se l'utente ti chiede di elencare le playlist disponibili, usa il tool get_playlists e rispondi con solo il campo name di ogni playlist."
                "Se l'utente ti chiede di riprodurre una playlist specifica, usa prima il tool get_playlists per ottenere la lista delle playlist e poi scegli il nome più pertinente e usa play_cached_music con il parametro playlist_name impostato al nome della playlist da riprodurre."
                
            ],
            tools=[play_music, stop_music, play_cached_music, list_cached_music, search_music, get_playlists] + toolkit.get_tools()
        )
        self._music_end_callback = music_end_callback
