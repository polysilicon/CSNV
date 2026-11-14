"""Polymarket cards for the Crispy Discord bot.

- A polymarket.com/event/... link in a message gets a reply card: the question, the odds of each outcome (as a bar
  and a percentage: Polymarket prices are the market's implied probability), volume and end date.
- /polymarket <search> finds the best-matching open market and shows the same card (other matches listed under it).

Data: Polymarket's public Gamma API (no key). Information only, not advice.
"""
import json, re
import aiohttp

API = "https://gamma-api.polymarket.com/"
LINK = re.compile(r"https?://(?:www\.)?polymarket\.com/(?:[a-z]{2}/)?event/([a-z0-9-]+)", re.I)
UA = {"User-Agent": "Mozilla/5.0 (compatible; crispy-bot/1.0)"}
SHOW = 8   # outcomes on a card


async def _get(session, path, **params):
    async with session.get(API + path, params=params, headers=UA, timeout=aiohttp.ClientTimeout(total=10)) as r:
        if r.status != 200: return None
        return await r.json()


async def event(session, slug):
    d = await _get(session, "events", slug=slug)
    return d[0] if d else None


async def search(session, q):
    d = await _get(session, "public-search", q=q, events_status="active", limit_per_type=6)
    return [e for e in (d or {}).get("events", []) if not e.get("closed")]


def _price(m, i=0):
    try: return float(json.loads(m.get("outcomePrices") or "[]")[i])
    except (ValueError, IndexError, TypeError): return None


def bar(p):
    n = round((p or 0) * 10)
    return "█" * n + "░" * (10 - n)


def money(v):
    try: v = float(v)
    except (TypeError, ValueError): return "?"
    return f"${v / 1e6:,.1f}M" if v >= 1e6 else f"${v / 1e3:,.0f}K" if v >= 1e3 else f"${v:,.0f}"


def card(e, others=()):
    """Embed fields for an event, free of discord imports so it can be tested alone."""
    markets = [m for m in e.get("markets", []) if m.get("outcomePrices")]
    open_ms = [m for m in markets if not m.get("closed")] or markets
    lines = []
    if len(open_ms) == 1:   # one question: each of its outcomes (usually Yes / No)
        m = open_ms[0]
        outs = json.loads(m.get("outcomes") or "[]")
        for i, o in enumerate(outs[:SHOW]):
            p = _price(m, i)
            if p is not None: lines.append(f"`{bar(p)}` **{p * 100:.0f}%** {o}")
    else:                    # several: each option's chance of "Yes", likeliest first
        ranked = sorted(open_ms, key=lambda m: -(_price(m) or 0))
        for m in ranked[:SHOW]:
            p = _price(m)
            if p is None: continue
            label = m.get("groupItemTitle") or m.get("question") or "?"
            lines.append(f"`{bar(p)}` **{p * 100:.0f}%** {label}")
        if len(ranked) > SHOW: lines.append(f"…and {len(ranked) - SHOW} more")
    state = "Resolved" if e.get("closed") else "Open"
    fields = [("Volume", money(e.get("volume"))), ("Status", state)]
    if e.get("endDate"): fields.append(("Ends", e["endDate"][:10]))
    if others: fields.append(("Other matches", "\n".join(f"[{o['title'][:70]}](https://polymarket.com/event/{o['slug']})" for o in others[:4])))
    return {"title": e.get("title", "Polymarket")[:250], "url": f"https://polymarket.com/event/{e.get('slug', '')}",
            "description": "\n".join(lines)[:3900] or "No prices yet.", "fields": fields,
            "footer": "Polymarket · prices are the market's implied odds · not advice", "image": e.get("image")}


def embed(discord, data):
    em = discord.Embed(title=data["title"], url=data["url"], description=data["description"], color=0x2E5CFF)
    for n, v in data["fields"]: em.add_field(name=n, value=v, inline=n != "Other matches")
    if data.get("image"): em.set_thumbnail(url=data["image"])
    em.set_footer(text=data["footer"])
    return em


async def reply_links(message, discord):
    slugs = list(dict.fromkeys(m.group(1) for m in LINK.finditer(message.content or "")))[:2]
    if not slugs: return
    async with aiohttp.ClientSession() as session:
        for slug in slugs:
            e = await event(session, slug)
            if e: await message.reply(embed=embed(discord, card(e)), mention_author=False)


def register(bot, discord, app_commands):
    @bot.tree.command(name="polymarket", description="Look up a Polymarket prediction market's odds")
    @app_commands.describe(search="What to look for, e.g. 'bitcoin november' or 'election 2028'")
    async def polymarket_cmd(interaction: discord.Interaction, search: str):
        await interaction.response.defer()
        async with aiohttp.ClientSession() as session:
            found = await globals()["search"](session, search[:100])
            if not found:
                return await interaction.followup.send(f"No open Polymarket market matches \"{search[:100]}\".")
            e = await event(session, found[0]["slug"]) or found[0]
            await interaction.followup.send(embed=embed(discord, card(e, found[1:])))
