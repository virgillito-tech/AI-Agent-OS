# tools/video_tools.py
import os
import torch
import json
import platform
import uuid
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
    


def get_video_device():
    if torch.cuda.is_available(): return "cuda"
    if platform.system() == "Darwin" and torch.backends.mps.is_available(): return "mps"
    return "cpu"

@tool
def genera_video_universale(prompt: str, model_id: str = None, num_frames: int = 24) -> str:
    """
    Genera una clip video da un prompt. 
    Supporta: 'THUDM/CogVideoX-2b' (Qualità) o 'damo-vilab/text-to-video-ms-1.5m' (Veloce).
    """
    import torch
    import os
    import uuid
    from diffusers import CogVideoXPipeline, DiffusionPipeline, DPMSolverMultistepScheduler
    from diffusers.utils import export_to_video

    # 1. FORZATURA GLOBALE PRECISIONE (Per evitare float64 "clandestini")
    torch.set_default_dtype(torch.float32)
    
    model_name = model_id or os.getenv("VIDEO_MODEL_NAME", "THUDM/CogVideoX-2b")
    # Fix per modello leggero (usa un ID più recente se il vecchio dà 404)
    if "damo" in model_name or "ali-vilab" in model_name:
        model_name = "strangerzonehf/ModelScope-text-to-video-ms-1.5m-baked"

    device = "mps" if torch.backends.mps.is_available() else "cpu"
    print(f"🎬 [VIDEO FACTORY] Avvio su {device} | Modello: {model_name}")

    try:
        if "CogVideoX" in model_name:
            # Carichiamo in float32 per stabilità totale su M3
            pipe = CogVideoXPipeline.from_pretrained(model_name, torch_dtype=torch.float32)
            
            # --- FORCE CAST CRUCIALE ---
            # Cicliamo su ogni parte del modello per assicurarci che NULLA sia float64
            pipe.vae.to(dtype=torch.float32)
            pipe.transformer.to(dtype=torch.float32)
            pipe.text_encoder.to(dtype=torch.float32)
        else:
            pipe = DiffusionPipeline.from_pretrained(model_name, torch_dtype=torch.float32)
            pipe.scheduler = DPMSolverMultistepScheduler.from_config(pipe.scheduler.config)

        pipe.to(device)

        # Ottimizzazione memoria per 18GB VRAM
        if device == "mps":
            pipe.enable_attention_slicing()
            # Se hai meno di 36GB di RAM, abilitiamo l'offload
            pipe.enable_model_cpu_offload()

        # Generazione
        print(f"🌀 Rendering frame in corso...")
        # Usiamo un seed fisso per evitare calcoli randomici float64
        generator = torch.Generator(device="cpu").manual_seed(42)
        
        video_frames = pipe(
            prompt=prompt,
            num_inference_steps=25, 
            num_frames=num_frames,
            generator=generator
        ).frames[0]

        # 4. SALVATAGGIO
        os.makedirs("sandbox/videos", exist_ok=True)
        filename = f"video_{uuid.uuid4().hex[:4]}.mp4"
        path = os.path.abspath(os.path.join("sandbox/videos", filename))
        
        export_to_video(video_frames, path, fps=8)
        
        # Pulizia VRAM
        del pipe
        torch.mps.empty_cache()

        return f"✅ Video generato con successo! Percorso: {path}"

    except Exception as e:
        error_msg = str(e)
        print(f"❌ [ERRORE VIDEO] {error_msg}")
        if "float64" in error_msg:
            return "❌ Errore Hardware Persistente: Il Mac prova ancora a usare float64. Ti consiglio di usare il modello leggero 'strangerzonehf/ModelScope-text-to-video-ms-1.5m-baked'."
        return f"❌ Errore: {error_msg}"