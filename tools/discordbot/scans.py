"""Who scanned it first, and how it's moved since: shared by the $TICKER cards (tickers.py) and the contract-address
cards (dex.py).

Every card shows "Scanned by <name>" (with their avatar) at the top. The first time anything is scanned in a server,
the scanner, the price and the time are saved (scans.json, next to the bot). Every later card for the same thing, by
anyone, adds a "Since first scan" field: the change in price since then, who called it first and when, e.g.
"▲ +42.1% (1.42x) · first scanned by Sam 3 days ago at $0.0012". The first scan stays the reference for good.
"""
import json, os, time

HERE = os.path.dirname(os.path.abspath(__file__))
FILE = os.path.join(HERE, "scans.json")
_data = None


def _load():
    global _data
    if _data is None:
        try:
            with open(FILE) as f: _data = json.load(f)
        except FileNotFoundError: _data = {}
        except Exception as e:
            print(f"[scans] can't read {FILE}: {e}"); _data = {}
    return _data


def _save():
    try:
        tmp = FILE + ".tmp"
        with open(tmp, "w") as f: json.dump(_data, f, separators=(",", ":"))
        os.replace(tmp, FILE)
    except Exception as e: print(f"[scans] can't save: {e}")


def note(guild_id, key, user_id, name, price):
    """The first scan of `key` in this server ({by, uid, price, t}), or None if this is the first (it's saved now)."""
    d = _load()
    k = f"{guild_id}:{key}"
    first = d.get(k)
    if first: return first
    if price is not None:
        d[k] = {"by": name[:40], "uid": str(user_id), "price": price, "t": int(time.time())}
        _save()
    return None


def since(first, price, fmt):
    """The 'Since first scan' line (no discord imports, so it can be tested alone)."""
    when = f"<t:{first['t']}:R>"
    who = first["by"]
    base = f"first scanned by **{who}** {when} at {fmt(first['price'])}"
    p0 = first.get("price")
    if not p0 or price is None: return base
    pct = (price - p0) / p0 * 100
    arrow = "▲" if pct >= 0 else "▼"
    mult = price / p0
    x = f" ({mult:,.2f}x)" if mult >= 2 or mult <= 0.5 else ""
    return f"{arrow} **{pct:+,.1f}%**{x} · {base}"


def decorate(em, message, key, price, fmt):
    """Add the scanner and, if someone scanned it before, the change since then, to a discord.Embed."""
    import discord
    user = message.author
    name = getattr(user, "display_name", None) or user.name
    em.set_author(name=f"Scanned by {name}", icon_url=user.display_avatar.url if user.display_avatar else None)
    try:
        first = note(message.guild.id if message.guild else 0, key, user.id, discord.utils.escape_markdown(name), price)
    except Exception as e:
        print(f"[scans] {key}: {e}"); return
    if first: em.add_field(name="Since first scan", value=since(first, price, fmt), inline=False)
