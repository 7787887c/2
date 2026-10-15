import json
import time
import random
import string
import re
import os
import argparse
import webbrowser
import requests
import requests.adapters
import concurrent.futures
import threading
from datetime import datetime
from pathlib import Path
from threading import Lock

try:
    from colorama import Fore, Style, init
    init(autoreset=True)
except ImportError:
    class _Dummy:
        def __getattr__(self, _): return ""
    Fore = Style = _Dummy()

CONFIG_PATH = Path(__file__).parent / "config.json"
CACHE_PATH = Path(__file__).parent / "cache_hits.json"
SEEN_PATH = Path(__file__).parent / "seen.json"

BANNER = f"""{Fore.MAGENTA}
 ████  █████ █████ █   █
 █     █     █     █  █
 ████  ████  ████  ███
    █  █     █     █  █
 ████  █████ █████ █   █  nyx sniper v4 — turbo (no-discord)
{Style.RESET_ALL}"""

BLOCKLIST_OBVIOS = {
    "aaa","abc","123","000","111","xxx","zzz","lol","wtf","omg","god","sex","hot","top","pro","bot","api","app","web","dev","vip","ceo","bio","car","dog","cat","fox","owl","sky","sun","moon","star","ice","fire","fly","try","win","ace","king","queen","jack","nox","nyx","vex","kai","zay","eva","ada","lia","ana","mia","leo","max","sam","tom","bob","joe","kim","ray","jay","sky",
    "void","nova","lynx","aura","tur","epi","syz",
    "love","hate","life","dead","dark","light","fire","water","wind","earth","cold","warm","cool","best","good","nice","free","play","game","test","user","admin","root","help","info","home","work","time","year","city","girl","boy","man","baby","star","wolf","bear","lion","tiger","eagle",
    # extras 4c comuns que nunca liberam
    "abcd","qwer","asdf","zxcv","qwerty","aaaa","bbbb","cccc","dddd","test","code","data","site","page","name","user","pass","word","love","hate",
}

# bloqueia padrões visuais (3l e 4l)
RE_REPEATED = re.compile(r"^(.)\1+$")          # aaa / aaaa
RE_ABAB = re.compile(r"^(..)\1$")              # abab (4l)
RE_SEQUENCIAL_4 = re.compile(r"^(abcd|bcde|cdef|defg|efgh|fghi|ghij|hijk|ijkl|jklm|klmn|lmno|mnop|nopq|opqr|pqrs|qrst|rstu|stuv|tuvw|uvwx|vwxy|wxyz|qwer|asdf|zxcv)$")
RE_SEQUENCIAL_3 = re.compile(r"^(abc|bcd|cde|def|efg|fgh|ghi|hij|ijk|jkl|klm|lmn|mno|nop|opq|pqr|qrs|rst|stu|tuv|uvw|vwx|wxy|xyz|qwe|asd|zxc)$")
# compat alias
RE_4C_REPEATED = RE_REPEATED
RE_4C_ABAB = RE_ABAB
RE_4C_SEQUENCIAL = RE_SEQUENCIAL_4

RE_3CHAR_VALIDO = re.compile(r"^[a-z0-9][a-z0-9_\.]{1}[a-z0-9]$")

UA_LIST = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:124.0) Gecko/20100101 Firefox/124.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15",
]

HEADERS_BASE = {
    "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Cache-Control": "no-cache",
    "Pragma": "no-cache",
}

_thread_local = threading.local()

def get_session(pool_size: int = 14) -> requests.Session:
    if not hasattr(_thread_local, "session"):
        s = requests.Session()
        adapter = requests.adapters.HTTPAdapter(pool_connections=pool_size, pool_maxsize=pool_size, max_retries=0, pool_block=False)
        s.mount("https://", adapter)
        s.mount("http://", adapter)
        _thread_local.session = s
    return _thread_local.session

def rand_headers(extra: dict | None = None) -> dict:
    h = dict(HEADERS_BASE)
    h["User-Agent"] = random.choice(UA_LIST)
    if extra:
        h.update(extra)
    return h

