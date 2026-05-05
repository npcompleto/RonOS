import os
from datetime import datetime
from typing import List, Optional
from langchain_anthropic import ChatAnthropic
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain_core.tools import tool

class LangChainAgentWrapper:
    """
    Wrapper per rendere l'agente LangChain compatibile con l'interfaccia usata in main.py.
    Gestisce la memoria tramite file Markdown giornalieri.
    """
    def __init__(self, executor):
        self.executor = executor
        self.memory_dir = "agents/memory"
        if not os.path.exists(self.memory_dir):
            os.makedirs(self.memory_dir)

    def _get_memory_file_path(self):
        # Nome file basato sulla data odierna: AAAA-MM-GG.md
        today = datetime.now().strftime("%Y-%m-%d")
        return os.path.join(self.memory_dir, f"{today}.md")

    def _read_memory(self):
        file_path = self._get_memory_file_path()
        if not os.path.exists(file_path):
            return ""
        with open(file_path, "r", encoding="utf-8") as f:
            return f.read()

    def _read_long_term_memory(self):
        file_path = os.path.join(self.memory_dir, "long_term.md")
        if not os.path.exists(file_path):
            return ""
        with open(file_path, "r", encoding="utf-8") as f:
            return f.read()

    def _append_to_memory(self, user_input, bot_output):
        file_path = self._get_memory_file_path()
        with open(file_path, "a", encoding="utf-8") as f:
            f.write(f"Utente: {user_input}\n")
            f.write(f"Bot: {bot_output}\n\n")

    def run(self, input_text: str, session_id: str = "default"):
        # Leggiamo la memoria dal file MD
        history_context = self._read_memory()
        long_term_context = self._read_long_term_memory()
        
        # Prepariamo l'input con il contesto della memoria
        full_input = ""
        
        if long_term_context:
            full_input += f"MEMORIA A LUNGO TERMINE (fatti importanti consolidati):\n{long_term_context}\n\n"
            
        if history_context:
            full_input += f"Ecco il contesto delle conversazioni precedenti di oggi:\n\n{history_context}\n---\n"
        
        full_input += f"Utente: {input_text}"

        # Eseguiamo l'agente
        result = self.executor.invoke({
            "input": full_input,
            "chat_history": [] # Non usiamo più la memoria interna di LangChain
        })
        
        # Estraiamo l'output testuale
        output = result["output"]
        if isinstance(output, list):
            output = "".join([block.get("text", "") for block in output if isinstance(block, dict) and block.get("type") == "text"])
        
        # Salviamo l'interazione nel file MD
        self._append_to_memory(input_text, output)
        
        # Mock della risposta Agno per mantenere compatibilità con main.py
        class Response:
            def __init__(self, content):
                self.content = content
        
        return Response(output)

class BaseAgent:
    def __init__(self, name: str, role: str, instructions: list[str], tools: list = None, enable_memory: bool = False):
        """
        Inizializza un agente base utilizzando LangChain e memoria su file Markdown.
        """
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY non trovata. Assicurati di averla definita nel file .env")

        ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-haiku-4-5-20251001")
        
        llm = ChatAnthropic(
            model=ANTHROPIC_MODEL,
            anthropic_api_key=api_key,
            temperature=0
        )
        
        self.tools = tools or []
        
        # Prompt di sistema
        system_instructions = "\n".join([f"- {i}" for i in instructions])
        system_msg = f"Nome: {name}\nRuolo: {role}\n\nIstruzioni:\n{system_instructions}\n\nUsa il contesto fornito per ricordare i dettagli dell'utente."
        
        prompt = ChatPromptTemplate.from_messages([
            ("system", system_msg),
            MessagesPlaceholder(variable_name="chat_history"), # Manteniamo per compatibilità con create_tool_calling_agent
            ("human", "{input}"),
            MessagesPlaceholder(variable_name="agent_scratchpad"),
        ])
        
        agent = create_tool_calling_agent(llm, self.tools, prompt)
        
        self.executor = AgentExecutor(
            agent=agent,
            tools=self.tools,
            verbose=True,
            handle_parsing_errors=True
        )
        
        self.agent = LangChainAgentWrapper(self.executor)
