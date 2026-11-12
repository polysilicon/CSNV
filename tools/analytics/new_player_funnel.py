#!/usr/bin/env python3
"""New-player funnel and retention for the Crispy network, from the Velocity proxy logs (plus backend logs).

Run ON THE AMP HOST (player data stays there):

    python3 new_player_funnel.py [--days 60] [--exclude lbxd] [--out /root/crispy_analytics] [--names]

Reads
  - test01 (Velocity) logs: every login, server switch, disconnect (with reason), refused login (no names).
  - Anarchy/Vanilla logs from before the proxy existed: a "new" player who had played there before the proxy logs
    start is counted as a returning veteran, not a new player.
  - Lobby log lines for the example sessions (chat and commands in their first visit).
Writes <out>/funnel-<date>.md (real names, stays on the host) and prints the same report with names replaced by
"Player A", "Player B"... unless --names. Standard library only.

Definitions (all times are the server's, UTC)
  visit         sessions less than 30 min apart are one visit (crash/reconnect/server restart is not a "return")
  new player    first visit inside the window, never seen by the proxy before, not a pre-proxy Anarchy/Vanilla player
  chose a mode  reached any server other than the lobby during the first visit
  10 minutes    first visit lasted >= 10 min (lobby time included)
  D1            came back (a new visit) within 48 h of first joining      - counted once 48 h have passed
  D7            played on any day from day 7 to day 13 after first joining - counted once 14 days have passed
  D30           played on any day from day 30 to day 59                   - counted once 60 days have passed
  ever returned any later visit at all
"""
import argparse, collections, datetime as dt, glob, gzip, os, re, statistics, subprocess, sys

I = "/AMPStorage/.ampdata/instances"
PROXY = f"{I}/test01/Minecraft/logs"
LOBBY = f"{I}/CrispyLobby01/Minecraft/logs"
PRE_PROXY = [f"{I}/CrispyAnarchy01/Minecraft/logs", f"{I}/Vanilla01/Minecraft/logs"]
REJOIN = dt.timedelta(minutes=30)
# Velocity server name -> backend instance (its own log has deaths, commands and chat)
BACKEND = {"anarchy": "CrispyAnarchy01", "og": "CrispyAnarchy01", "vanilla": "Vanilla01", "skyblock": "Falling01", "falling": "Falling01",
           "pvp": "CrispyPvP01", "multiverse": "CrispyPvP01", "factions": "Factions01", "extraction": "Extraction01", "lobby": "CrispyLobby01"}
DEATH = re.compile(r" (was slain|was shot|was killed|was blown|blew up|drowned|burned|went up in flames|walked into fire|tried to swim|fell |hit the ground|"
                   r"suffocated|starved|withered|froze|was pricked|was squashed|was impaled|experienced kinetic|was fireballed|died|was struck|was poked|was speared|didn't want to live)")

LINE = re.compile(r"^\[(\d\d):(\d\d):(\d\d)\] (?:\[[^\]]*\] )*?(?:\[[^\]]*\]: |)(.*)$")
CONNECT = re.compile(r"\[connected player\] (\S+) \(/[^)]*\) has connected$")
DISCONNECT = re.compile(r"\[connected player\] (\S+) \(/[^)]*\) has disconnected(?:: (.*))?$")
SERVER = re.compile(r"\[server connection\] (\S+) -> (\S+) has connected$")
TROUBLE = re.compile(r"\[connected player\] (\S+) \(/[^)]*\): (unable to connect to server (\S+)|kicked from server (\S+): (.*)|read timed out)$")
SOURCE = re.compile(r"\[source\] (\S+) host=(\S+) new=(\w+)")   # CrispyTags 1.11.0+: the address each login used
REFUSED = re.compile(r"\[initial connection\] \S+ has disconnected: (.*)$")
SHUTDOWN = re.compile(r"Shutting down the proxy|Closing endpoint|Proxy shutting down")


def opener(path):
    return gzip.open(path, "rt", encoding="utf-8", errors="replace") if path.endswith(".gz") else open(path, encoding="utf-8", errors="replace")


