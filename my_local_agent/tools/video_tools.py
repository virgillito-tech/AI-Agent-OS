# tools/video_tools.py
import os
import json
from PIL import Image, ImageDraw, ImageFont
from moviepy.editor import ImageClip, concatenate_videoclips
from langchain_core.tools import tool

@tool
def crea_reel_video(testi_json: str) -> str:
    """
    Crea un Reel MP4 verticale (1080x1920) unendo le foto salvate nella cartella 'sandbox/assets_reel'.
    Passa una lista JSON di stringhe con i testi da sovrapporre. 
    Esempio parametro: '["Ready to discover Sicily?", "Un oasi di pace...", "Riscaldamento autonomo", "Prenota ora"]'
    """
    print("🎬 [TOOL: Video] Inizio montaggio Reel in corso (potrebbe volerci un minuto)...")
    cartella_assets = os.path.join("sandbox", "assets_reel")
    output_file = os.path.join("sandbox", "reel_casa_vacanze.mp4")
    
    if not os.path.exists(cartella_assets):
        return "❌ Errore: Cartella assets_reel non trovata. Hai prima estratto le foto?"
        
    try:
        testi = json.loads(testi_json)
    except:
        testi = ["Scopri la magia", "Relax totale", "Prenota ora!"] # Fallback di sicurezza
        
    # Trova le immagini scaricate dallo scraper
    immagini = [f for f in sorted(os.listdir(cartella_assets)) if f.lower().endswith(('.png', '.jpg', '.jpeg'))]
    if not immagini:
        return "❌ Errore: Nessuna foto trovata nella cartella assets_reel."
        
    clips = []
    target_w, target_h = 1080, 1920
    
    try:
        for i, img_name in enumerate(immagini):
            img_path = os.path.join(cartella_assets, img_name)
            img = Image.open(img_path).convert("RGBA") # Usiamo RGBA per le trasparenze
            
            # --- 1. Ridimensionamento e Taglio (Aspect Fill Verticale 9:16) ---
            img_ratio = img.width / img.height
            target_ratio = target_w / target_h
            
            if img_ratio > target_ratio:
                new_h = target_h
                new_w = int(new_h * img_ratio)
            else:
                new_w = target_w
                new_h = int(new_w / img_ratio)
                
            # Ridimensiona l'immagine mantenendo l'alta qualità
            img = img.resize((new_w, new_h), Image.Resampling.LANCZOS)
            
            # Ritaglia esattamente il centro per arrivare a 1080x1920
            left = (img.width - target_w) / 2
            top = (img.height - target_h) / 2
            right = (img.width + target_w) / 2
            bottom = (img.height + target_h) / 2
            img = img.crop((left, top, right, bottom))
            
            # --- 2. Disegno Testo con Sfondo Semitrasparente ---
            # Creiamo un livello trasparente per disegnare il box nero
            txt_layer = Image.new('RGBA', img.size, (255,255,255,0))
            draw = ImageDraw.Draw(txt_layer)
            
            testo = testi[i] if i < len(testi) else ""
            
            if testo:
                # Tenta di usare un bel font, altrimenti usa quello di sistema
                try:
                    font = ImageFont.truetype("/Library/Fonts/Arial Bold.ttf", 65)
                except:
                    try:
                        font = ImageFont.truetype("Arial.ttf", 65)
                    except:
                        font = ImageFont.load_default()
                
                # Calcola quanto spazio occupa il testo
                bbox = draw.textbbox((0, 0), testo, font=font)
                text_w = bbox[2] - bbox[0]
                text_h = bbox[3] - bbox[1]
                
                # Posizioniamo il testo in basso al centro (stile TikTok/Reel)
                x = (target_w - text_w) / 2
                y = target_h - 400 
                
                # Sfondo nero semitrasparente dietro la scritta
                padding = 30
                draw.rectangle([x - padding, y - padding, x + text_w + padding, y + text_h + padding], fill=(0, 0, 0, 160))
                # Testo bianco sopra
                draw.text((x, y), testo, fill="white", font=font)
            
            # Fondi l'immagine ritagliata con il livello del testo
            final_frame = Image.alpha_composite(img, txt_layer).convert("RGB")
            
            # Salva frame temporaneo
            temp_path = os.path.join(cartella_assets, f"temp_{i}.jpg")
            final_frame.save(temp_path)
            
            # --- 3. Crea la clip video (3 secondi per foto) ---
            clip = ImageClip(temp_path).set_duration(3.5)
            clips.append(clip)
            
        # Unisci tutte le clip e renderizza il file MP4 finale!
        final_video = concatenate_videoclips(clips, method="compose")
        final_video.write_videofile(output_file, fps=24, codec="libx264", audio=False, logger=None)
        
        # Pulizia dei file temporanei
        for i in range(len(immagini)):
            try:
                os.remove(os.path.join(cartella_assets, f"temp_{i}.jpg"))
            except: pass
            
        return f"✅ Reel montato con successo in formato 9:16! Il video finale è salvato in: {output_file}"
        
    except Exception as e:
        return f"❌ Errore critico durante il montaggio video: {e}"