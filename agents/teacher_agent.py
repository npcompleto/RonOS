from agents.base_agent import BaseAgent
from langchain_community.agent_toolkits.file_management.toolkit import FileManagementToolkit
import config

toolkit = FileManagementToolkit(root_dir="./agents/knowledge")

from langchain_core.tools import tool
import os

@tool
def save_json_test(file_path: str, text: str):
    """
    Salva il contenuto testuale/JSON di una verifica in un file sul disco.
    DEVI usare questo tool per salvare la verifica che hai generato.
    Args:
        file_path: Il nome del file (es. 'geometria_test.json')
        text: L'intero contenuto della verifica (tutte le 40+ domande e risposte).
    """
    full_path = os.path.join("./agents/knowledge", file_path)
    with open(full_path, "w", encoding="utf-8") as f:
        f.write(text)
    return f"File salvato correttamente in {full_path}"

# Rimuovi il write_file di default per evitare ambiguità e usa il nostro custom
tools = [t for t in toolkit.get_tools() if t.name != "write_file"] + [save_json_test]

class TeacherAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            name="TeacherAgent",
            role="Il tuo compito è occuparti di insegnamento di matematica e scienze.",
            instructions=[
                "Il tuo compito principale è preparare verifiche di matematica e scienze per una ragazza delle scuole medie.",
                "Le verifiche devono essere a risposta multipla o essere dei problemi/espressioni da risolvere",
                "Leggi gli argomenti usand i tool a disposizione dal file math.md e science.md",
                "In base agli argomenti crea un file di verifica in formato json e salvalo con il nome <argomento>_test_<timestamp>.json",
                "il file deve avere la seguente struttura: ",
                "questions:",
                " -question",
                " -answer",
                " -options",
                "Usa SEMPRE il tool 'save_json_test' per salvare il file finale. Assicurati di compilare correttamente i campi 'file_path' e 'text' con l'intero JSON.",
                "Quando hai finito dichiara di aver preparato la verifica e di averla salvata"
            ],
            tools=tools
        )



