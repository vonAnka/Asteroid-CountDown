"""Dev-startare for balansering: kor spelet som desktop och startar om det
automatiskt varje gang config.py sparas. INGEN pygbag-byggtid.

    python dev.py

Andra varden i config.py, spara -> spelet startar om med de nya vardena.
Avsluta med Ctrl+C i terminalen (eller stang fonstret och tryck Ctrl+C).

pygbag behovs bara nar du vill testa sjalva webb-bygget for itch.io:
    python -m pygbag --port 8000 main.py
"""

import os
import subprocess
import sys
import time

WATCH = "config.py"          # filen vi bevakar
TARGET = "main.py"           # spelet som startas om


def main():
    proc = None
    last_mtime = 0.0
    print("dev.py: kor spelet, startar om nar %s sparas (Ctrl+C avslutar)" % WATCH)
    try:
        while True:
            try:
                mtime = os.path.getmtime(WATCH)
            except OSError:
                mtime = last_mtime
            # starta om om config andrats eller om spelet avslutats (stangt fonster)
            if mtime != last_mtime or (proc is not None and proc.poll() is not None):
                if mtime != last_mtime and proc is not None:
                    print("-> %s andrad, startar om..." % WATCH)
                last_mtime = mtime
                if proc is not None and proc.poll() is None:
                    proc.terminate()
                    try:
                        proc.wait(timeout=3)
                    except subprocess.TimeoutExpired:
                        proc.kill()
                proc = subprocess.Popen([sys.executable, TARGET])
            time.sleep(0.4)
    except KeyboardInterrupt:
        print("\ndev.py: avslutar")
        if proc is not None and proc.poll() is None:
            proc.terminate()


if __name__ == "__main__":
    main()
