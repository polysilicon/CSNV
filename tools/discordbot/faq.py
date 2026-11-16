"""/ask for the Crispy Discord bot: answers about the servers, from the website's FAQ, without a language model.

Where answers come from
- The website. Every page in www.crispyanarchy.net's sitemap is read every REFRESH seconds and each FAQPage block in
  its structured data (the /faq/ page, the mode pages' question sections) becomes an entry: question, answer, page.
  So a question added to the site (marketing/site/build.py) and deployed is one Yoink can answer after the next
  refresh (or /askadmin reload). The last good copy is kept in faq_site.json, so a site outage never empties /ask.
- faq_extra.toml next to this file: bot-only entries (bot features, small talk, Crispymon), live entries filled in
  with real data (who's online, your votes, your link), and extra phrasings for website questions.

How a question is matched (no language model, nothing leaves the machine)
- Every entry is indexed by its question, its extra phrasings and its answer.
- Meaning: a small sentence-embedding model (fastembed + BAAI/bge-small-en-v1.5, ~130 MB, CPU, a few ms a question)
  scores how close the question is to each phrasing (2 threads, ~260 MB of RAM with the bot), so "do I lose my stuff if someone kills me at the market" finds
  the market answer with no words in common. If fastembed isn't installed, matching falls back to words only.
- Words: a keyword score (BM25-style, with a small synonym list for game slang) for exact terms the model can blur
  ("uno", "2b2t", "$btc").
- The two are blended; above ANSWER the best entry is the answer, between SUGGEST and ANSWER Yoink answers with its
  best guess and offers the next ones, below SUGGEST it says it doesn't know and points to tickets. Every question
  that isn't answered confidently goes to faq_misses.jsonl, so new entries can be written for what people really ask.

Where it works: /ask in Discord, mentioning @Yoink with a question, "!ask <question>" in Discord, and "!ask
<question>" in game chat on any bridged server (answered to that player only, by tellraw).
Staff: /askadmin reload | status | misses | test <question>.
"""
import asyncio, datetime, html, json, math, os, re, time, tomllib
import aiohttp

HERE = os.path.dirname(os.path.abspath(__file__))
SITE = "https://www.crispyanarchy.net"
EXTRA = os.path.join(HERE, "faq_extra.toml")
CACHE = os.path.join(HERE, "faq_site.json")
MISSES = os.path.join(HERE, "faq_misses.jsonl")
LOBBY = "/AMPStorage/.ampdata/instances/CrispyLobby01/Minecraft/plugins/CrispyLobby/"
REFRESH = 6 * 3600
ANSWER, SUGGEST = 0.55, 0.45     # blended score thresholds (tuned on faq_tests.txt)
EMB_W = 0.8                      # weight of the meaning score against the keyword score
COOLDOWN = 4                     # seconds between questions from one person
GAME_MAX = 230                   # characters of an answer shown in game chat
MODEL = "BAAI/bge-small-en-v1.5"
UA = {"User-Agent": "Mozilla/5.0 (compatible; crispy-bot/1.0)"}
COLOR = 0xF39C12

STOP = set("a an the is are am was be do does did i me my you your u ur we our it its to of in on at for and or "
           "can could would should will how what whats what's where when who why which there this that with from "
           "get got have has please pls plz any some just about yoink hey so if im i'm".split())
SYN = {"ip": "address", "addy": "address", "adress": "address", "connect": "join", "rn": "now", "tp": "teleport",
       "tpa": "teleport", "dc": "discord", "sb": "skyblock", "mv": "multiverse", "ez": "extraction", "pts": "points",
       "coop": "co-op", "friends": "friend", "mates": "friend", "items": "item", "votes": "vote", "voting": "vote",
       "voted": "vote", "rewards": "reward", "linking": "link", "linked": "link", "colour": "color", "colours": "color",
       "colors": "color", "tags": "tag", "servers": "server", "modes": "mode", "gamemode": "mode", "mobile": "phone",
       "pe": "bedrock", "mcpe": "bedrock", "console": "bedrock", "xbox": "bedrock", "switch": "bedrock",
       "ps4": "bedrock", "ps5": "bedrock", "playstation": "bedrock", "hacks": "hack", "hacking": "hack",
       "hacker": "hack", "cheats": "hack", "griefing": "grief", "rules": "rule", "players": "player",
       "online": "online", "dead": "online", "killed": "die", "dies": "die", "died": "die", "death": "die"}