def log_files(d):
    """Dated logs in order, then latest.log (dated from its first line's day, after the last dated file)."""
    dated = []
    for p in glob.glob(os.path.join(d, "*.log*")):
        m = re.match(r"(\d{4})-(\d\d)-(\d\d)-(\d+)\.log(\.gz)?$", os.path.basename(p))
        if m: dated.append(((dt.date(int(m[1]), int(m[2]), int(m[3])), int(m[4])), p))
    dated.sort()
    out = [(k[0], p) for k, p in dated]
    latest = os.path.join(d, "latest.log")
    if os.path.exists(latest):
        out.append((dt.datetime.fromtimestamp(os.path.getmtime(latest), dt.timezone.utc).date(), latest))
    return out


def events(d, lo=None, hi=None):
    """(datetime, message) for every line, with day roll-over inside a file. latest.log is dated back from its mtime.
    lo/hi (dates) skip dated files outside that range."""
    files = log_files(d)
    for day, path in files:
        if lo and not path.endswith("latest.log") and (day < lo - dt.timedelta(days=1) or day > hi): continue
        rows, prev = [], None
        with opener(path) as f:
            for line in f:
                m = LINE.match(line.rstrip("\n"))
                if not m: continue
                t = dt.time(int(m[1]), int(m[2]), int(m[3]))
                rows.append((t, m[4]))
        if not rows: continue
        if path.endswith("latest.log"):   # count the roll-overs, then start that many days before its mtime day
            rolls = sum(1 for a, b in zip(rows, rows[1:]) if dt.datetime.combine(day, b[0]) < dt.datetime.combine(day, a[0]) - dt.timedelta(hours=1))
            day = day - dt.timedelta(days=rolls)
        cur = day
        for t, msg in rows:
            stamp = dt.datetime.combine(cur, t)
            if prev and stamp < prev - dt.timedelta(hours=1):
                cur += dt.timedelta(days=1); stamp = dt.datetime.combine(cur, t)
            prev = stamp
            yield stamp, msg, path


class Session:
    def __init__(self, name, start):
        self.name, self.start, self.end = name, start, None
        self.servers = []      # (time, server)
        self.trouble = []      # (time, text)
        self.reason = None     # disconnect reason


def parse_proxy():
    sessions, open_s, refused, last_t = [], {}, collections.Counter(), None
    global SOURCES; SOURCES = {}
    first_seen_file = None
    for t, msg, path in events(PROXY):
        if first_seen_file is None: first_seen_file = t
        if SHUTDOWN.search(msg):
            for s in open_s.values(): s.end = t; s.reason = s.reason or "proxy restart"
            open_s.clear()
        if (m := CONNECT.search(msg)):
            n = m[1]
            if n in open_s: open_s[n].end = open_s[n].end or t
            s = Session(n, t); sessions.append(s); open_s[n] = s
        elif (m := SERVER.search(msg)):
            if m[1] in open_s: open_s[m[1]].servers.append((t, m[2]))
        elif (m := TROUBLE.search(msg)):
            if m[1] in open_s: open_s[m[1]].trouble.append((t, m[2]))
        elif (m := DISCONNECT.search(msg)):
            s = open_s.pop(m[1], None)
            if s: s.end, s.reason = t, m[2]
        elif (m := SOURCE.search(msg)):
            SOURCES.setdefault(m[1], m[2])   # first address this name ever used
        elif (m := REFUSED.search(msg)):
            refused[(t.isocalendar()[0], t.isocalendar()[1], m[1][:70])] += 1
        last_t = t
    for s in open_s.values(): s.end = last_t; s.reason = s.reason or "(still online / log ended)"
    return sessions, refused, first_seen_file, last_t


def visits_of(sessions):
    """Merge a player's sessions that are < REJOIN apart into visits: [(start, end, [sessions])]."""
    by = collections.defaultdict(list)
    for s in sessions: by[s.name].append(s)
    out = {}
    for n, ss in by.items():
        ss.sort(key=lambda s: s.start)
        v = []
        for s in ss:
            if v and s.start - v[-1][1] < REJOIN:
                v[-1][1] = max(v[-1][1], s.end or s.start); v[-1][2].append(s)
            else:
                v.append([s.start, s.end or s.start, [s]])
        out[n] = v
    return out


