import platform
import asyncio
import subprocess
import re

_gpu_percent: float = 0.0

async def gpu_polling_loop():
    global _gpu_percent
    sistema = platform.system().lower()
    
    while True:
        try:
            valore_rilevato = 0.0
            if sistema == "darwin":
                cmd = ["ioreg", "-c", "IOAccelerator", "-r", "-l"]
                process = await asyncio.get_event_loop().run_in_executor(
                    None, 
                    lambda: subprocess.check_output(cmd, stderr=subprocess.DEVNULL).decode()
                )
                match_renderer = re.search(r'"Renderer Utilization %"=(\d+)', process)
                match_device = re.search(r'"Device Utilization %"=(\d+)', process)
                if match_renderer and int(match_renderer.group(1)) > 0:
                    valore_rilevato = float(match_renderer.group(1))
                elif match_device:
                    valore_rilevato = float(match_device.group(1))
            
            elif sistema in ["windows", "linux"]:
                try:
                    res = subprocess.check_output(["nvidia-smi", "--query-gpu=utilization.gpu", "--format=csv,noheader,nounits"], stderr=subprocess.STDOUT).decode()
                    valore_rilevato = float(res.strip())
                except Exception:
                    pass

            _gpu_percent = valore_rilevato
        except Exception:
            _gpu_percent = 0.0
            
        # Aumentato da 2 a 5 secondi per ridurre il carico CPU
        await asyncio.sleep(5)

def get_gpu_percent() -> float:
    return _gpu_percent
