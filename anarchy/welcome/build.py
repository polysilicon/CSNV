#!/usr/bin/env python3
"""crispy_welcome: what a brand-new player is told on Crispy Anarchy (26.2 datapack).

    python3 build.py <outdir>      -> <outdir>/crispy_welcome  (install as world/datapacks/crispy_welcome, /reload)

Hook: the live random_spawn datapack's check.mcfunction runs `function crispy_welcome:new` right after it scatters a
brand-new player (empty inventory, no XP), so only genuinely new players are welcomed; nobody else is touched.

- 4 s after landing (once the chunks are in): a title and a short welcome in chat with buttons:
  [Market] (/trigger market: the market datapack's 3-second teleport), [Clans] (/clan list), [Survival tips]
  (/trigger cw_help) and [Other modes] (/lobby, the proxy).
- [Survival tips] works for anyone, any time: /trigger cw_help.
- Their first death (once): a line about random respawns and beds, with the tips button.
- Test it yourself: /trigger cw_test (players in TESTERS) or /function crispy_welcome:test (ops) - scatters you like a new player (random_spawn:place) and
  runs the whole sequence, including the first-death line on your next death. Inventory is untouched.
"""
import json, os, shutil, sys

OUT = os.path.join(sys.argv[1], "crispy_welcome")
TESTERS = ["lbxd"]   # may run /trigger cw_test (no op needed)
FN = os.path.join(OUT, "data", "crispy_welcome", "function")


def fn(name, lines):
    p = os.path.join(FN, name + ".mcfunction")
    os.makedirs(os.path.dirname(p), exist_ok=True)
    open(p, "w", encoding="utf-8").write("\n".join(lines) + "\n")


def t(text, color="gray", **kw):
    d = {"text": text, "color": color}; d.update(kw); return d


def button(label, color, command, hover):
    return t(label, color, bold=True, underlined=True, click_event={"action": "run_command", "command": command},
             hover_event={"action": "show_text", "value": t(hover, "gray")})


def tellraw(parts):
    return "tellraw @s " + json.dumps(parts, ensure_ascii=False)


shutil.rmtree(OUT, ignore_errors=True)
os.makedirs(os.path.join(OUT, "data", "minecraft", "tags", "function"))
json.dump({"pack": {"description": "Crispy Anarchy: welcome and survival tips for brand-new players (26.2)",
                    "min_format": [107, 0], "max_format": [107, 1]}},
          open(os.path.join(OUT, "pack.mcmeta"), "w"), indent=2)
json.dump({"values": ["crispy_welcome:load"]}, open(os.path.join(OUT, "data/minecraft/tags/function/load.json"), "w"))
json.dump({"values": ["crispy_welcome:tick"]}, open(os.path.join(OUT, "data/minecraft/tags/function/tick.json"), "w"))

fn("load", [
    "scoreboard objectives add cw_t dummy",          # ticks until the welcome shows
    "scoreboard objectives add cw_new dummy",        # 1 = welcomed as new, first-death line not shown yet
    "scoreboard objectives add cw_deaths deathCount",
    "scoreboard objectives add cw_life minecraft.custom:minecraft.time_since_death",
    "scoreboard objectives add cw_help trigger",
    "scoreboard objectives add cw_test trigger",     # testers only (TESTERS): replay the new-player experience
])

fn("tick", [
    "execute as @a[scores={cw_t=1..}] run scoreboard players remove @s cw_t 1",
    "execute as @a[scores={cw_t=0}] at @s run function crispy_welcome:show",
    "execute as @a[scores={cw_help=1..}] run function crispy_welcome:tips",
    "scoreboard players enable @a cw_help",
    *[f"scoreboard players enable @a[name={n}] cw_test" for n in TESTERS],
    "execute as @a[scores={cw_test=1..}] run function crispy_welcome:test",
    # first death of a welcomed player, shown 2 s after they respawn
    "execute as @a[scores={cw_new=1,cw_deaths=1..,cw_life=40..}] run function crispy_welcome:first_death",
])

# called by random_spawn:check right after a brand-new player is scattered
fn("new", [
    "scoreboard players set @s cw_t 80",
    "scoreboard players set @s cw_new 1",
    "scoreboard players set @s cw_deaths 0",
])

fn("show", [
    "scoreboard players reset @s cw_t",
    'title @s times 10 70 20',
    'title @s subtitle ' + json.dumps(t("No rules · No claims · One world since 2020", "gray")),
    'title @s title ' + json.dumps(t("CRISPY ANARCHY", "gold", bold=True)),
    "playsound minecraft:ui.toast.challenge_complete master @s ~ ~ ~ 0.5 1.2",
    tellraw(t(" ")),
    tellraw([t("✦ Welcome to Crispy Anarchy, ", "gold", bold=True), {"selector": "@s", "color": "yellow", "bold": True}, t("!", "gold", bold=True)]),
    tellraw(t("No rules, no claims, no protected bases: anyone can kill you or take your stuff. "
              "One world, never reset since 2020.", "gray")),
    tellraw(t("You've landed somewhere random near the old spawn, the most wrecked part of the map. "
              "Head out a couple of thousand blocks for untouched land.", "gray")),
    tellraw([button("[Market]", "gold", "/trigger market",
                    "Shops for custom enchantments and cyberware implants.\nPvP is on there too. Also: /trigger market"),
             t("  "),
             button("[Clans]", "aqua", "/clan list", "Team up with other players.\n/clan list, /clan create <name>"),
             t("  "),
             button("[Survival tips]", "green", "/trigger cw_help", "How not to lose everything on day one.\nAny time: /trigger cw_help"),
             t("  "),
             button("[Other modes]", "light_purple", "/lobby", "Back to the lobby: Skyblock, Multiverse,\nExtraction Zone and Vanilla")]),
    tellraw(t(" ")),
])

TIPS = [
    "Sleep in a bed to set your respawn point. Without one you respawn somewhere random.",
    "Ender chests are the only storage nobody else can open.",
    "The old spawn around 0, 0 is griefed. Travel far out before you build anything.",
    "No rules means no protection: hide your base away from paths and portals.",
    "The Market (/trigger market) sells custom enchantments for XP and cyberware implants for diamonds.",
    "Want a team? /clan list shows the clans; ask in chat to join one.",
    "Chat here is shared with every Crispy server and the Discord, so say hi.",
]
fn("tips", [
    "scoreboard players set @s cw_help 0",
    tellraw(t("Survival tips", "green", bold=True)),
    *[tellraw([t(" • ", "dark_gray"), t(x, "gray")]) for x in TIPS],
    tellraw([t(" "), button("[Market]", "gold", "/trigger market", "Go to the Market (3-second teleport)"), t("  "),
             button("[Clans]", "aqua", "/clan list", "List the clans")]),
])

fn("first_death", [
    "scoreboard players set @s cw_new 0",
    tellraw([t("You died! ", "red", bold=True),
             t("With no bed you respawn somewhere random, so sleep in one to come back near your stuff. ", "gray"),
             button("[Survival tips]", "green", "/trigger cw_help", "How not to lose everything")]),
])

fn("test", [
    "scoreboard players set @s cw_test 0",
    tellraw(t("Testing the new-player welcome: scattering you like a brand-new player...", "yellow")),
    "function random_spawn:place",
    "function crispy_welcome:new",
])

print("wrote", OUT)