def pre_proxy_players(names, before):
    """Names (of the candidates) seen joining Anarchy/Vanilla in logs dated before `before`."""
    if not names: return set()
    pat = re.compile(r"(?<![A-Za-z0-9_])(" + "|".join(re.escape(n.lstrip(".")) for n in names) + r")(?:\[[^\]]*\])? joined the game")
    seen = set()
    for d in PRE_PROXY:
        for day, p in log_files(d):
            if day >= before or p.endswith("latest.log"): continue
            try:
                with opener(p) as f:
                    for line in f:
                        if "joined the game" in line and (m := pat.search(line)): seen.add(m[1])
            except (OSError, EOFError): pass
    return seen


def lobby_lines(name, start, end):
    """Chat and commands by this player in the lobby logs during [start, end]."""
    out, bare = [], name.lstrip(".")
    for t, msg, path in events(LOBBY, start.date(), end.date()):
        if t < start - dt.timedelta(minutes=1): continue
        if t > end + dt.timedelta(minutes=1): break
        if bare in msg and ("issued server command" in msg or f"<{bare}>" in msg or f"{bare}:" in msg or "left the game" in msg or "joined the game" in msg):
            out.append((t, re.sub(r"\s+", " ", msg)[:140]))
    return out


def backend_activity(name, server, start, end):
    """What a player did on a backend server between start and end: deaths, commands, chat lines, from its log."""
    inst = BACKEND.get(server.lower())
    if not inst: return None
    bare = name.lstrip(".")
    deaths, cmds, chat, first_death = 0, [], 0, None
    for t, msg, path in events(f"{I}/{inst}/Minecraft/logs", start.date(), end.date()):
        if t < start: continue
        if t > end: break
        if bare not in msg: continue
        if f"{bare} issued server command: " in msg:
            cmds.append((t, msg.split("issued server command: ", 1)[1].split(" ")[0][:30]))
        elif re.search(rf"<(?:\[[^\]]*\] ?)*{re.escape(bare)}>|\] {re.escape(bare)}: ", msg) or f"<{bare}>" in msg:
            chat += 1
        elif re.search(rf"(?<![A-Za-z0-9_]){re.escape(bare)}{DEATH.pattern}", msg):
            deaths += 1
            first_death = first_death or t
    return {"deaths": deaths, "first_death": first_death, "cmds": cmds, "chat": chat}


