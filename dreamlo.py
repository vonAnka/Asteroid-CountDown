"""Global topplista via Dreamlo (http://dreamlo.com). Fungerar pa desktop via
urllib (i en bakgrundstrad sa spelloopen inte fryser) och i webblasaren via
pygbags EGNA (odokumenterade) JS-bro -- INTE pyodide.http.pyfetch, som visade
sig sakna helt i pygbags runtime (dess "pyodide compat layer" ar bara en stub
som loggar "N/I"). pygbag byter ut sjalva stdlib-modulen `platform` mot en
JS-interop-shim nar koden kors under emscripten (samma modul anvands av
pygbags egen bootstrap for att t.ex. ladda numpy/pygame-ce via dlopen), med
`platform.window` (rå JS window-objekt) och `platform.jsiter` (kor en JS-
generatorfunktion till den ar klar och hamtar sista yield som resultat).
Vi installerar en liten JS-fetch-generator via `platform.window.eval(...)`
och kor den via `platform.jsiter`, exakt samma monster pygbag sjalv anvander
internt (support/cross/aio/fetch.py) -- fast med ett fix sa ett natverksfel
faktiskt avslutar generatorn istallet for att hanga polling-loopen for evigt.

Allt ar best-effort: strular natverket, nycklarna eller svaret fran Dreamlo
kraschar spelet ALDRIG -- funktionerna returnerar bara None/gor inget.

Nycklarna las fran .env (publicCode/privateCode, INTE incheckad i git).
pygbags webbygge hoppar over dotfiler (.env skulle saknas i webblasaren), sa
nycklarna speglas automatiskt hit till dreamlo_keys.py -- en vanlig .py-fil
som FAKTISKT paketeras med. Den ar ocksa gitignorad (innehaller nycklarna i
klartext); kor spelet lokalt en gang efter att ha andrat .env sa den hinner
uppdateras infor nasta pygbag-bygge."""

import asyncio
import json
import platform          # pa desktop: vanlig stdlib-modul. Under pygbag/emscripten:
import sys                # bytt mot en JS-interop-shim (platform.window, .jsiter).
import urllib.parse
import urllib.request

TIMEOUT = 5
_IS_BROWSER = sys.platform == "emscripten"
_js_installed = False

_FETCH_JS = """
window.DreamloFetch = window.DreamloFetch || {};
window.DreamloFetch.get = function* (url) {
    var content = 'undefined';
    fetch(new Request(url, { method: 'GET' }))
        .then(resp => resp.text())
        .then(text => { content = text; })
        .catch(err => { content = ''; });   // avslutar pollingen aven om fetch misslyckas
    while (content == 'undefined') {
        yield;
    }
    yield content;
};
"""


async def _browser_fetch_text(url):
    """Hamtar url som text via pygbags JS-bro (se moduldocstring). Kastar vid
    fel/timeout -- anroparen fangar."""
    global _js_installed
    if not _js_installed:
        platform.window.eval(_FETCH_JS)
        _js_installed = True
    return await asyncio.wait_for(
        platform.jsiter(platform.window.DreamloFetch.get(url)), timeout=TIMEOUT)


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
    if not _IS_BROWSER:
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
        if _IS_BROWSER:
            text = await _browser_fetch_text(url)
            data = json.loads(text)
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
        if _IS_BROWSER:
            await _browser_fetch_text(url)
        else:
            def _blocking():
                with urllib.request.urlopen(url, timeout=TIMEOUT) as resp:
                    resp.read()
            await asyncio.to_thread(_blocking)
    except Exception:
        pass
