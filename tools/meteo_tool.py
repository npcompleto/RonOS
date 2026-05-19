from langchain_core.tools import tool
import config
import requests
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright, expect

load_dotenv()

@tool
def get_meteo_domani(city: str) -> str:
    """Ottiene le previsioni meteo per una città data"""

    url = f"https://www.ilmeteo.it/meteo/{city.lower()}/domani"
    
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
            
            csv += f"{entry['hours']},{entry['temp']},{entry['prec']}\n"
            if int(entry['hours']) == 24:
                break
        
        return f"Meteo per {city.capitalize()}:\n{csv}"
    except Exception as e:
        return f"Non sono riuscito a trovare le previsioni meteo per {city.capitalize()} {e}"