# ---------- io helpers ----------
def load_config():
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

def load_seen():
    if SEEN_PATH.exists():
        try: return set(json.loads(SEEN_PATH.read_text(encoding="utf-8")))
        except: return set()
    return set()

def save_seen(seen: set):
    SEEN_PATH.write_text(json.dumps(sorted(seen), indent=2), encoding="utf-8")

def load_cache():
    if CACHE_PATH.exists():
        try: return json.loads(CACHE_PATH.read_text(encoding="utf-8"))
        except: return {}
    return {}

def save_cache(cache: dict):
    CACHE_PATH.write_text(json.dumps(cache, indent=2, ensure_ascii=False), encoding="utf-8")

def is_blocked(u: str, extra: list) -> bool:
    u = u.lower().strip()
    if u in BLOCKLIST_OBVIOS: return True
    if u in {x.lower() for x in extra}: return True
    if u.startswith(("_",".")) or u.endswith(("_",".")): return True
    if "__" in u or ".." in u or "._" in u or "_." in u: return True
    if len(u) == 3:
        if RE_REPEATED.match(u): return True
        if RE_SEQUENCIAL_3.match(u): return True
    if len(u) == 4:
        if RE_REPEATED.match(u): return True
        if RE_ABAB.match(u): return True
        if RE_SEQUENCIAL_4.match(u): return True
        if u[0] == u[3] and u[0] != u[1]: return True  # abca
    return False

# ---------- geradores ----------
# 3c = misturado letras+números + semi com _/.  Ex: y_2, u4v, t.v, c2x  (3 chars)
# 3l = apenas letras [a-z]{3}
# 4l = apenas letras [a-z]{4}

def gen_3c(qtd: int, semi_ratio: float, usar_ponto: bool) -> list[str]:
    out = []
    chars_alnum = string.ascii_lowercase + string.digits
    chars_alpha = string.ascii_lowercase
    tentativas = 0
    while len(out) < qtd and tentativas < qtd * 80:
        tentativas += 1
        quer_semi = random.random() < semi_ratio
        if quer_semi:
            sep = random.choice(["_", "."] if usar_ponto else ["_"])
            a = random.choice(chars_alnum)
            b = random.choice(chars_alnum)
            # evita dígito+dígito semi (ex 1_2) — feio e raro liberar bonito
            if a.isdigit() and b.isdigit():
                # 70% chance de reroll um dos dois pra letra
                if random.random() < 0.7:
                    if random.random() < 0.5: a = random.choice(chars_alpha)
                    else: b = random.choice(chars_alpha)
            cand = f"{a}{sep}{b}"
        else:
            # alphanum puro de 3 — força pelo menos 1 dígito em 85% pra fugir dos óbvios
            if random.random() < 0.85:
                pos_num = random.randint(0, 2)
                arr = [random.choice(chars_alnum) for _ in range(3)]
                arr[pos_num] = random.choice(string.digits)
                cand = "".join(arr)
            else:
                cand = "".join(random.choice(chars_alpha) for _ in range(3))
        cand = cand.lower()
        if not RE_3CHAR_VALIDO.match(cand): continue
        if is_blocked(cand, []): continue
        if cand not in out:
            out.append(cand)
    return out

def gen_3l(qtd: int) -> list[str]:
    out = []
    tent = 0
    while len(out) < qtd and tent < qtd * 40:
        tent += 1
        cand = "".join(random.choice(string.ascii_lowercase) for _ in range(3))
        if is_blocked(cand, []): continue
        if cand in out: continue
        out.append(cand)
    return out

def gen_4l(qtd: int) -> list[str]:
    out = []
    tent = 0
    while len(out) < qtd and tent < qtd * 40:
        tent += 1
        cand = "".join(random.choice(string.ascii_lowercase) for _ in range(4))
        if is_blocked(cand, []): continue
        if cand in out: continue
        out.append(cand)
    return out