def pct(a, b): return f"{100 * a / b:.0f}%" if b else "n/a"
def mins(td): return td.total_seconds() / 60


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=60)
    ap.add_argument("--exclude", default="lbxd", help="comma-separated staff/test names to leave out")
    ap.add_argument("--out", default="/root/crispy_analytics")
    ap.add_argument("--names", action="store_true", help="print real names (the file on the host always has them)")
    ap.add_argument("--examples", type=int, default=5)
    a = ap.parse_args()

    sessions, refused, log_start, log_end = parse_proxy()
    excl = {x.strip().lower() for x in a.exclude.split(",") if x.strip()}
    sessions = [s for s in sessions if s.name.lstrip(".").lower() not in excl]
    visits = visits_of(sessions)
    now = log_end
    win_start = now - dt.timedelta(days=a.days)

    cand = {n: v for n, v in visits.items() if win_start <= v[0][0] <= now}
    veterans = pre_proxy_players(list(cand), log_start.date())
    new = {n: v for n, v in cand.items() if n.lstrip(".") not in veterans}

    rows = []
    for n, v in new.items():
        first = v[0]; start, end, ss = first
        servers = [(t, srv) for s in ss for t, srv in s.servers]
        modes = [(t, srv) for t, srv in servers if srv.lower() != "lobby"]
        trouble = [x for s in ss for x in s.trouble]
        reason = ss[-1].reason
        later = [x for x in v[1:]]
        age = now - start
        def played_between(d0, d1): return any(d0 <= (x[0] - start).days <= d1 for x in later)
        rows.append({
            "name": n, "bedrock": n.startswith("."), "start": start, "end": end, "dur": mins(end - start),
            "reached_lobby": any(srv.lower() == "lobby" for _, srv in servers),
            "mode": modes[0][1] if modes else None, "to_mode": mins(modes[0][0] - start) if modes else None,
            "trouble": trouble, "reason": reason, "visits": len(v),
            "d1": (len(later) > 0 and later[0][0] - start <= dt.timedelta(hours=48)) if age >= dt.timedelta(hours=48) else None,
            "d7": played_between(7, 13) if age >= dt.timedelta(days=14) else None,
            "d30": played_between(30, 59) if age >= dt.timedelta(days=60) else None,
            "ever": len(later) > 0, "first": first,
            # bounce: chose a mode but the whole first visit was under 2 minutes; error: a kick/connection failure in it
            "bounce": bool(modes) and (end - start) < dt.timedelta(minutes=2), "error": bool(trouble),
        })
    rows.sort(key=lambda r: r["start"])
    for r in rows:
        r["act"] = None
        if r["mode"]:
            start, end, ss = r["first"]
            r["act"] = backend_activity(r["name"], r["mode"], start, end)
    alias = {r["name"]: (r["name"] if a.names else f"Player {chr(65 + i % 26)}{'' if i < 26 else i // 26}") for i, r in enumerate(rows)}

    L = []
    p = L.append
    p(f"# Crispy new-player funnel, {win_start:%Y-%m-%d} to {now:%Y-%m-%d %H:%M} UTC")
    p(f"Proxy logs since {log_start:%Y-%m-%d}. Excluded: {', '.join(sorted(excl)) or 'nobody'}. "
      f"{len(cand)} names first seen in the window; {len(cand) - len(new)} had played Anarchy/Vanilla before the proxy, so {len(new)} are new.")
    p("")
    # ---- weekly cohorts
    p("## Weekly cohorts (by week of first join)")
    p("| week of | new | Bedrock | median 1st visit | chose a mode | bounced (<2 min) | error in 1st visit | 1st visit >= 10 min | D1 | D7 | D30 | ever returned |")
    p("|---|---|---|---|---|---|---|---|---|---|---|---|")
    weeks = collections.defaultdict(list)
    for r in rows: weeks[(r["start"] - dt.timedelta(days=r["start"].weekday())).date()].append(r)
    def rate(rs, k):
        el = [r for r in rs if r[k] is not None]
        return f"{pct(sum(r[k] for r in el), len(el))} ({sum(r[k] for r in el)}/{len(el)})" if el else "too soon"
    for wk in sorted(weeks):
        rs = weeks[wk]
        p(f"| {wk} | {len(rs)} | {sum(r['bedrock'] for r in rs)} | {statistics.median(r['dur'] for r in rs):.1f} min | "
          f"{pct(sum(1 for r in rs if r['mode']), len(rs))} | {pct(sum(r['bounce'] for r in rs), len(rs))} | {pct(sum(r['error'] for r in rs), len(rs))} | "
          f"{pct(sum(1 for r in rs if r['dur'] >= 10), len(rs))} | "
          f"{rate(rs, 'd1')} | {rate(rs, 'd7')} | {rate(rs, 'd30')} | {pct(sum(r['ever'] for r in rs), len(rs))} |")
    N = len(rows)
    p(f"| **all** | **{N}** | {sum(r['bedrock'] for r in rows)} | {statistics.median(r['dur'] for r in rows) if rows else 0:.1f} min | "
      f"{pct(sum(1 for r in rows if r['mode']), N)} | {pct(sum(r['bounce'] for r in rows), N)} | {pct(sum(r['error'] for r in rows), N)} | "
      f"{pct(sum(1 for r in rows if r['dur'] >= 10), N)} | {rate(rows, 'd1')} | {rate(rows, 'd7')} | {rate(rows, 'd30')} | {pct(sum(r['ever'] for r in rows), N)} |")
    p("")
    # ---- funnel
    p("## Funnel (first visit, then return)")
    st = [("joined the proxy", N),
          ("reached the lobby", sum(r["reached_lobby"] for r in rows)),
          ("chose a mode (left the lobby for a server)", sum(1 for r in rows if r["mode"])),
          ("first visit lasted 10+ minutes", sum(1 for r in rows if r["dur"] >= 10)),
          ("came back at all", sum(r["ever"] for r in rows))]
    el1 = [r for r in rows if r["d1"] is not None]
    st.append((f"came back within 48 h (of {len(el1)} old enough)", sum(r["d1"] for r in el1)))
    prev = None
    for label, n in st:
        drop = f" (lost {prev - n}, {pct(prev - n, prev)})" if prev is not None and "48 h" not in label else ""
        p(f"- {label}: **{n}** {pct(n, N)}{drop}")
        if "48 h" not in label: prev = n
    p("")
    p("Note: the funnel stages overlap (a 10-minute lobby visit counts as 10 minutes); the drop-off sections below split them.")
    p("")
    # ---- where first visits end
    p("## How first visits end")
    lobby_only = [r for r in rows if not r["mode"]]
    p(f"- Left without ever leaving the lobby: **{len(lobby_only)}** of {N} ({pct(len(lobby_only), N)}); "
      f"their lobby time: median {statistics.median(r['dur'] for r in lobby_only) if lobby_only else 0:.1f} min, "
      f"under 1 min: {sum(1 for r in lobby_only if r['dur'] < 1)}, 1-3 min: {sum(1 for r in lobby_only if 1 <= r['dur'] < 3)}, "
      f"3-10 min: {sum(1 for r in lobby_only if 3 <= r['dur'] < 10)}, 10+ min: {sum(1 for r in lobby_only if r['dur'] >= 10)}; "
      f"came back later: {sum(r['ever'] for r in lobby_only)}")
    tr = [r for r in rows if r["trouble"]]
    p(f"- Hit a connection error or kick in their first visit: **{len(tr)}** ({pct(len(tr), N)}); came back later: {sum(r['ever'] for r in tr)}")
    reasons = collections.Counter((r["reason"] or "(normal quit)").split(".")[0][:70] for r in rows)
    p("- Last disconnect reason of the first visit: " + "; ".join(f"{k} x{v}" for k, v in reasons.most_common(8)))
    p("")
    p("## First mode chosen")
    p("| first mode | players | median min to choose | median 1st visit | came back at all | D1 |")
    p("|---|---|---|---|---|---|")
    bym = collections.defaultdict(list)
    for r in rows: bym[r["mode"] or "(none, lobby only)"].append(r)
    for m, rs in sorted(bym.items(), key=lambda x: -len(x[1])):
        tm = [r["to_mode"] for r in rs if r["to_mode"] is not None]
        p(f"| {m} | {len(rs)} | {statistics.median(tm) if tm else 0:.1f} | {statistics.median(r['dur'] for r in rs):.1f} min | "
          f"{pct(sum(r['ever'] for r in rs), len(rs))} | {rate(rs, 'd1')} |")
    p("")
    p("## What happened on the first server (from that server's own log)")
    p("| first mode | players | died in 1st visit | median deaths | died within 3 min of joining | used a command | top commands tried | chatted |")
    p("|---|---|---|---|---|---|---|---|")
    for m, rs in sorted(bym.items(), key=lambda x: -len(x[1])):
        acts = [(r, r["act"]) for r in rs if r["act"]]
        if not acts: continue
        died = [r for r, x in acts if x["deaths"]]
        fast = [r for r, x in acts if x["first_death"] and x["first_death"] - r["start"] <= dt.timedelta(minutes=3)]
        cc = collections.Counter(c for r, x in acts for c in {c for _, c in x["cmds"]})
        p(f"| {m} | {len(acts)} | {len(died)} ({pct(len(died), len(acts))}) | {statistics.median(x['deaths'] for r, x in acts):.0f} | {len(fast)} | "
          f"{pct(sum(1 for r, x in acts if x['cmds']), len(acts))} | {', '.join(f'{c} x{n}' for c, n in cc.most_common(6)) or '-'} | {pct(sum(1 for r, x in acts if x['chat']), len(acts))} |")
    short = [r for r in rows if r["mode"] and r["dur"] < 10 and r["act"]]
    if short:
        p(f"- Of the {len(short)} who chose a mode but left within 10 minutes: died at least once {sum(1 for r in short if r['act']['deaths'])}, "
          f"tried a command {sum(1 for r in short if r['act']['cmds'])}, chatted {sum(1 for r in short if r['act']['chat'])}.")
    p("")
    p("## By source (address used on first join; CrispyTags 1.11.0+, so only players since it went live)")
    bys = collections.defaultdict(list)
    for r in rows: bys[SOURCES.get(r["name"], "(before tracking)")].append(r)
    p("| first-join address | new | chose a mode | 1st visit >= 10 min | median 1st visit | D1 | D7 | ever returned |")
    p("|---|---|---|---|---|---|---|---|")
    for h, rs in sorted(bys.items(), key=lambda x: -len(x[1])):
        p(f"| {h} | {len(rs)} | {pct(sum(1 for r in rs if r['mode']), len(rs))} | {pct(sum(1 for r in rs if r['dur'] >= 10), len(rs))} | "
          f"{statistics.median(r['dur'] for r in rs):.1f} min | {rate(rs, 'd1')} | {rate(rs, 'd7')} | {pct(sum(r['ever'] for r in rs), len(rs))} |")
    p("")
    p("## Java vs Bedrock")
    for label, rs in (("Java", [r for r in rows if not r["bedrock"]]), ("Bedrock", [r for r in rows if r["bedrock"]])):
        if rs: p(f"- {label}: {len(rs)} new, chose a mode {pct(sum(1 for r in rs if r['mode']), len(rs))}, "
                 f"errors {pct(sum(1 for r in rs if r['trouble']), len(rs))}, came back {pct(sum(r['ever'] for r in rs), len(rs))}, D1 {rate(rs, 'd1')}")
    p("")
    p("## Refused before login (no name: unofficial clients, auth outages, timeouts)")
    rw = collections.Counter()
    for (y, w, why), c in refused.items(): rw[why] += c
    for why, c in rw.most_common(6): p(f"- {why}: {c} (all time in the logs)")
    p("")
    # ---- examples
    p("## Example first visits")
    picks = []
    def take(pred, label):
        for r in rows:
            if r not in [x for x, _ in picks] and pred(r): picks.append((r, label)); return
    take(lambda r: not r["mode"] and r["dur"] < 3 and not r["ever"], "left the lobby within 3 minutes, never came back")
    take(lambda r: r["trouble"] and not r["ever"], "hit an error, never came back")
    take(lambda r: not r["mode"] and r["dur"] >= 3 and not r["ever"], "stayed in the lobby a while, never chose a mode")
    take(lambda r: r["mode"] and r["dur"] < 10 and not r["ever"], "chose a mode, gone within 10 minutes")
    take(lambda r: r["mode"] and r["ever"] and r["dur"] >= 10, "the good case: played and came back")
    for r, label in picks[:a.examples]:
        start, end, ss = r["first"]
        p(f"### {alias[r['name']]}{' (Bedrock)' if r['bedrock'] else ''}: {label}")
        tl = [(start, "logged in")]
        for s in ss:
            tl += [(t, f"-> {srv}") for t, srv in s.servers] + [(t, f"! {x}") for t, x in s.trouble]
            if s.end: tl.append((s.end, f"disconnected{': ' + s.reason if s.reason else ''}"))
        if r["act"]:
            for t, c in r["act"]["cmds"]: tl.append((t, f"{r['mode']}: ran {c}"))
            if r["act"]["first_death"]: tl.append((r["act"]["first_death"], f"{r['mode']}: first death ({r['act']['deaths']} deaths this visit)"))
        for t, x in lobby_lines(r["name"], start, end):
            x = x.replace(r["name"].lstrip("."), alias[r["name"]]) if not a.names else x
            tl.append((t, "lobby: " + x))
        for t, x in sorted(tl, key=lambda e: e[0]):
            p(f"- +{mins(t - start):5.1f} min  {x}")
        p(f"- visits in total: {r['visits']}")
        p("")
    text = "\n".join(L)
    os.makedirs(a.out, mode=0o700, exist_ok=True)
    full = text
    if not a.names:
        for real, al in alias.items(): full = full.replace(al + ":", al + f" [{real}]:", 1)
    path = os.path.join(a.out, f"funnel-{now:%Y-%m-%d}.md")
    with open(path, "w") as f: f.write(full + "\n")
    os.chmod(path, 0o600)
    print(text)
    print(f"\n(full report with names: {path})")


if __name__ == "__main__":
    main()
