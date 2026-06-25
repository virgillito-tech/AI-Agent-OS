import PyInstaller.__main__
import os
import platform
import sys

def build():
    print(f"Building on {platform.system()}...")
    
    # Crea un .env fittizio se non esiste per evitare crash di PyInstaller
    if not os.path.exists('.env'):
        with open('.env', 'w') as f:
            f.write('# Dummy env file per PyInstaller\n')
            
    sep = ';' if platform.system() == 'Windows' else ':'
    artifact_name = os.environ.get('ARTIFACT_NAME', 'AIAgentOS')
    
    # Assicurati che l'estensione non sia inclusa in ARTIFACT_NAME per il --name
    name_param = artifact_name.replace('.exe', '')
    
    args = [
        'main.py',
        '--name', name_param,
        '--onefile',
        f'--add-data=prompts{sep}prompts',
        f'--add-data=.env{sep}.env',
        '--clean'
    ]
    
    print(f"Running PyInstaller with args: {args}")
    PyInstaller.__main__.run(args)

if __name__ == '__main__':
    build()
