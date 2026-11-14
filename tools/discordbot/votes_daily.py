"""Daily vote post for the Crispy Discord bot, and /vote.

Just after midnight UTC (when minecraftservers.org and most server lists start a new vote day) Yoink posts one card in
the general chat: the vote links (the featured site first, with its bonus), where we stand on minecraftservers.org this
month and how many votes the first page of its Anarchy list needs, and this month's top voters. The previous day's
card is deleted, so there's only ever one. /vote shows the same card to whoever asks.

Data: the lobby plugin's own files on this machine (CrispyLobby config.yml for the links, votes.json for the voters),
and two public minecraftservers.org pages read once per card. Nothing here gives or changes votes.
"""
import asyncio, datetime, json, os, re, time
from zoneinfo import ZoneInfo
import aiohttp

HERE = os.path.dirname(os.path.abspath(__file__))
STATE = os.path.join(HERE, "votes_daily.json")
LOBBY = "/AMPStorage/.ampdata/instances/CrispyLobby01/Minecraft/plugins/CrispyLobby/"
CHANNEL_ID = 1564294972696563722   # 💬General-Chat (not bridged to the game)
DAILY_POST = False   # the midnight card is off for now (2026-11-14); /vote still works
MSO_ID = 587166
UA = {"User-Agent": "Mozilla/5.0 (compatible; crispy-bot/1.0)"}
LINK = re.compile(r'-\s*\{name:\s*([^,]+?),\s*url:\s*"([^"]+)"([^}]*)\}')


def links():
    """[(name, url, featured)] from the lobby's vote config, featured first."""
    try: s = open(LOBBY + "config.yml", encoding="utf-8").read()
    except OSError: return [], 0
    out = [(m.group(1).strip(), m.group(2), "featured: true" in m.group(3)) for m in LINK.finditer(s) if "CHANGE_ME" not in m.group(2)]
    bonus = re.search(r"^\s*featured-bonus:\s*(\d+)", s, re.M)
    return sorted(out, key=lambda l: not l[2]), int(bonus.group(1)) if bonus else 0


def top_voters(n=5):
    month = datetime.datetime.now(ZoneInfo("America/Chicago")).strftime("%Y-%m")   # the plugin's month
    try: data = json.load(open(LOBBY + "votes.json", encoding="utf-8"))
    except (OSError, ValueError): return [], {}
    rows = [(pd.get("name") or k, (pd.get("months") or {}).get(month, 0)) for k, pd in data.items()]
    rows = sorted([r for r in rows if r[1] > 0], key=lambda r: -r[1])[:n]
    today = datetime.datetime.now(datetime.timezone.utc).date()
    alive = {str(today), str(today - datetime.timedelta(days=1))}
    streaks = sorted([(pd.get("name") or k, pd.get("streak", 0)) for k, pd in data.items() if pd.get("lastDay") in alive and pd.get("streak", 0) >= 2],
                     key=lambda r: -r[1])[:3]
    return rows, streaks


def _text(html):
    import html as h
    return re.sub(r"\s+", " ", h.unescape(re.sub(r"<[^>]+>", " ", html)))


async def mso_standing(session):
    """(our rank, our votes, votes of the last server on page 1 of the Anarchy list) or Nones."""
    async def page(url):
        async with session.get(url, headers=UA, timeout=aiohttp.ClientTimeout(total=15)) as r:
            return await r.text() if r.status == 200 else ""
    try:
        t = _text(await page(f"https://minecraftservers.org/server/{MSO_ID}"))
        rank, votes = re.search(r"Rank ([\d,]+)", t), re.search(r"Votes ([\d,]+)", t)
        ids = re.findall(r'href="/server/(\d+)"', await page("https://minecraftservers.org/type/anarchy"))
        need = None
        if ids:
            last = _text(await page(f"https://minecraftservers.org/server/{ids[-1]}"))
            v = re.search(r"Votes ([\d,]+)", last)
            need = int(v.group(1).replace(",", "")) if v else None
        num = lambda m: int(m.group(1).replace(",", "")) if m else None
        return num(rank), num(votes), need
    except Exception as e:
        print(f"[votes] minecraftservers.org: {type(e).__name__}: {e}")
        return None, None, None


