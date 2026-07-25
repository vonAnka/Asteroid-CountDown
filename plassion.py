"""Global topplista via Plassion (https://plassion.com/rank/). Ersatte Dreamlo
eftersom Dreamlo kraver en betald uppgradering for HTTPS, och webblasare
blockerar HTTP-anrop fran en HTTPS-sida (t.ex. itch.io) som "mixed content".
Plassion ar HTTPS-only och skickar `Access-Control-Allow-Origin: *` (verifierat
med ett riktigt anrop), sa den funkar aven i webblasaren.

Samma tva-vagars fetch som tidigare (se historik i dreamlo.py om den finns
kvar): urllib i en bakgrundstrad pa desktop, och pygbags egna (odokumenterade)
JS-bro (platform.window.eval + platform.jsiter) i webblasaren -- INTE
pyodide.http.pyfetch, som saknas helt i pygbags runtime.

Plassion svarar med CSV, inte JSON:
    <leaderboard-namn>
    <filtertyp>,<antal>
    <varde>,<namn>,<datetid>
    ...
setrec.php kraver ocksa ett `uid` (unikt ANVANDAR-id, tanke att undvika
dubbletter fran samma spelare). Vi har inga persistenta spelarkonton -- varje
inskickad poang ska synas som en egen rad, sa vi slumpar ett uid per anrop.

Allt ar best-effort: strular natverket, nycklarna eller svaret fran Plassion
kraschar spelet ALDRIG -- funktionerna returnerar bara None/gor inget.

Nycklarna las fran .env (plassionPublicCode/plassionPrivateCode, INTE
incheckad i git). pygbags webbygge hoppar over dotfiler (.env skulle saknas i
webblasaren), sa nycklarna speglas automatiskt hit till plassion_keys.py -- en
vanlig .py-fil som FAKTISKT paketeras med. Den ar ocksa gitignorad; kor spelet
lokalt en gang efter att ha andrat .env sa den hinner uppdateras infor nasta
pygbag-bygge.

OBS: admin-koden (for att radera/hantera listan pa plassion.com/rank/) hor
INTE hemma har -- den behovs bara for manuell hantering, aldrig av spelet."""

import asyncio
import platform          # pa desktop: vanlig stdlib-modul. Under pygbag/emscripten:
import random             # bytt mot en JS-interop-shim (platform.window, .jsiter).
import sys
import urllib.parse
import urllib.request

TIMEOUT = 5
MAX_ENTRIES = 20
_IS_BROWSER = sys.platform == "emscripten"
_js_installed = False

_FETCH_JS = """
window.PlassionFetch = window.PlassionFetch || {};
window.PlassionFetch.get = function* (url) {
    var content = 'undefined';
    fetch(new Request(url, { method: 'GET', cache: 'no-store' }))
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
        platform.jsiter(platform.window.PlassionFetch.get(url)), timeout=TIMEOUT)


async def _fetch_text(url):
    if _IS_BROWSER:
        return await _browser_fetch_text(url)

    def _blocking():
        with urllib.request.urlopen(url, timeout=TIMEOUT) as resp:
            return resp.read().decode("utf-8")
    return await asyncio.to_thread(_blocking)


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


def _sync_keys_file(keys, path="plassion_keys.py"):
    """Skriver om plassion_keys.py om .env gett nya varden (no-op annars)."""
    content = (
        "# Auto-genererad av plassion.py fran .env -- kor spelet lokalt igen\n"
        "# efter att ha andrat .env for att uppdatera denna fil.\n"
        f"PUBLIC_CODE = {keys.get('plassionPublicCode', '')!r}\n"
        f"PRIVATE_CODE = {keys.get('plassionPrivateCode', '')!r}\n"
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
        import plassion_keys
        return plassion_keys.PUBLIC_CODE, plassion_keys.PRIVATE_CODE
    except Exception:
        return "", ""


PUBLIC_CODE, PRIVATE_CODE = _load_keys()


def _normalize(text):
    """Plassions CSV -> lista av {'name','score'}, hogst poang forst.
    Format: rad1=namn, rad2='typ,antal', sedan en rad per post: 'varde,namn,datum'."""
    lines = text.splitlines()
    out = []
    for line in lines[2:]:
        parts = line.split(",", 2)
        if len(parts) < 2:
            continue
        try:
            out.append({"name": parts[1], "score": int(parts[0])})
        except Exception:
            continue
    out.sort(key=lambda x: x["score"], reverse=True)
    return out


async def get_scores_plassion():
    """Hamtar den globala topplistan. Returnerar en lista [{'name','score'}, ...]
    eller None om det misslyckas (inga nycklar, natverk nere, trasigt svar)."""
    if not PUBLIC_CODE:
        return None
    # cache-buster: getrec.php svarar med Cache-Control: max-age=600, och
    # webblasarens fetch() respekterar det -- utan detta skulle listan
    # kunna visa en gammal (t.ex. tom) cachad version i flera minuter,
    # aven strax efter en riktig sparning.
    busy = random.randint(0, 2 ** 31 - 1)
    url = f"https://plassion.com/getrec.php?cod={PUBLIC_CODE}&qty={MAX_ENTRIES}&_={busy}"
    try:
        text = await _fetch_text(url)
        return _normalize(text)
    except Exception:
        return None


async def save_score_plassion(player_name, score):
    """Sparar en poang till den globala topplistan. Tyst fel om natverket
    eller nycklarna strular -- spelet fortsatter som vanligt. `uid` slumpas
    per anrop -- vi har inga persistenta spelarkonton, sa varje insparad
    poang ska bli en egen rad (Plassion dedupar annars pa uid)."""
    if not PRIVATE_CODE:
        return
    name = urllib.parse.quote(str(player_name))
    uid = random.randint(1, 2 ** 63 - 1)
    url = (f"https://plassion.com/setrec.php?cod={PRIVATE_CODE}"
           f"&uid={uid}&val={int(score)}&txt={name}")
    try:
        await _fetch_text(url)
    except Exception:
        pass
