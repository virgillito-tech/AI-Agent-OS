# tools/converter_tools.py
import os
from langchain_core.tools import tool

@tool
def converti_documento(input_path: str, formato_output: str) -> str:
    """
    Converte fisicamente un documento locale in un nuovo formato.
    Formati output supportati: 'docx', 'pdf', 'xlsx', 'json', 'csv'.
    Restituisce il percorso del nuovo file generato pronto per essere inviato o letto.
    """
    print(f"🔄 [TOOL: Converter] Conversione di {input_path} in {formato_output.upper()}...")
    
    if not os.path.exists(input_path):
        return f"Errore: Il file {input_path} non esiste sul computer."
        
    estensione_input = os.path.splitext(input_path)[1].lower().replace(".", "")
    formato_output = formato_output.lower().replace(".", "")
    
    # Prepariamo il percorso del nuovo file
    base_name = os.path.splitext(input_path)[0]
    output_path = f"{base_name}_convertito.{formato_output}"
    
    try:
        # 1. PDF -> WORD (DOCX)
        if estensione_input == "pdf" and formato_output == "docx":
            from pdf2docx import Converter
            cv = Converter(input_path)
            cv.convert(output_path, start=0, end=None)
            cv.close()
            return f"✅ Conversione completata. Il file Word è stato salvato qui: {output_path}"
            
        # 2. WORD (DOCX) -> PDF
        elif estensione_input == "docx" and formato_output == "pdf":
            from docx2pdf import convert
            convert(input_path, output_path)
            return f"✅ Conversione completata. Il file PDF è stato salvato qui: {output_path}"
            
        # 3. CSV -> EXCEL o JSON
        elif estensione_input == "csv" and formato_output in ["xlsx", "json"]:
            import pandas as pd
            df = pd.read_csv(input_path)
            if formato_output == "xlsx":
                df.to_excel(output_path, index=False)
            else:
                df.to_json(output_path, orient="records", indent=4)
            return f"✅ Conversione completata. Dati salvati in: {output_path}"
            
        # 4. EXCEL -> CSV o JSON
        elif estensione_input == "xlsx" and formato_output in ["csv", "json"]:
            import pandas as pd
            df = pd.read_excel(input_path)
            if formato_output == "csv":
                df.to_csv(output_path, index=False)
            else:
                df.to_json(output_path, orient="records", indent=4)
            return f"✅ Conversione completata. Dati salvati in: {output_path}"
            
        else:
            return f"⚠️ Errore: La conversione da {estensione_input.upper()} a {formato_output.upper()} non è ancora supportata nativamente."
            
    except Exception as e:
        return f"❌ Errore critico durante la conversione: {e}"