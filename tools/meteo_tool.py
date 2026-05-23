from langchain_core.tools import tool
import config
import requests
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright, expect
from datetime import datetime, timedelta
from db import get_connection, init_db

load_dotenv()
init_db()


@tool
def get_meteo_domani(date: str, city: str) -> str:
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

def sync_weekly_meteo(city: str = "Bareggio"):
    """Job settimanale per sincronizzare le previsioni meteo di domani"""
    config.logger.info("Esecuzione job settimanale: sync_weekly_meteo")
    for i in range(7):
        result = sync_meteo(days_from_today=i, city=city)
        config.logger.info(f"Risultato sync_weekly_meteo {i}: {result}")

def sync_meteo(days_from_today: int = 1, city: str = "Bareggio") -> str:
    """Ottiene le previsioni meteo per una città data"""

    url = f"https://www.ilmeteo.it/meteo/{city.lower()}/{days_from_today}"
    
    try:
        # Avvio browser - Headless True per l'esecuzione in background
        p = sync_playwright().start()
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        page = context.new_page()
        
        config.logger.info(f"Navigazione su {url}...")
        page.goto(url)

        page.get_by_role("button", name="accetta", exact=True).click()

        page.wait_for_selector("table.weather_table")

        table = page.locator("table.weather_table")
        
        # Estraiamo i dati in modo atomico usando evaluate
        # Questo evita problemi di timeout sui singoli elementi
        data = page.evaluate("""() => {
            const rows = Array.from(document.querySelectorAll('table.weather_table tr'));
            return rows.slice(1).map(row => {
                const cells = row.querySelectorAll('td');
                if (cells.length < 4) return null;
                return {
                    hours: cells[0].innerText.trim(),
                    temp: cells[2].innerText.trim(),
                    prec: cells[3].innerText.trim()
                };
            }).filter(item => item !== null);
        }""")
        
        browser.close()

        # Formattazione output
        csv = "hours,temp,precipitation\n"
        for entry in data:
            
            try:
                csv += f"{entry['hours']},{entry['temp']},{entry['precip']}\n"
                if int(entry['hours']) == 24:
                    break
            except Exception:
                # ignore non-numeric hour fields
                pass

        # Persist the CSV into the database with date (tomorrow) and city as unique key
        try:
            db_date = (datetime.today() + timedelta(days=1)).strftime("%Y-%m-%d")
            city_norm = city.strip().lower()
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute(
                "INSERT OR REPLACE INTO meteo_forecast (date, city, dati_meteo) VALUES (?, ?, ?)",
                (db_date, city_norm, csv)
            )
            conn.commit()
            conn.close()
            config.logger.info(f"Meteo salvato per {city_norm} - {db_date}")
        except Exception as e:
            config.logger.error(f"Errore salvataggio meteo: {e}")

        return f"Meteo per {days_from_today} giorni da oggi per {city.capitalize()}:\n{csv}"
    except Exception as e:
        return f"Non sono riuscito a trovare le previsioni meteo per {city.capitalize()} {e}"