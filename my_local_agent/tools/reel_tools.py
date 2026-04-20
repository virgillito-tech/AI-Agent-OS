# tools/reel_tools.py
import os
import requests
from urllib.parse import urljoin
from bs4 import BeautifulSoup
from langchain_core.tools import tool

@tool
def estrai_asset_sito(url: str) -> str:
    """
    Estrae immagini e testi principali da un sito web di una casa vacanze (o altro sito) per creare un Reel.
    Salva le immagini scaricate automaticamente nella cartella 'sandbox/assets_reel'.
    """
    print(f"🕵️‍♂️ [TOOL: Reel Maker] Scansione del sito {url} in corso...")
    
    # Crea la cartella dove salveremo le foto da montare
    cartella_assets = os.path.join("sandbox", "assets_reel")
    os.makedirs(cartella_assets, exist_ok=True)
    
    try:
        # Mascheriamo la richiesta per sembrare un vero browser (evita i blocchi)
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # 1. ESTRAZIONE TESTI (Titoli e Punti di forza)
        testi_estratti = []
        for tag in soup.find_all(['h1', 'h2', 'h3', 'p']):
            testo = tag.get_text(strip=True)
            # Prendiamo frasi a effetto: non troppo corte (inutili) e non troppo lunghe (non ci stanno nel video)
            if 15 < len(testo) < 80: 
                testi_estratti.append(testo)
        
        # Rimuoviamo duplicati e teniamo le 5 frasi più belle
        testi_unici = list(set(testi_estratti))[:5]
        
        # 2. ESTRAZIONE IMMAGINI
        immagini = soup.find_all('img')
        foto_scaricate = 0
        
        for img in immagini:
            if foto_scaricate >= 6: # Scarichiamo massimo 6 foto per il reel
                break
                
            img_url = img.get('src') or img.get('data-src') # Molti siti usano data-src per caricare le immagini
            if not img_url:
                continue
                
            # Rende l'URL assoluto (es. aggiunge https://tuosito.com se manca)
            img_url = urljoin(url, img_url)
            
            # Filtriamo via icone SVG o piccoli loghi
            if img_url.lower().endswith('.svg') or 'logo' in img_url.lower() or 'icon' in img_url.lower():
                continue
                
            try:
                # Scarichiamo fisicamente la foto
                img_data = requests.get(img_url, headers=headers, timeout=5).content
                nome_file = f"foto_reel_{foto_scaricate + 1}.jpg"
                percorso_file = os.path.join(cartella_assets, nome_file)
                
                with open(percorso_file, 'wb') as f:
                    f.write(img_data)
                foto_scaricate += 1
            except Exception as e:
                print(f"⚠️ Impossibile scaricare {img_url}: {e}")
                
        # Resoconto per l'AI
        res_testuale = f"✅ Estrazione completata!\n- Foto salvate con successo: {foto_scaricate} (nella cartella {cartella_assets})\n- Testi chiave estratti dal sito pronti per il video:\n"
        for t in testi_unici:
            res_testuale += f"  * \"{t}\"\n"
            
        return res_testuale
        
    except Exception as e:
        return f"❌ Errore durante l'estrazione degli asset: {e}"