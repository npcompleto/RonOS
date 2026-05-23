import asyncio
from langchain_core.tools import tool
import config
import requests
from dotenv import load_dotenv
from playwright.async_api import async_playwright, expect  # Cambiato in async_playwright
from datetime import datetime, timedelta
from db import get_connection, init_db
import json

load_dotenv()
init_db()


@tool
def get_meteo(date: str, city: str) -> str:
    """Restituisce il CSV meteo salvato nel DB per la data (DD/MM/YYYY o YYYY-MM-DD) e la città.

    Parametri:
    - date: data in formato DD/MM/YYYY oppure YYYY-MM-DD
    - city: nome della città
    """
    from db import get_connection
    # Normalize city
    city_norm = city.strip().lower()

    # Parse date input to YYYY-MM-DD
    db_date = None
    for fmt in ("%d/%m/%Y", "%Y-%m-%d"):
        try:
            db_date = datetime.strptime(date.strip(), fmt).strftime("%Y-%m-%d")
            break
        except Exception:
            continue

    if not db_date:
        return "Formato data non valido. Usa DD/MM/YYYY o YYYY-MM-DD."

    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT dati_meteo FROM meteo_forecast WHERE date = ? AND city = ? LIMIT 1', (db_date, city_norm))
        row = cursor.fetchone()
        conn.close()

        if not row or not row[0]:
            return f"Nessun dato meteo trovato per {city.capitalize()} il {db_date}"

        return row[0]
    except Exception as e:
        return f"Errore durante l'accesso al DB per meteo: {e}"


# Trasformato in funzione asincrona
async def sync_weekly_meteo(city: str = "Bareggio"):
    """Job settimanale per sincronizzare le previsioni meteo di domani"""
    config.logger.info("Esecuzione job settimanale: sync_weekly_meteo")
    for i in range(7):
        # Aggiunto l'await per chiamare la funzione asincrona
        result = await sync_meteo(days_from_today=i, city=city)
        config.logger.debug(f"Risultato sync_weekly_meteo {i}: {result}")


# Trasformato in funzione asincrona
async def sync_meteo(days_from_today: int = 1, city: str = "Bareggio") -> str:
    """Ottiene le previsioni meteo per una città data"""

    url = f"https://www.ilmeteo.it/meteo/{city.lower()}/{days_from_today}"
    
    try:
        # Usiamo il context manager asincrono (pulisce automaticamente i processi alla fine)
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context()
            page = await context.new_page()
            
            config.logger.debug(f"Navigazione su {url}...")
            await page.goto(url)

            # Gestione del click sul pulsante dei cookie con await
            try:
                # Messo in un try-except nel caso in cui il banner non appaia nelle chiamate successive
                await page.get_by_role("button", name="accetta", exact=True).click(timeout=5000)
            except Exception:
                pass

            await page.wait_for_selector("table.weather_table")

            # Estraiamo i dati in modo atomico usando evaluate (con await)
            data = await page.evaluate("""() => {
                const rows = Array.from(document.querySelectorAll('table.weather_table tr'));
                return rows.slice(1).map(row => {
                    const cells = row.querySelectorAll('td');
                    if (cells.length < 4) return null;
                    return {
                        hours: cells[0].innerText.trim(),
                        temp: cells[2].innerText.trim(),
                        prec: cells[3].innerText.trim()  // Notare la chiave 'prec'
                    };
                }).filter(item => item !== null);
            }""")
            
            await browser.close()

        # Formattazione output
        csv = "hours,temp,precipitation\n"
        jsonObject = {}
        for entry in data:
            config.logger.info(f"Elaborazione entry meteo: {entry}")
            try:                
                jsonObject[entry['hours']] = {'temperature': entry['temp'], 'precipitation': entry['prec']}
                if int(entry['hours']) == 24:
                    break
            except Exception as e:
                # Ignora i campi ora non numerici
                config.logger.error(f"Errore durante l'elaborazione dei dati meteo: {e}")

        # Persistenza dei dati nel database
        try:
            # Corretto: calcola la data corretta in base a 'days_from_today' invece di fare sempre +1 giorno
            db_date = (datetime.today() + timedelta(days=days_from_today)).strftime("%Y-%m-%d")
            city_norm = city.strip().lower()
            
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute(
                "INSERT OR REPLACE INTO meteo_forecast (date, city, dati_meteo) VALUES (?, ?, ?)",
                (db_date, city_norm, json.dumps(jsonObject))
            )
            conn.commit()
            conn.close()
            config.logger.debug(f"Meteo salvato per {city_norm} - {db_date}")
        except Exception as e:
            config.logger.error(f"Errore salvataggio meteo: {e}")

        return f"Meteo per {days_from_today} giorni da oggi per {city.capitalize()}:\n{json.dumps(jsonObject)}"
        
    except Exception as e:
        return f"Non sono riuscito a trovare le previsioni meteo per {city.capitalize()} {e}"

def run_sync_weekly_meteo(city: str = "Bareggio"):
    try:
        # Se c'è già un loop attivo in questo thread, usiamo quello
        loop = asyncio.get_running_loop()
        loop.create_task(sync_weekly_meteo(city))
    except RuntimeError:
        # Altrimenti ne avviamo uno nuovo (caso tipico di un thread dedicato)
        asyncio.run(sync_weekly_meteo(city))