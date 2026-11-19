"""Daily Word for the Crispy Discord bot: picks the lobby's word of the day, and /dailyword shows how it's going.

The game itself is a lobby plugin (dailyword/ in the repo: guess a five-letter word in six tries). This module is its
word supply. Once a minute it checks the date (America/Chicago, like Balatro Craft's daily run); on a new day it picks
a random word nobody has had yet and writes the lobby plugin's word.json ({day, number, word}), plus valid.txt (every
allowed guess) and answers.txt (the plugin's fallback if this bot is ever down).

Word lists (downloaded once, cached next to this file, refreshed monthly):
- answers: common US-English five-letter words with swears removed (first20hours/google-10000-english, no-swears
  list), kept only if they're lowercase words in a spelling dictionary (wooorm/dictionaries en), so no names,
  abbreviations or plurals; minus the bot's censor list and BLOCK; plus MINECRAFT words, picked about 1 day in 5.
- valid guesses: every five-letter English word in dwyl/english-words (~16k), plus all answers.
Used words are kept in dailyword_state.json so the same word never comes back.

/dailyword: today's number and how many have played and solved (never today's word), yesterday's word with its
results, and the longest current streaks, from the plugin's summary.json.
"""
import asyncio, datetime, json, os, random, re, time
from zoneinfo import ZoneInfo
import aiohttp

HERE = os.path.dirname(os.path.abspath(__file__))
LOBBY = "/AMPStorage/.ampdata/instances/CrispyLobby01/Minecraft/plugins/DailyWord/"
STATE = os.path.join(HERE, "dailyword_state.json")
CACHE = os.path.join(HERE, "dailyword_lists.json")
ZONE = ZoneInfo("America/Chicago")
COMMON = "https://raw.githubusercontent.com/first20hours/google-10000-english/master/google-10000-english-usa-no-swears.txt"
DICT = "https://raw.githubusercontent.com/wooorm/dictionaries/main/dictionaries/en/index.dic"
ALL = "https://raw.githubusercontent.com/dwyl/english-words/master/words_alpha.txt"
REFRESH_DAYS = 30
MC_CHANCE = 0.2
# Minecraft words (all ordinary English too, so they're fair guesses for everyone)
MINECRAFT = """torch stone blaze anvil creep spawn craft sword arrow bread brick chest cocoa coral flint glass golem honey
lever llama melon ocean panda sheep skull slime sugar biome chunk fence frost horse magma pearl plank realm shard shell
smelt spore stair trade vines wheat witch ghost steak boots crops flame quest raids mossy cacti beets lapis""".split()
# Never an answer (still fine as a guess): names, brands, slang, fragments and words we'd rather not show everyone.
BLOCK = set("""thong sperm booty spank slave naked daddy latex craps trans tumor rehab fatty gonna gotta kinda wanna
xerox yahoo intel japan dutch welsh roman maria peter randy roger sally terry jenny jimmy billy bobby harry frank belle
inter multi promo specs highs admin login inbox email modem toner condo bible devil drunk dying""".split())
UA = {"User-Agent": "Mozilla/5.0 (compatible; crispy-bot/1.0)"}
WORD = re.compile(r"^[a-z]{5}$")


def _load(path, default):
    try:
        with open(path, encoding="utf-8") as f: return json.load(f)
    except (OSError, ValueError): return default


def _save(path, data):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f: json.dump(data, f, indent=1)
    os.replace(tmp, path)


def _censored():
    try:
        with open(os.path.join(HERE, "censor_words.txt"), encoding="utf-8") as f:
            return {l.strip().lower() for l in f if l.strip() and not l.startswith("#")}
    except OSError:
        return set()


async def _lists():
    """(answers, valid): from the cache, re-downloaded every REFRESH_DAYS (or kept if a download fails)."""
    cache = _load(CACHE, {})
    if cache.get("answers") and time.time() - cache.get("at", 0) < REFRESH_DAYS * 86400:
        return cache["answers"], cache["valid"]
    try:
        async with aiohttp.ClientSession(headers=UA, timeout=aiohttp.ClientTimeout(total=120)) as s:
            async def get(u):
                async with s.get(u) as r:
                    r.raise_for_status(); return await r.text()
            common, dic, allw = await get(COMMON), await get(DICT), await get(ALL)
        five = lambda txt: {w for w in (l.strip().lower() for l in txt.splitlines()) if WORD.match(w)}
        dict_lower = {w for w in (l.split("/")[0].strip() for l in dic.splitlines()) if WORD.match(w)}
        bad = _censored()
        answers = sorted((five(common) & dict_lower) - BLOCK - bad)
        mc = [w for w in MINECRAFT if WORD.match(w) and w not in bad]
        valid = sorted(five(allw) | set(answers) | set(mc))
        cache = {"at": time.time(), "answers": answers, "minecraft": mc, "valid": valid}
        _save(CACHE, cache)
        print(f"[dailyword] word lists: {len(answers)} answers, {len(mc)} Minecraft words, {len(valid)} valid guesses")
    except Exception as e:
        print(f"[dailyword] word list download failed ({type(e).__name__}: {e}); using the cached lists")
        if not cache.get("answers"): raise
    return cache["answers"], cache["valid"]


