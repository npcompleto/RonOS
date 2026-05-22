import os
import asyncio
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
import re

class TelegramBot:
    def __init__(self, agent_callback):
        """
        Inizializza il bot Telegram.
        
        Args:
            agent_callback (callable): Funzione che accetta una stringa (il messaggio dell'utente) 
                                       e restituisce una stringa (la risposta dell'agente).
        """
        self.token = os.getenv("TELEGRAM_TOKEN")
        if not self.token:
            raise ValueError("TELEGRAM_TOKEN non trovato. Assicurati di averlo definito nel file .env")
        
        self.allowed_chat_id = os.getenv("TELEGRAM_CHAT_ID")
        allowed_users_env = os.getenv("TELEGRAM_ALLOWED_USER_IDS", "")
        self.allowed_user_ids = [uid.strip() for uid in allowed_users_env.split(",") if uid.strip()]
        
        self.agent_callback = agent_callback
        
        # Costruisci l'applicazione Telegram
        self.app = ApplicationBuilder().token(self.token).build()

        # Registra i gestori degli eventi
        self.app.add_handler(CommandHandler("start", self.start_command))
        self.app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message))

    def _is_allowed(self, update: Update) -> bool:
        """Controlla se l'utente e la chat sono autorizzati."""
        if not update.message:
            return False
            
        chat_id = str(update.message.chat_id)
        user_id = str(update.message.from_user.id)
        
        # Verifica la chat (se configurata)
        if self.allowed_chat_id and chat_id != self.allowed_chat_id:
            print(f"[Telegram] Accesso negato: chat_id '{chat_id}' non autorizzato.")
            return False
            
        # Verifica l'utente (se configurato)
        if self.allowed_user_ids and user_id not in self.allowed_user_ids:
            print(f"[Telegram] Accesso negato: user_id '{user_id}' non autorizzato.")
            return False
            
        return True

    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Gestisce il comando /start"""
        if not self._is_allowed(update):
            return

        welcome_message = (
            "Ciao! Sono il tuo assistente AI. 🤖\n"
            "Scrivimi qualsiasi cosa e la passerò al sistema multi-agente per risponderti."
        )
        await update.message.reply_text(welcome_message)

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Gestisce i messaggi testuali inviati dall'utente"""
        if not self._is_allowed(update):
            return
            
        user_message = update.message.text
        
        # Invia l'azione "sto scrivendo..." per feedback all'utente
        await update.message.reply_chat_action(action="typing")
        
        try:
            # Poiché agent.run() è sincrono e blocca l'esecuzione, lo facciamo girare
            # in un thread separato tramite asyncio.to_thread per mantenere responsivo il bot
            response_text = await asyncio.to_thread(self.agent_callback, user_message)
            
            # Invia la risposta all'utente
            cleaned_text = re.sub(r'\[\[.*?\]\]', '', response_text)
            await update.message.reply_text(cleaned_text)
            
        except Exception as e:
            print(f"Errore durante l'elaborazione del messaggio: {e}")
            await update.message.reply_text("Scusa, si è verificato un errore interno durante l'elaborazione della tua richiesta.")

    def run(self):
        """Avvia il polling del bot"""
        print("Avvio del bot Telegram in corso... Premi Ctrl+C per fermarlo.")
        self.app.run_polling(
            poll_interval=1.0,      # Tempo di attesa tra una richiesta e l'altra (in secondi)
            timeout=30,             # Timeout del Long Polling lato Telegram (default è 10)
            read_timeout=60,        # Tempo massimo di attesa risposta della rete prima di un timeout locale
            write_timeout=20,       # Timeout per l'invio dei dati
            connect_timeout=20,     # Timeout per stabilire la connessione iniziale
            bootstrap_retries=-1,   # Tenta all'infinito se fallisce l'avvio iniziale (-1)
            close_loop=True
        )