"""Global topplista via Dreamlo (http://dreamlo.com). Fungerar i webblasaren
(pygbag/pyodide, via pyfetch) och pa desktop (via urllib, i en bakgrundstrad
sa spelloopen inte fryser). Allt ar best-effort: strular natverket, nycklarna
eller svaret fran Dreamlo kraschar spelet ALDRIG -- funktionerna returnerar
bara None/gor inget, och main.py faller tillbaka pa den lokala topplistan.

Nycklarna las fran .env (publicCode/privateCode, INTE incheckad i git).
pygbags webbygge hoppar over dotfiler (.env skulle saknas i webblasaren), sa
nycklarna speglas automatiskt hit till dreamlo_keys.py -- en vanlig .py-fil
som FAKTISKT paketeras med. Den ar ocksa gitignorad (innehaller nycklarna i
klartext); kor spelet lokalt en gang efter att ha andrat .env sa den hinner
uppdateras infor nasta pygbag-bygge."""

import asyncio
import json
import sys
import urllib.parse
import urllib.request

TIMEOUT = 5


def _read_env(path=".env"):
    keys = {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, _, v = line.partition("=")
                keys[k.strip()] = v.strip().strip('"').strip("'")
    except Exception:
        pass
    return keys


def _sync_keys_file(keys, path="dreamlo_keys.py"):
    """Skriver om dreamlo_keys.py om .env gett nya varden (no-op annars)."""
    content = (
        "# Auto-genererad av dreamlo.py fran .env -- kor spelet lokalt igen\n"
        "# efter att ha andrat .env for att uppdatera denna fil.\n"
        f"PUBLIC_KEY = {keys.get('publicCode', '')!r}\n"
        f"PRIVATE_KEY = {keys.get('privateCode', '')!r}\n"
    )
    try:
        try:
            with open(path, "r", encoding="utf-8") as f:
                if f.read() == content:
                    return
        except Exception:
            pass
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
    except Exception:
        pass


def _load_keys():
    if sys.platform != "emscripten":
        env = _read_env()
        if env:
            _sync_keys_file(env)
    try:
        import dreamlo_keys
        return dreamlo_keys.PUBLIC_KEY, dreamlo_keys.PRIVATE_KEY
    except Exception:
        return "", ""


PUBLIC_KEY, PRIVATE_KEY = _load_keys()


def _normalize(data):
    """Dreamlos JSON -> lista av {'name','score'}, hogst poang forst. Hanterar
    kvirkarna: 'leaderboard'/'entry' saknas eller ar '' nar listan ar tom, och
    'entry' ar en enda dict (inte lista) nar det bara finns EN post."""
    lb = data.get("dreamlo", {}).get("leaderboard", {})
    entry = lb.get("entry") if isinstance(lb, dict) else None
    if not entry:
        entry = []
    elif isinstance(entry, dict):
        entry = [entry]
    out = []
    for e in entry:
        try:
            out.append({"name": str(e.get("name", "???")), "score": int(e.get("score", 0) or 0)})
        except Exception:
            continue
    out.sort(key=lambda x: x["score"], reverse=True)
    return out


async def get_scores_dreamlo():
    """Hamtar den globala topplistan. Returnerar en lista [{'name','score'}, ...]
    eller None om det misslyckas (inga nycklar, natverk nere, trasigt svar)."""
    if not PUBLIC_KEY:
        return None
    url = f"http://dreamlo.com/lb/{PUBLIC_KEY}/json"
    try:
        if sys.platform == "emscripten":
            from pyodide.http import pyfetch
            response = await pyfetch(url)
            data = await response.json()
        else:
            def _blocking():
                with urllib.request.urlopen(url, timeout=TIMEOUT) as resp:
                    return json.loads(resp.read().decode("utf-8"))
            data = await asyncio.to_thread(_blocking)
        return _normalize(data)
    except Exception:
        return None


async def save_score_dreamlo(player_name, score):
    """Sparar en poang till den globala topplistan. Tyst fel om natverket
    eller nycklarna strular -- spelet fortsatter som vanligt."""
    if not PRIVATE_KEY:
        return
    name = urllib.parse.quote(str(player_name))
    url = f"http://dreamlo.com/lb/{PRIVATE_KEY}/add/{name}/{int(score)}"
    try:
        if sys.platform == "emscripten":
            from pyodide.http import pyfetch
            await pyfetch(url)
        else:
            def _blocking():
                with urllib.request.urlopen(url, timeout=TIMEOUT) as resp:
                    resp.read()
            await asyncio.to_thread(_blocking)
    except Exception:
        pass