async def tick():
    """Make sure the lobby has today's word; pick a new one when the day changes."""
    day = datetime.datetime.now(ZONE).date().isoformat()
    st = _load(STATE, {"used": [], "number": 0, "day": None, "word": None})
    cur = _load(LOBBY + "word.json", {})
    if st.get("day") == day and cur.get("day") == day and cur.get("word") == st.get("word"):
        return
    answers, valid = await _lists()
    cache = _load(CACHE, {})
    os.makedirs(LOBBY, exist_ok=True)
    # the guess lists first, so the plugin can check guesses against them as soon as the word arrives
    for name, words in (("valid.txt", valid), ("answers.txt", answers)):
        path = LOBBY + name
        text = "\n".join(words) + "\n"
        try:
            with open(path, encoding="utf-8") as f: same = f.read() == text
        except OSError: same = False
        if not same:
            with open(path + ".tmp", "w", encoding="utf-8") as f: f.write(text)
            os.replace(path + ".tmp", path)
    if st.get("day") != day:   # a new day: a new word
        used = set(st.get("used", []))
        mc = [w for w in cache.get("minecraft", []) if w not in used]
        pool = mc if mc and random.random() < MC_CHANCE else [w for w in answers if w not in used]
        if not pool:   # every word has been used: start over
            used = set(); pool = answers
        word = random.choice(pool)
        st = {"used": sorted(used | {word}), "number": st.get("number", 0) + 1, "day": day, "word": word}
        _save(STATE, st)
        print(f"[dailyword] #{st['number']} for {day} picked")
    _save(LOBBY + "word.json", {"day": day, "number": st["number"], "word": st["word"]})


async def loop():
    await asyncio.sleep(5)
    while True:
        try: await tick()
        except Exception as e: print(f"[dailyword] {type(e).__name__}: {e}")
        await asyncio.sleep(60)


def _bars(dist):
    top = max(dist) or 1
    return "\n".join(f"`{i + 1}` " + ("🟩" * max(1 if n else 0, round(n / top * 8))) + f" {n}" for i, n in enumerate(dist))


def register(bot, discord, app_commands):
    orig = bot.setup_hook

    async def hook():
        await orig()
        asyncio.create_task(loop())
    bot.setup_hook = hook

    @bot.tree.command(name="dailyword", description="Daily Word: today's results, yesterday's word and the longest streaks")
    async def dailyword_cmd(interaction: discord.Interaction):
        s = _load(LOBBY + "summary.json", None)
        if not s:
            return await interaction.response.send_message("Daily Word hasn't started yet.", ephemeral=True)
        t = s.get("today", {})
        em = discord.Embed(color=0x6AAA64, title=f"🟩 Daily Word #{s.get('number')}",
                           description=f"Guess the five-letter word in six tries. Same word for everyone, new one at midnight (Central).\n"
                                       f"**Play in the lobby:** `/word`, or Lobby Minigames in the server selector.")
        em.add_field(name="Today", value=f"{t.get('played', 0)} played · {t.get('solved', 0)} solved" +
                     (f"\n{_bars(t['dist'])}" if t.get("solved") else ""), inline=False)
        y = s.get("yesterday")
        if y and y.get("word"):
            em.add_field(name=f"Yesterday (#{y.get('number')})", value=f"The word was **{y['word'].upper()}**: {y.get('solved', 0)} of {y.get('played', 0)} solved it.", inline=False)
        if s.get("streaks"):
            em.add_field(name="Streaks", value="\n".join(f"🔥 {discord.utils.escape_markdown(x['name'])}: {x['streak']}" for x in s["streaks"]), inline=False)
        await interaction.response.send_message(embed=em)