async def card(discord):
    ls, bonus = links()
    async with aiohttp.ClientSession() as session:
        rank, votes, need = await mso_standing(session)
    em = discord.Embed(title="🗳️ New vote day: vote for Crispy!", color=0xF53EDF,
                       description="Votes reset at midnight UTC. Every vote is a **reward on the server you pick** plus "
                                   "**points for tags and colours**. Vote on several sites for several rewards, and every "
                                   "day for a **streak bonus**. Use your exact Minecraft name.")
    feat = [l for l in ls if l[2]]
    if feat:
        em.add_field(name="⭐ Start here", inline=False,
                     value=f"**[{feat[0][0]}]({feat[0][1]})**" + (f"  ·  +{bonus} bonus point" + ("s" if bonus != 1 else "") if bonus else ""))
    others = [l for l in ls if not l[2]]
    if others: em.add_field(name="More sites, more rewards", inline=False, value="  ·  ".join(f"[{n}]({u})" for n, u, _ in others)[:1024])
    if rank and votes is not None:
        line = f"Rank **#{rank:,}** with **{votes}** vote{'s' if votes != 1 else ''} this month."
        if need is not None and votes < need: line += f"\n**{need - votes + 1}** more puts us on page 1 of its Anarchy list."
        elif need is not None: line += "\nWe're on page 1 of its Anarchy list. Keep it there!"
        em.add_field(name="Us on MinecraftServers.org", value=line, inline=False)
    rows, streaks = top_voters()
    if rows: em.add_field(name="Top voters this month", value="\n".join(f"**{i + 1}.** {n.replace('_', chr(92) + '_')} · {v}" for i, (n, v) in enumerate(rows)), inline=True)
    if streaks: em.add_field(name="Longest streaks", value="\n".join(f"🔥 {n.replace('_', chr(92) + '_')} · {s} days" for n, s in streaks), inline=True)
    em.set_footer(text="In game: /vote to claim rewards and see which sites you've done today")
    return em


def _load():
    try: return json.load(open(STATE))
    except (OSError, ValueError): return {}


def _save(d):
    try: json.dump(d, open(STATE, "w"))
    except OSError as e: print(f"[votes] can't save state: {e}")


async def daily(bot, discord):
    await bot.wait_until_ready()
    while True:
        now = datetime.datetime.now(datetime.timezone.utc)
        nxt = (now + datetime.timedelta(days=1)).replace(hour=0, minute=3, second=0, microsecond=0)
        if now.hour == 0 and now.minute < 3: nxt = now.replace(minute=3, second=0, microsecond=0)
        await asyncio.sleep((nxt - now).total_seconds())
        st = _load()
        if st.get("day") == str(nxt.date()): continue   # already posted today (restart around midnight)
        try:
            ch = bot.get_channel(CHANNEL_ID) or await bot.fetch_channel(CHANNEL_ID)
            if st.get("message"):
                try: await (await ch.fetch_message(st["message"])).delete()
                except Exception: pass
            msg = await ch.send(embed=await card(discord))
            _save({"day": str(nxt.date()), "message": msg.id})
        except Exception as e:
            print(f"[votes] daily post failed: {type(e).__name__}: {e}")
        await asyncio.sleep(60)


def register(bot, discord, app_commands):
    orig = bot.setup_hook

    async def hook():
        await orig()
        if DAILY_POST: asyncio.create_task(daily(bot, discord))
    bot.setup_hook = hook

    @bot.tree.command(name="vote", description="Vote for Crispy: the vote links, our list ranking and top voters")
    async def vote_cmd(interaction: discord.Interaction):
        await interaction.response.defer()
        await interaction.followup.send(embed=await card(discord))