# compat — código antigo chamava gen_4char_letras
def gen_4char_letras(qtd: int) -> list[str]:
    return gen_4l(qtd)

# ---------- checks OTIMIZADOS ----------
def check_instagram(username: str, session: requests.Session | None = None) -> bool | None:
    """
    Prioriza endpoint leve web_profile_info (JSON ~2kb) antes do HTML pesado.
    404 / user null = livre
    200 com user = ocupado
    429 = None (rate)
    """
    s = session or get_session()
    # 1) API leve
    api_url = f"https://www.instagram.com/api/v1/users/web_profile_info/?username={username}"
    try:
        r = s.get(api_url, headers=rand_headers({"X-IG-App-ID": "936619743392459", "X-Requested-With": "XMLHttpRequest", "Accept": "*/*"}), timeout=10, allow_redirects=False)
        if r.status_code == 404:
            return True
        if r.status_code == 200:
            try:
                j = r.json()
                data = j.get("data", {})
                user = data.get("user")
                if user is None:
                    return True
                # se veio user com username, está ocupado
                return False
            except:
                txt = r.text
                if "Sorry, this page isn" in txt:
                    return True
                return False
        if r.status_code == 429:
            return None
        # 302/outro -> cai pro fallback
    except requests.RequestException:
        pass

    # 2) fallback HTML (comparável mas mais pesado)
    try:
        url = f"https://www.instagram.com/{username}/"
        r = s.get(url, headers=rand_headers(), timeout=10, allow_redirects=True)
        if r.status_code == 404:
            return True
        if r.status_code == 200:
            txt = r.text
            if "Sorry, this page isn" in txt or "Esta p\u00e1gina n\u00e3o est\u00e1 dispon\u00edvel" in txt:
                return True
            return False
        if r.status_code == 429:
            return None
        return None
    except requests.RequestException:
        return None

def check_tiktok(username: str, session: requests.Session | None = None) -> bool | None:
    """
    Usa oEmbed (API leve). 404 = livre, 200+author_name = ocupado.
    Não confia em HTML 200 (TikTok sempre retorna 200 com 'Please wait...').
    """
    s = session or get_session()
    try:
        oembed_url = f"https://www.tiktok.com/oembed?url=https://www.tiktok.com/@{username}"
        r = s.get(oembed_url, headers=rand_headers(), timeout=10)
        if r.status_code == 200:
            try:
                data = r.json()
                if data.get("author_name") or data.get("title"):
                    return False
                return False
            except:
                return False
        if r.status_code == 404:
            return True
        if r.status_code == 429:
            return None
        # fallback só se oEmbed bloqueou: checa 404 no html
        r2 = s.get(f"https://www.tiktok.com/@{username}", headers=rand_headers(), timeout=10, allow_redirects=True)
        if r2.status_code == 404:
            return True
        if r2.status_code == 200:
            return False
        return None
    except requests.RequestException:
        return None

def check_user_fast(username: str, plataformas: list[str]) -> tuple[str, str | None, str, str]:
    """
    Passada rápida SEM sleep — roda dentro do pool.
    Retorna candidato livre ou status ocupado/rate.
    A verificação dupla é feita FORA do pool pelo caller.
    """
    s = get_session()
    # opcional: micro delay entre checks pra não ser rajada perfeita
    # delay é gerenciado fora; aqui é direto
    ig_res = None
    tt_res = None
    if "instagram" in plataformas:
        ig_res = check_instagram(username, s)
    if "tiktok" in plataformas:
        tt_res = check_tiktok(username, s)

    # se algum marcou livre, retorna como candidato (ainda não confirmado)
    if ig_res is True:
        return (username, "Instagram", "candidato", "IG oEmbed/API 404")
    if tt_res is True:
        return (username, "TikTok", "candidato", "TT oEmbed 404")
    # rate se nenhuma confirmou ocupado
    if ig_res is None or tt_res is None:
        if ig_res is False or tt_res is False:
            return (username, None, "ocupado", "uma plataforma confirmou ocupado")
        return (username, None, "rate", "429/incerto")
    return (username, None, "ocupado", "ambas ocupadas")