entries = []          # {id, q, a, alts, url, live, src}
_index = []           # (entry number, text) per indexed phrasing
_vecs = None          # embeddings of _index texts (numpy array) or None
_model = None
_lex = None           # keyword index
_loaded_at = 0
_orphans = []         # [alts] keys that match no website question
_last_q = {}
_site_ok = None       # (time, number of site questions) of the last successful site read


# ------------------------------------------------------------------------------------------------ text
def words(text):
    out = []
    for w in re.findall(r"[a-z0-9$/][a-z0-9'$/.-]*", (text or "").lower()):
        w = w.strip(".'-")
        w = SYN.get(w, w)
        if w and w not in STOP:
            out.append(w)
    return out


class Lex:
    """BM25 over each entry's question + phrasings (weighted) and answer."""
    def __init__(self, docs):
        self.docs = [dict() for _ in docs]
        for d, (strong, weak) in zip(self.docs, docs):
            for w in words(strong): d[w] = d.get(w, 0) + 2
            for w in words(weak): d[w] = d.get(w, 0) + 1
        n = len(docs) or 1
        df = {}
        for d in self.docs:
            for w in d: df[w] = df.get(w, 0) + 1
        self.idf = {w: math.log(1 + (n - c + 0.5) / (c + 0.5)) for w, c in df.items()}
        self.avg = sum(sum(d.values()) for d in self.docs) / n or 1

    def scores(self, query):
        q = set(words(query))
        if not q: return [0.0] * len(self.docs)
        out = []
        for d in self.docs:
            ln, s = sum(d.values()), 0.0
            for w in q:
                f = d.get(w, 0)
                if f: s += self.idf.get(w, 0) * f * 2.2 / (f + 1.2 * (0.25 + 0.75 * ln / self.avg))
            out.append(s)
        # normalise: share of the query's total possible weight that matched (0..1)
        best = sum(self.idf.get(w, 1.5) for w in q) * 1.6 or 1
        return [min(1.0, s / best) for s in out]


# ------------------------------------------------------------------------------------------------ loading
def _site_from_html(page, url):
    qas = []
    for block in re.findall(r'<script type="application/ld\+json">(.*?)</script>', page, re.S):
        try: data = json.loads(block)
        except ValueError: continue
        for node in (data.get("@graph") or [data]) if isinstance(data, dict) else data:
            if isinstance(node, dict) and node.get("@type") == "FAQPage":
                for qa in node.get("mainEntity") or []:
                    q = (qa.get("name") or "").strip()
                    a = ((qa.get("acceptedAnswer") or {}).get("text") or "").strip()
                    if q and a: qas.append({"q": html.unescape(q), "a": html.unescape(a), "url": url})
    return qas


async def fetch_site():
    """All FAQ questions on the site, /faq/ first (it wins duplicates). Raises if the site can't be read."""
    timeout = aiohttp.ClientTimeout(total=20)
    async with aiohttp.ClientSession(headers=UA, timeout=timeout) as s:
        async with s.get(SITE + "/sitemap.xml") as r:
            r.raise_for_status()
            urls = re.findall(r"<loc>([^<]+)</loc>", await r.text())
        urls = [u for u in urls if u.startswith(SITE)]
        urls.sort(key=lambda u: (not u.rstrip("/").endswith("/faq"), "/news/" in u, u))
        out, seen = [], set()
        for u in urls:
            if "/news/" in u: continue   # news posts don't carry FAQs
            try:
                async with s.get(u) as r:
                    if r.status != 200: continue
                    page = await r.text()
            except aiohttp.ClientError:
                continue
            for qa in _site_from_html(page, u):
                k = qa["q"].lower()
                if k not in seen:
                    seen.add(k); out.append(qa)
    if not out: raise ValueError("no FAQ questions found on the site")
    return out


def _load_extra():
    try:
        with open(EXTRA, "rb") as f: return tomllib.load(f)
    except (OSError, tomllib.TOMLDecodeError) as e:
        print(f"[faq] {EXTRA}: {e}")
        return {}


