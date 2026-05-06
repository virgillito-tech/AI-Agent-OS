import subprocess

def run_applescript(script):
    result = subprocess.run(['osascript', '-e', script], capture_output=True, text=True)
    return result.stdout.strip(), result.stderr.strip()

# Test Spotify (don't play, just get state or something to avoid blasting music)
script = 'tell application "Spotify" to get player state'
out, err = run_applescript(script)
print("Spotify:", out, err)
