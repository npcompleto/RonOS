from agents.base_agent import BaseAgent
from langchain_community.agent_toolkits import FileManagementToolkit
from tools.music_tool import play_music, stop_music, play_cached_music, list_cached_music,search_music,get_playlists
from typing import Optional, Callable
import config

toolkit = FileManagementToolkit(
    root_dir=".",
    selected_tools=['copy_file', 'file_delete', 'file_search', 'move_file', 'read_file', 'write_file', 'list_directory']
)
class MemoryAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            name="Memory Agent",
            role="Il tuo compito è ricordare informazioni all'utente.",
            instructions=[
                "Il tuo compito è tenere in ordine il file long_term.md che si trova dentro ./agents/memory/",
                "Se il file non esiste usa il tool write_file per crearlo",
                "Se il file esiste, non devi andare in append, ma riscrivilo sempre da zero"
                "Leggi due file: "
                "1- file di memoria con data corrente nel path './agents/memory/YYYY-MM-DD.md' "
                "2- il file di memoria principale './agents/memory/long_term.md'"
                "Letti questi due file, cancella il file long_term.md",
                "alla fine inserisci dentro il file long_term.md una sintesi di tutte le informazioni che ritieni importanti per l'utente.",                
            ],
            tools=toolkit.get_tools()
        )