def _build(site):
    global entries, _index, _vecs, _lex, _loaded_at, _orphans
    extra = _load_extra()
    alts = {k.lower(): v for k, v in (extra.get("alts") or {}).items()}
    new = []
    for i, qa in enumerate(site):
        new.append({"id": f"site{i}", "q": qa["q"], "a": qa["a"], "url": qa.get("url"), "live": None, "src": "site",
                    "alts": list(alts.get(qa["q"].lower(), []))})
    for e in extra.get("entry") or []:
        if e.get("q") and (e.get("a") or e.get("live")):
            new.append({"id": e.get("id") or e["q"], "q": e["q"], "a": e.get("a", ""), "url": e.get("url"),
                        "live": e.get("live"), "src": "extra", "alts": list(e.get("alts") or [])})
    known = {qa["q"].lower() for qa in site}
    _orphans = [k for k in (extra.get("alts") or {}) if k.lower() not in known]
    index = []
    for n, e in enumerate(new):
        for t in [e["q"]] + e["alts"]: index.append((n, t, 1.0))
        if e["src"] == "site": index.append((n, e["a"][:300], 0.93))   # the answer counts, a little less
    vecs = None
    if _model is not None:
        try:
            import numpy as np
            vecs = np.array(list(_model.embed([t for _, t, _ in index], batch_size=8)))   # small batches: ~260 MB in all, not ~800
        except Exception as ex:
            print(f"[faq] embedding failed, words only: {ex}")
    lex = Lex([(" ".join([e["q"]] + e["alts"]), e["a"]) for e in new])
    entries, _index, _vecs, _lex, _loaded_at = new, index, vecs, lex, time.time()
    print(f"[faq] {len(new)} entries ({len(site)} from the site), {len(index)} phrasings, model {'on' if vecs is not None else 'off'}")


def _load_model():
    global _model
    try:
        from fastembed import TextEmbedding
        _model = TextEmbedding(MODEL, cache_dir=os.path.join(HERE, ".fastembed"), threads=2)   # 2 threads: never competes with the game servers
    except Exception as e:
        _model = None
        print(f"[faq] no embedding model ({type(e).__name__}: {e}); matching by words only")


def _cached_site():
    try:
        with open(CACHE, encoding="utf-8") as f: return json.load(f)
    except (OSError, ValueError):
        return []


async def reload(fetch=True):
    """Re-read the site (unless fetch=False) and faq_extra.toml. Returns (site questions, error or None)."""
    global _site_ok
    err, site = None, None
    if fetch:
        try:
            site = await fetch_site()
            with open(CACHE, "w", encoding="utf-8") as f: json.dump(site, f, ensure_ascii=False, indent=1)
            _site_ok = (time.time(), len(site))
        except Exception as e:
            err = f"{type(e).__name__}: {e}"
            print(f"[faq] site read failed, using the saved copy: {err}")
    if site is None: site = _cached_site()
    await asyncio.to_thread(_build, site)
    return len(site), err


# ------------------------------------------------------------------------------------------------ matching
def _rank(question):
    """[(score, entry number)] best first."""
    if not entries: return []
    lex = _lex.scores(question)
    emb = [0.0] * len(entries)
    if _vecs is not None and _model is not None:
        import numpy as np
        q = np.array(list(_model.embed([question])))[0]
        sims = _vecs @ q / (np.linalg.norm(_vecs, axis=1) * np.linalg.norm(q) + 1e-9)
        for (n, _, w), s in zip(_index, sims):
            s = float(s) * w
            if s > emb[n]: emb[n] = s
        # bge similarities sit roughly in 0.45 (unrelated) .. 0.95 (same question); stretch that to 0..1
        emb = [max(0.0, min(1.0, (s - 0.45) / 0.5)) for s in emb]
        score = [EMB_W * e + (1 - EMB_W) * l for e, l in zip(emb, lex)]
    else:
        score = lex
    return sorted(((s, n) for n, s in enumerate(score)), reverse=True)


def match(question):
    """(entry or None, confidence, [other likely entries])."""
    ranked = _rank(question)
    if not ranked: return None, 0.0, []
    best_s, best_n = ranked[0]
    others = [entries[n] for s, n in ranked[1:4] if s >= max(SUGGEST, best_s - 0.08) and entries[n]["q"] != entries[best_n]["q"]][:2]
    if best_s < SUGGEST: return None, best_s, [entries[n] for s, n in ranked[:3] if s >= SUGGEST * 0.75]
    return entries[best_n], best_s, others


def log_miss(where, who, question, best, score):
    try:
        with open(MISSES, "a", encoding="utf-8") as f:
            f.write(json.dumps({"t": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"), "where": where,
                                "who": who, "q": question[:300], "best": best, "score": round(score, 3)}, ensure_ascii=False) + "\n")
    except OSError:
        pass


