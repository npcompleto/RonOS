const API_BASE_URL = `http://${window.location.hostname}:8001/api`;

const LogLevel = {
  DEBUG: 'DEBUG',
  INFO: 'INFO',
  WARNING: 'WARNING',
  ERROR: 'ERROR',
};

class Logger {
  constructor() {
    this.queue = [];
    this.isOnline = navigator.onLine;
    this.batchSize = 10;
    this.flushInterval = 5000; // 5 secondi
    
    // Listener per cambiamenti di connettività
    window.addEventListener('online', () => {
      this.isOnline = true;
      this.flush();
    });
    window.addEventListener('offline', () => {
      this.isOnline = false;
    });

    // Flush periodico dei log
    setInterval(() => this.flush(), this.flushInterval);
  }

  log(level, message) {
    const timestamp = new Date().toISOString();
    const logEntry = {
      level,
      message,
      timestamp,
    };

    this.queue.push(logEntry);

    // Console output locale
    const consoleMethod = this._getConsoleMethod(level);
    consoleMethod(`[${timestamp}] [${level}] ${message}`);

    // Flush se il batch è pieno
    if (this.queue.length >= this.batchSize) {
      this.flush();
    }
  }

  debug(message) {
    this.log(LogLevel.DEBUG, message);
  }

  info(message) {
    this.log(LogLevel.INFO, message);
  }

  warning(message) {
    this.log(LogLevel.WARNING, message);
  }

  error(message) {
    this.log(LogLevel.ERROR, message);
  }

  async flush() {
    if (this.queue.length === 0 || !this.isOnline) {
      return;
    }

    const logsToSend = [...this.queue];
    this.queue = [];

    try {
      for (const logEntry of logsToSend) {
        await fetch(`${API_BASE_URL}/logs`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify(logEntry),
        }).catch(err => {
          // Se il log fallisce, lo rimette nella queue per il prossimo tentativo
          this.queue.push(logEntry);
        });
      }
    } catch (err) {
      // Rimetti i log nella queue se c'è un errore
      this.queue.push(...logsToSend);
    }
  }

  _getConsoleMethod(level) {
    switch (level) {
      case LogLevel.DEBUG:
        return console.debug;
      case LogLevel.INFO:
        return console.log;
      case LogLevel.WARNING:
        return console.warn;
      case LogLevel.ERROR:
        return console.error;
      default:
        return console.log;
    }
  }
}

export const logger = new Logger();
