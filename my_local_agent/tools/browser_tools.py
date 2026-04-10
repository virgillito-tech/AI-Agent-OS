# tools/browser_tools.py
import os
import time
from langchain_core.tools import tool
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

def _inizializza_driver():
    """Configura e avvia il browser Chrome in modalità visibile."""
    chrome_options = Options()
    # chrome_options.add_argument("--headless") # Commenta questa riga per vedere il browser all'opera!
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_options)
    return driver

@tool
def automazione_login_sito(url: str, selettore_username: str, env_var_username: str, selettore_password: str, env_var_password: str, selettore_invio: str) -> str:
    """
    Esegue il login automatico su un sito web IN MODO SICURO.
    Invece di passare le password in chiaro, devi passare i NOMI delle variabili d'ambiente 
    presenti nel file .env (es. env_var_username='HF_EMAIL', env_var_password='HF_PASSWORD').
    """
    # 1. Recupero Sicuro delle Credenziali (l'AI non le vede!)
    username = os.getenv(env_var_username)
    password = os.getenv(env_var_password)
    
    if not username or not password:
        return f"❌ Errore: Non ho trovato le credenziali nel file .env per le variabili {env_var_username} e {env_var_password}."

    print(f"🔐 [TOOL: Browser] Avvio automazione login su: {url} (Credenziali: {env_var_username})...")
    driver = _inizializza_driver()
    
    try:
        driver.get(url)
        wait = WebDriverWait(driver, 15)
        
        # Inserimento Username 
        campo_user = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, selettore_username)))
        campo_user.send_keys(username)
        
        # Inserimento Password
        campo_pass = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, selettore_password)))
        campo_pass.send_keys(password)
        
        # Click sul pulsante di invio
        btn_invio = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, selettore_invio)))
        btn_invio.click()
        
        time.sleep(5) 
        url_finale = driver.current_url
        
        return f"✅ Login tentato con successo. URL attuale: {url_finale}. Il browser rimarrà aperto."
        
    except Exception as e:
        return f"❌ Errore durante l'automazione del login: {e}"

@tool
def naviga_e_clicca(url: str, selettore_click: str = None, testo_da_scrivere: str = None, selettore_input: str = None) -> str:
    """
    Strumento generico per navigare, cliccare o compilare moduli su un sito.
    Utile per azioni complesse dopo il login.
    """
    print(f"🌐 [TOOL: Browser] Navigazione su: {url}...")
    driver = _inizializza_driver()
    
    try:
        driver.get(url)
        time.sleep(2)
        
        report = f"Navigato su {url}. "
        
        if selettore_input and testo_da_scrivere:
            campo = driver.find_element(By.CSS_SELECTOR, selettore_input)
            campo.send_keys(testo_da_scrivere)
            report += f"Scritto '{testo_da_scrivere}' nel campo {selettore_input}. "
            
        if selettore_click:
            bottone = driver.find_element(By.CSS_SELECTOR, selettore_click)
            bottone.click()
            report += f"Cliccato su {selettore_click}. "
            
        return f"✅ Operazione completata: {report}"
        
    except Exception as e:
        return f"❌ Errore durante l'automazione browser: {e}"
    finally:
        driver.quit() # Qui chiudiamo per pulizia sessione