# ------------------------------------------------------------------------------------------------ live answers
def _votes_for(name):
    try:
        with open(LOBBY + "votes.json", encoding="utf-8") as f: data = json.load(f)
    except (OSError, ValueError):
        return None
    pd = data.get((name or "").lower().lstrip(".")) or data.get((name or "").lower())
    if pd is None:
        pd = next((v for v in data.values() if (v.get("name") or "").lower() == (name or "").lower()), None)
    return pd


def _votes_text(name):
    pd = _votes_for(name)
    if not pd:
        return f"I can't find any votes for **{name}** yet. Vote on the sites in `/vote` with that exact name and they'll show up here."
    today = datetime.datetime.now(datetime.timezone.utc).date()
    streak = pd.get("streak", 0) if pd.get("lastDay") in (str(today), str(today - datetime.timedelta(days=1))) else 0
    voted = len(pd.get("voted") or []) if pd.get("lastDay") == str(today) else 0
    lines = [f"**{pd.get('name') or name}**: {pd.get('points', 0)} vote points, {pd.get('unclaimed', 0)} reward(s) waiting to be sent "
             f"(type `/vote` in game), {pd.get('total', 0)} votes in total.",
             f"Today: {voted} site(s) voted · streak {streak} day(s) (best {pd.get('best', 0)}). A new vote day starts at midnight UTC."]
    pending = {k: v for k, v in (pd.get("pending") or {}).items() if v}
    if pending:
        lines.append("Sent and waiting for you to join: " + ", ".join(f"{v} on {k.title()}" for k, v in pending.items()) + ".")
    return "\n".join(lines)


async def live_answer(kind, ctx):
    """ctx: bot, bridges, list_players, mc_name (linked or in-game name or None), discord (bool)."""
    if kind == "online":
        lines = []
        for key, cfg in ctx["bridges"].items():
            try:
                names, _ = await ctx["list_players"](cfg)
                lines.append(f"**{cfg['name']}** ({len(names)}): " + (", ".join(n.lstrip('.') for n in names[:20]) + (" …" if len(names) > 20 else "") if names else "nobody right now"))
            except Exception:
                lines.append(f"**{cfg['name']}**: offline or restarting")
        return "\n".join(lines) or "No servers are bridged."
    if kind == "myvotes":
        if not ctx.get("mc_name"):
            return "Link your Minecraft account first (`/link` with your exact name while you're online in game), then ask again. Or type `/vote` in game to see your points."
        return _votes_text(ctx["mc_name"])
    if kind == "mylink":
        if not ctx.get("discord"):
            return "Ask that in Discord (I can only see links from there): `/link` with your exact name starts it."
        n = ctx.get("mc_name")
        return f"Yes: your Discord is linked to **{n}**. `/unlink` removes it." if n else \
            "Not yet. Join any Crispy server, then type `/link` with your exact Minecraft name in Discord and `/verify` the code I send you in game."
    if kind == "help":
        return ("Ask me anything about the Crispy servers in plain words: the IP, versions, Bedrock, rules, voting and rewards, "
                "Discord linking, Skyblock, Anarchy, Multiverse, Extraction Zone and more. I can also tell you **who's online** and "
                "**your vote points** (once your account is linked).\n"
                "Use `/ask`, mention me with a question, or type `!ask <question>` here or in game chat.\n"
                "Also: `$BTC`-style price cards, contract-address token cards, `/newpairs`, `/polymarket`, `/vote`, `/online`, `/link`.")
    return None


# ------------------------------------------------------------------------------------------------ replies
async def answer(question, ctx):
    """(entry or None, text, confidence, others)."""
    if time.time() - _loaded_at > REFRESH: asyncio.create_task(reload())
    e, score, others = await asyncio.to_thread(match, question)
    if e is None: return None, None, score, others
    text = (await live_answer(e["live"], ctx)) if e.get("live") else e["a"]
    return e, text or e["a"], score, others


def embed(discord, question, e, text, score, others):
    if e is None:
        em = discord.Embed(color=0x95A5A6, title="I'm not sure about that one",
                           description="I don't have an answer for that yet, so I've noted the question for staff. "
                                       "Try asking another way, check www.crispyanarchy.net/faq/, or open a ticket in the Discord.")
        if others: em.add_field(name="Maybe one of these?", value="\n".join(f"• {o['q']}" for o in others), inline=False)
        return em
    em = discord.Embed(color=COLOR, title=e["q"][:256], description=text[:4000], url=e.get("url") or None)
    if score < ANSWER:
        em.set_author(name="My best guess:")
    if others:
        em.add_field(name="Related", value="\n".join(f"• {o['q']}" for o in others), inline=False)
    em.set_footer(text=("From www.crispyanarchy.net" if e["src"] == "site" else "Yoink") + " · /ask anything about the servers")
    return em