def double_check(username: str, plataforma: str) -> tuple[bool, str]:
    """Verificação dupla FORA do pool — dorme sem travar worker."""
    time.sleep(random.uniform(1.2, 1.8))
    s = get_session()
    if plataforma == "Instagram":
        c = check_instagram(username, s)
    else:
        c = check_tiktok(username, s)
    if c is True:
        return True, "confirmado 2x"
    return False, f"falso positivo {plataforma} — 2ª checagem deu {c}"

def notificar(webhook_url: str, username: str, plataforma: str, detalhe: str):
    embed = {
        "title": f"@{username}  •  {plataforma}  •  LIVRE ✓ (verificado 2x)",
        "description": f"`{username}` parece **disponível** no **{plataforma}**! (dupla checagem OK)\n→ https://www.instagram.com/{username}/  •  https://www.tiktok.com/@{username}",
        "color": 3066993,
        "fields": [
            {"name": "Username", "value": f"`{username}`", "inline": True},
            {"name": "Plataforma", "value": plataforma, "inline": True},
            {"name": "Hora", "value": datetime.now().strftime("%d/%m/%Y %H:%M:%S"), "inline": True},
            {"name": "Tamanho", "value": f"{len(username)}c ({'semi' if '_' in username or '.' in username else 'alphanum' if any(c.isdigit() for c in username) else 'letras'})", "inline": True},
        ],
        "footer": {"text": f"nyx sniper v4 • {detalhe}"},
        "timestamp": datetime.utcnow().isoformat()
    }
    payload = {"embeds": [embed], "username": "nyx sniper", "content": f"@here `@{username}` livre no {plataforma}! (verificado)"}
    try:
        r = requests.post(webhook_url, json=payload, timeout=12)
        if r.status_code not in (200, 204):
            print(f"{Fore.RED}[!] webhook {r.status_code}: {r.text[:300]}{Style.RESET_ALL}")
        else:
            print(f"{Fore.GREEN}[→] webhook enviado @{username} ({plataforma}){Style.RESET_ALL}")
    except Exception as e:
        print(f"{Fore.RED}[!] webhook erro: {e}{Style.RESET_ALL}")

def tocar_som():
    try:
        import winsound
        winsound.Beep(1200, 300)
        winsound.Beep(1600, 400)
    except:
        print("\a", end="")