def strip_md(text):
    text = re.sub(r"\*\*|__|`", "", text)
    return re.sub(r"<#\d+>", "the Discord", text)


def game_json(question, e, text, score):
    if e is None:
        parts = [{"text": "[Yoink] ", "color": "gold", "bold": True},
                 {"text": "I don't know that one yet (noted for staff). Try other words, or see crispyanarchy.net/faq", "color": "gray", "bold": False}]
        return json.dumps({"text": "", "extra": parts})
    body = strip_md(text).replace("\n", " ")
    short = body if len(body) <= GAME_MAX else body[:GAME_MAX].rsplit(" ", 1)[0] + "…"
    parts = [{"text": "[Yoink] ", "color": "gold", "bold": True},
             {"text": ("Best guess: " if score < ANSWER else ""), "color": "yellow", "bold": False},
             {"text": short, "color": "white", "bold": False}]
    root = {"text": "", "extra": parts}
    if e.get("url") and (len(body) > GAME_MAX or True):
        parts.append({"text": " [more]" if len(body) > GAME_MAX else " [link]", "color": "aqua", "bold": False})
        root.update({"clickEvent": {"action": "open_url", "value": e["url"]}, "click_event": {"action": "open_url", "url": e["url"]},
                     "hoverEvent": {"action": "show_text", "contents": body[:600]}, "hover_event": {"action": "show_text", "value": body[:600]}})
    return json.dumps(root, ensure_ascii=False)


def _cool(key):
    now = time.monotonic()
    if now - _last_q.get(key, 0) < COOLDOWN: return True
    _last_q[key] = now
    return False


ASK_RE = re.compile(r"^\s*!ask\b[\s:,]*(.*)$", re.I | re.S)