def main(once: bool | None = None, no_browser: bool | None = None, no_sound: bool | None = None):
    # CLI pra rodar no GitHub Actions (--once = 1 rodada e sai)
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--no-browser", action="store_true")
    parser.add_argument("--no-sound", action="store_true")
    args, _ = parser.parse_known_args()
    if once is None: once = args.once
    if no_browser is None: no_browser = args.no_browser
    if no_sound is None: no_sound = args.no_sound
    # env var do GitHub Secrets tem prioridade
    env_webhook = os.environ.get("WEBHOOK_URL", "").strip()

    print(BANNER)
    cfg = load_config()
    webhook = env_webhook or cfg.get("webhook_url", "")
    has_webhook = webhook.startswith("https://") and "SEU_ID" not in webhook
    if not has_webhook:
        print(f"{Fore.YELLOW}[!] sem webhook válido — dry-run (só console){Style.RESET_ALL}")
        webhook = None

    # remove discord se ainda vier no config antigo
    plataformas = [p.lower() for p in cfg.get("plataformas", ["instagram", "tiktok"]) if p.lower() != "discord"]
    if not plataformas:
        plataformas = ["instagram", "tiktok"]
    intervalo = int(cfg.get("intervalo_segundos", 6))
    jitter = float(cfg.get("jitter", 0.7))
    delay_entre = float(cfg.get("delay_entre_checks", 0))
    g = cfg.get("gerador", {})
    # novo: 3c misturado + 3l só letras + 4l só letras (compat com config antigo)
    qtd_3c = int(g.get("qtd_3c_por_rodada", g.get("qtd_3char_por_rodada", 40)))
    qtd_3l = int(g.get("qtd_3l_por_rodada", 30))
    qtd_4l = int(g.get("qtd_4l_por_rodada", g.get("qtd_4char_por_rodada", 30)))
    semi_ratio = float(g.get("semi_ratio_3char", g.get("semi_ratio_3c", 0.35)))
    usar_ponto = bool(g.get("usar_ponto", True))
    abrir_nav = bool(cfg.get("abrir_navegador_no_hit", True))
    som = bool(cfg.get("som_no_hit", True))
    if no_browser:
        abrir_nav = False
    if no_sound:
        som = False
    extra_block = cfg.get("blocklist_extra", [])
    workers = int(cfg.get("workers", 14))

    seen = load_seen()
    cache = load_cache()

    print(f"{Fore.CYAN}[cfg] v4 turbo: Session+keep-alive, double-check fora do pool, IG via web_profile_info{Style.RESET_ALL}")
    print(f"{Fore.CYAN}[cfg] 3c:{qtd_3c} misturado (y_2/u4v/t.v) + 3l:{qtd_3l} só letras + 4l:{qtd_4l} só letras = {qtd_3c+qtd_3l+qtd_4l}/rodada{Style.RESET_ALL}")
    print(f"{Fore.CYAN}[cfg] plataformas: {', '.join(plataformas)} | workers: {workers} | intervalo: {intervalo}s ±{jitter}{Style.RESET_ALL}")
    print(f"{Fore.CYAN}[cfg] discord removido | seen: {len(seen)} | webhook: {'ok' if webhook else 'off'}{Style.RESET_ALL}")
    print(f"{Fore.CYAN}[i] CTRL+C pra parar\n{Style.RESET_ALL}")

    rodada = 0
    hits_total = len(cache)
    lock = Lock()
    rodadas_desde_save = 0

    try:
        while True:
            rodada += 1
            t0 = time.time()
            batch_3c = gen_3c(qtd_3c, semi_ratio, usar_ponto)
            batch_3l = gen_3l(qtd_3l)
            batch_4l = gen_4l(qtd_4l)
            # filtra seen + blocklist_extra (não re-checa) — compat: aliases antigos ainda funcionam
            batch_3c = [u for u in batch_3c if u not in seen and not is_blocked(u, extra_block)]
            batch_3l = [u for u in batch_3l if u not in seen and not is_blocked(u, extra_block)]
            batch_4l = [u for u in batch_4l if u not in seen and not is_blocked(u, extra_block)]
            batch = batch_3c + batch_3l + batch_4l
            random.shuffle(batch)

            if not batch:
                print(f"{Fore.YELLOW}[!] rodada {rodada}: tudo já visto, gerando de novo...{Style.RESET_ALL}")
                time.sleep(1)
                continue

            print(f"{Fore.MAGENTA}— rodada {rodada} {datetime.now().strftime('%H:%M:%S')} — {len(batch_3c)}×3c + {len(batch_3l)}×3l + {len(batch_4l)}×4l = {len(batch)} checks com {workers} workers —{Style.RESET_ALL}")

            for u in batch:
                seen.add(u)

            rate_count = 0
            ocupado_count = 0
            falso_count = 0
            candidatos: list[tuple[str, str]] = []
            done = 0
            total = len(batch)

            # fase 1: checagem rápida em paralelo (sem sleep)
            with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as ex:
                fut2user = {ex.submit(check_user_fast, u, plataformas): u for u in batch}
                for fut in concurrent.futures.as_completed(fut2user):
                    username, plat_hit, status, detalhe = fut.result()
                    done += 1
                    tag = f"{len(username)}c"
                    if delay_entre > 0:
                        time.sleep(delay_entre * random.uniform(0.5, 1.5))

                    if status == "candidato" and plat_hit:
                        candidatos.append((username, plat_hit))
                        tipo = "semi" if "_" in username or "." in username else ("alphanum" if any(c.isdigit() for c in username) else "letras")
                        print(f"{Fore.YELLOW}[{done}/{total}] [?] @{username} ({tag} {tipo}) candidato {plat_hit} — re-checando...{Style.RESET_ALL}")
                    elif status == "rate":
                        rate_count += 1
                        print(f"{Fore.YELLOW}[{done}/{total}] [~] @{username} {tag} rate/incerto{Style.RESET_ALL}")
                    else:
                        ocupado_count += 1
                        # log mais silencioso pra não spammar
                        if done % 20 == 0 or total < 20:
                            print(f"{Fore.WHITE}[{done}/{total}] [-] @{username} {tag} ocupado{Style.RESET_ALL}")

            # fase 2: double-check SEQUENCIAL fora do pool (não trava workers)
            if candidatos:
                print(f"{Fore.CYAN}[i] {len(candidatos)} candidato(s) — verificação dupla...{Style.RESET_ALL}")
                for username, plat in candidatos:
                    ok, detalhe = double_check(username, plat)
                    tag = f"{len(username)}c"
                    if ok:
                        hits_total += 1
                        tipo = "semi" if "_" in username or "." in username else ("alphanum" if any(c.isdigit() for c in username) else "letras")
                        print(f"{Fore.GREEN}[✓] HIT {hits_total}  @{username}  ({tag} {tipo}) LIVRE no {plat}! {detalhe}{Style.RESET_ALL}")
                        with lock:
                            cache[username] = {"plataforma": plat, "hora": datetime.now().isoformat(), "detalhe": detalhe}
                        if webhook:
                            notificar(webhook, username, plat, detalhe)
                        if som:
                            tocar_som()
                        if abrir_nav:
                            try: webbrowser.open(f"https://www.instagram.com/{username}/")
                            except: pass
                    else:
                        falso_count += 1
                        print(f"{Fore.YELLOW}[×] @{username} {tag} falso positivo filtrado — {detalhe}{Style.RESET_ALL}")
                        ocupado_count += 1
            else:
                # log final se não teve candidato
                print(f"{Fore.WHITE}[i] nenhum candidato nesta rodada — todos ocupados/rate{Style.RESET_ALL}")

            elapsed = time.time() - t0
            print(f"{Fore.CYAN}[i] rodada {rodada} fim em {elapsed:.1f}s — hits:{hits_total} ocupados:{ocupado_count} rate:{rate_count} falsos filtrados:{falso_count}{Style.RESET_ALL}")

            rodadas_desde_save += 1
            # salva a cada 3 rodadas ou se teve hit/rate alto
            if rodadas_desde_save >= 3 or candidatos or rate_count > 5:
                save_seen(seen)
                save_cache(cache)
                rodadas_desde_save = 0
            if len(seen) > 12000:
                seen = set(sorted(seen)[-6000:])
                save_seen(seen)
                print(f"{Fore.YELLOW}[i] seen podado pra 6000{Style.RESET_ALL}")

            # modo --once: faz 1 rodada e sai (GitHub Actions)
            if once:
                save_seen(seen)
                save_cache(cache)
                print(f"{Fore.MAGENTA}--once: 1 rodada concluída. hits: {hits_total} | seen: {len(seen)}{Style.RESET_ALL}")
                return

            espera = intervalo + random.uniform(-jitter, jitter)
            if rate_count > total * 0.25:
                espera += 8
                print(f"{Fore.YELLOW}[!] muito rate ({rate_count}/{total}), backoff +8s{Style.RESET_ALL}")
            elif rate_count > 5:
                espera += 4

            print(f"{Fore.CYAN}[i] aguardando {espera:.1f}s...\n{Style.RESET_ALL}")
            time.sleep(max(3, espera))

    except KeyboardInterrupt:
        save_seen(seen)
        save_cache(cache)
        print(f"\n{Fore.MAGENTA}parado. hits: {hits_total} | seen: {len(seen)}{Style.RESET_ALL}")

if __name__ == "__main__":
    main()