def register(bot, discord, app_commands, bridges, list_players, rcon):
    """Wire /ask, /askadmin, @mentions and !ask (Discord). Game chat calls game() from the bridge."""
    ctx_base = {"bot": bot, "bridges": bridges, "list_players": list_players}
    orig_hook, orig_extras = bot.setup_hook, bot.extras

    async def hook():
        await orig_hook()
        await asyncio.to_thread(_load_model)
        await reload(fetch=False)                    # the saved copy first, so /ask works straight away
        async def refresher():
            while True:
                await reload()
                await asyncio.sleep(REFRESH)
        asyncio.create_task(refresher())
    bot.setup_hook = hook

    def dctx(user):
        return dict(ctx_base, mc_name=bot.links.get(str(user.id)), discord=True)

    async def ask_message(message, question):
        if not question.strip():
            return await message.reply("Ask me something after it, like `!ask how do I vote`.", mention_author=False)
        if _cool(("d", message.author.id)): return
        e, text, score, others = await answer(question, dctx(message.author))
        if e is None or score < ANSWER: log_miss("discord", message.author.name, question, e["q"] if e else (others[0]["q"] if others else None), score)
        await message.reply(embed=embed(discord, question, e, text, score, others), mention_author=False)

    async def extras(message):
        await orig_extras(message)
        try:
            content = message.content or ""
            m = ASK_RE.match(content)
            if m:
                return await ask_message(message, m.group(1))
            if bot.user and re.search(rf"<@!?{bot.user.id}>", content):
                question = re.sub(rf"<@!?{bot.user.id}>", "", content).strip()
                if question: await ask_message(message, question)
        except Exception as ex:
            print(f"[faq] message failed: {type(ex).__name__}: {ex}")
    bot.extras = extras

    @bot.tree.command(name="ask", description="Ask Yoink anything about the Crispy servers")
    @app_commands.describe(question="Your question, in your own words (e.g. how do I vote?)")
    async def ask_cmd(interaction: discord.Interaction, question: app_commands.Range[str, 1, 300]):
        if _cool(("d", interaction.user.id)):
            return await interaction.response.send_message("One question every few seconds, please!", ephemeral=True)
        await interaction.response.defer()
        e, text, score, others = await answer(question, dctx(interaction.user))
        if e is None or score < ANSWER: log_miss("discord", interaction.user.name, question, e["q"] if e else None, score)
        em = embed(discord, question, e, text, score, others)
        em.description = f"> {discord.utils.escape_markdown(question)[:200]}\n\n" + (em.description or "")
        await interaction.followup.send(embed=em)

    admin = app_commands.Group(name="askadmin", description="Staff: Yoink's /ask answers",
                               default_permissions=discord.Permissions(administrator=True))

    @admin.command(name="reload", description="Re-read the website FAQ and faq_extra.toml now")
    async def a_reload(interaction: discord.Interaction):
        if not bot.is_staff(interaction.user): return await interaction.response.send_message("Staff only.", ephemeral=True)
        await interaction.response.defer(ephemeral=True)
        n, err = await reload()
        await interaction.followup.send(f"Loaded {len(entries)} answers ({n} from the website)." + (f"\n⚠️ Website read failed, kept the saved copy: {err}" if err else "")
                                        + (f"\n⚠️ Phrasings in faq_extra.toml for questions the site no longer has: {', '.join(_orphans)[:1500]}" if _orphans else ""))

    @admin.command(name="status", description="What /ask knows and how it's matching")
    async def a_status(interaction: discord.Interaction):
        if not bot.is_staff(interaction.user): return await interaction.response.send_message("Staff only.", ephemeral=True)
        site = sum(1 for e in entries if e["src"] == "site")
        ok = f"<t:{int(_site_ok[0])}:R>" if _site_ok else "not this run (using the saved copy)"
        try: misses = sum(1 for _ in open(MISSES, encoding="utf-8"))
        except OSError: misses = 0
        await interaction.response.send_message(
            f"**{len(entries)}** answers: {site} from the website (last read {ok}), {len(entries) - site} from faq_extra.toml.\n"
            f"Matching: {'meaning + words (' + MODEL + ')' if _vecs is not None else 'words only (no embedding model)'}.\n"
            f"Unanswered questions logged: {misses} (`/askadmin misses`)."
            + (f"\n⚠️ Orphaned phrasings: {', '.join(_orphans)[:1500]}" if _orphans else ""), ephemeral=True)

    @admin.command(name="misses", description="The latest questions /ask couldn't answer confidently")
    async def a_misses(interaction: discord.Interaction):
        if not bot.is_staff(interaction.user): return await interaction.response.send_message("Staff only.", ephemeral=True)
        try: rows = [json.loads(l) for l in open(MISSES, encoding="utf-8")][-25:]
        except (OSError, ValueError): rows = []
        text = "\n".join(f"`{r['score']:.2f}` {discord.utils.escape_markdown(r['q'])[:120]}" + (f" → *{r['best']}*" if r.get("best") else "") for r in reversed(rows))
        await interaction.response.send_message((text or "Nothing logged yet.")[:1990], ephemeral=True)

    @admin.command(name="test", description="Show how a question would be matched")
    async def a_test(interaction: discord.Interaction, question: str):
        if not bot.is_staff(interaction.user): return await interaction.response.send_message("Staff only.", ephemeral=True)
        ranked = await asyncio.to_thread(_rank, question)
        text = "\n".join(f"`{s:.2f}` {entries[n]['q']}" for s, n in ranked[:5])
        await interaction.response.send_message(f"Answer at ≥ {ANSWER}, best guess at ≥ {SUGGEST}.\n{text}"[:1990], ephemeral=True)

    bot.tree.add_command(admin)


async def game(bot, cfg, rcon, list_players, bridges, player, text):
    """From the chat bridge: '!ask <question>' in game chat -> the answer, to that player only."""
    m = ASK_RE.match(text or "")
    if not m: return
    question = m.group(1).strip()
    target = player if re.fullmatch(r"\.?[A-Za-z0-9_]{1,16}", player or "") else None
    if not target or _cool(("g", player.lower())): return
    try:
        if not question:
            await rcon(cfg, "tellraw " + target + " " + json.dumps({"text": "[Yoink] Ask me something after it, like !ask how do I vote", "color": "gray"}))
            return
        mc = player
        e, ans, score, others = await answer(question, {"bot": bot, "bridges": bridges, "list_players": list_players,
                                                         "mc_name": mc, "discord": False})
        if e is None or score < ANSWER: log_miss(f"game:{cfg.get('name')}", player, question, e["q"] if e else None, score)
        await rcon(cfg, "tellraw " + target + " " + game_json(question, e, ans or "", score))
    except Exception as ex:
        print(f"[faq] game {player}: {type(ex).__name__}: {ex}")
