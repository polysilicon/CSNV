package.path = "../mod/?.lua;lib/?.lua;./?.lua;" .. package.path
json = require("json")
local data = dofile("../mod/data.lua")
local run = require("run")
local shop = require("shop")
local perks = require("perks")
local mock = require("mockgame")

local pass, fail = 0, 0
local function check(name, cond, msg)
  if cond then pass = pass + 1 else fail = fail + 1 print("FAIL " .. name .. (msg and (": " .. msg) or "")) end
end

local function tick(R, secs, dt)
  dt = dt or 0.1
  for _ = 1, math.floor(secs / dt + 0.5) do run.update(R, dt) end
end

local function new_run(opts)
  local g = mock.new(opts)
  local events = {}
  local logs = {}
  local R = run.new({ data = data, game = g, emit = function(e) events[#events + 1] = e end, files = {},
                     log = function(s) logs[#logs + 1] = s end })
  R.logs = logs
  run.validate(R)
  return R, g, events
end

local function has(t, v) for _, x in ipairs(t) do if x == v then return true end end return false end

-- 1. a run starts fresh: weapons unequipped, starter given, immortal, teleported to island 1, countdown
do
  local R, g, ev = new_run()
  run.start(R, "CRAB42")
  check("start state", R.state == "countdown")
  check("seed", R.seed == "CRAB42")
  check("immortal", g.immortal == true)
  check("weapons and cyberware stashed", g.count("unequip") == #data.systems.strip_areas, g.count("unequip"))
  check("starter given", g.calls[#g.calls] and true and g.count("give") == 1)
  check("teleported", g.count("teleport") == 1)
  check("portal sound", has(ev, "portal"))
  tick(R, data.systems.countdown_s + 0.2)
  check("wave 1 begins", R.state == "wave" and R.wave == 1, R.state)
  check("countdown ticks", #(function() local t = {} for _, e in ipairs(ev) do if e == "countdown" then t[#t + 1] = e end end return t end)() >= 3)
  -- spawn the whole wave
  tick(R, 30)
  check("wave 1 spawns up to max alive", #R.queue == run.band(R, 1).count - run.band(R, 1).max_alive, #R.queue)
  check("max alive respected", run.alive_count(R) <= run.band(R, 1).max_alive)
  check("hostile set", g.count("hostile") >= 1)
  local before = R.crystals
  g.kill_all(); tick(R, 0.2)
  check("crystals from kills", R.crystals > before)
  -- some may still be queued if max_alive < count: keep killing
  for _ = 1, 20 do if R.state ~= "wave" then break end tick(R, 3) g.kill_all() tick(R, 0.2) end
  check("wave cleared -> shop", R.state == "shop", R.state)
  check("time slowed in shop", g.dilated == true)
  check("six cards", #R.shop.cards == 6)
  check("cards 1-3 are crab perks", R.shop.cards[1].kind == "perk" and R.shop.cards[3].kind == "perk")
  check("card 4 cyberware", R.shop.cards[4] and R.shop.cards[4].kind == "cyberware")
  check("card 5 weapon", R.shop.cards[5] and R.shop.cards[5].kind == "weapon")
  check("no iconic before wave 5", not R.shop.cards[5].row.iconic and not R.shop.cards[6].row.iconic)
  -- buy a perk
  R.crystals = 1000
  local c1 = R.shop.cards[1]
  run.input(R, "buy1")
  check("perk bought", perks.stacks(R.perks, c1.id) == 1 and c1.sold)
  check("perk sound", has(ev, "perk"))
  run.input(R, "buy1")
  check("no double buy", perks.stacks(R.perks, c1.id) == 1)
  -- buy cyberware: snapshots its area, gives + equips
  local c4 = R.shop.cards[4]
  run.input(R, "buy4")
  check("cyberware given", g.count("give") == 2 and R.owned[c4.id])
  check("cyberware area snapshot", R.snap[c4.row.area] ~= nil)
  local cr = R.crystals
  run.input(R, "reroll")
  check("reroll costs", R.crystals == cr - data.systems.reroll_price)
  check("owned cyberware not offered again", not (R.shop.cards[4] and R.shop.cards[4].id == c4.id))
  run.input(R, "continue")
  check("shop closed", R.state == "countdown" and g.dilated == false)
  -- play to wave 3 then island hop after its shop
  local function clear_wave()
    tick(R, 4) -- countdown
    for _ = 1, 40 do if R.state ~= "wave" then break end tick(R, 3) g.kill_all() tick(R, 0.2) end
  end
  clear_wave() check("wave 2 cleared", R.wave == 2 and R.state == "shop")
  run.input(R, "continue")
  clear_wave() check("wave 3 cleared", R.wave == 3 and R.state == "shop")
  local tp = g.count("teleport")
  run.input(R, "continue")
  check("island hop after wave 3", g.count("teleport") == tp + 1 and R.stage_i == 2)
  run.input(R, "continue") clear_wave() run.input(R, "continue")
  tick(R, 4)
  check("wave 5 is a boss wave", R.wave == 5 and R.boss == true)
  local bosses = 0
  for _, r in ipairs(R.queue) do if r.boss then bosses = bosses + 1 end end
  for _, e in ipairs(R.enemies) do if e.row.boss then bosses = bosses + 1 end end
  check("boss present", bosses == data.systems.bosses_per_boss_wave, bosses)
  -- death ends the run and restores gear
  g.hp = 1
  tick(R, 0.1)
  check("death -> over", R.state == "over" and R.last.why == "died")
  check("death sound", has(ev, "death"))
  check("mortal again", g.immortal == false)
  check("run items removed", next(g.inv) == nil)
  check("stat mods removed", next(g.stats) == nil)
  check("originals re-equipped", g.count("equip") >= 4)
  check("no enemies left", next(g.ents) == nil)
  check("sent home", g.pos.x == 0 and g.pos.y == 0)
  check("best recorded", R.best.wave >= 4)
end

-- 1b. enemies only leave the count when seen alive then dead
do
  -- never appear: the counter must not tick down by itself; they are respawned, then dropped with a log line
  local R, g = new_run({ ghost = true })
  run.start(R, "GHOST1") tick(R, data.systems.countdown_s + 0.2)
  local start_count = #R.queue + run.alive_count(R)
  tick(R, data.systems.enemy_appear_timeout_s - 1)
  check("ghosts still counted before the timeout", #R.queue + run.alive_count(R) == start_count)
  check("no crystals for ghosts", R.crystals == data.systems.start_crystals)
  local respawned = false
  for _, l in ipairs(R.logs) do if l:find("never appeared, spawning it again") then respawned = true end end
  tick(R, 3)
  for _, l in ipairs(R.logs) do if l:find("never appeared, spawning it again") then respawned = true end end
  check("ghost enemy respawned", respawned)
  tick(R, 120)
  local dropped = false
  for _, l in ipairs(R.logs) do if l:find("dropped after") then dropped = true end end
  check("ghost dropped after retries, logged", dropped)
  check("no kill credit for ghosts", R.kills == 0)
end
do
  -- spawned already dead (e.g. not initialised): no credit, spawned again
  local R, g = new_run({ born_dead = true })
  run.start(R, "DEAD01") tick(R, data.systems.countdown_s + 0.2) tick(R, 5)
  check("born-dead not credited", R.kills == 0 and R.crystals == data.systems.start_crystals)
end
do
  -- seen alive, then dead: credited once
  local R, g = new_run()
  run.start(R, "ALIVE1") tick(R, data.systems.countdown_s + 0.2) tick(R, 0.5)
  local before = R.kills
  g.kill_all() tick(R, 0.2) tick(R, 0.2)
  check("real kill credited", R.kills > before)
  -- the run ends: every stashed area is re-equipped
  local eq = g.count("equip")
  run.finish(R, "quit")
  check("all stashed gear re-equipped", g.count("equip") - eq == #data.systems.strip_areas, g.count("equip") - eq)
end

do
  -- a spawn call that fails must not shrink the count: the enemy is queued again, and the error is logged
  local R, g = new_run({ spawn_fails = 2 })
  run.start(R, "FAIL01") tick(R, data.systems.countdown_s + 0.2)
  local total = run.band(R, 1).count
  tick(R, 0.1)
  check("failed spawn keeps the count", #R.queue + run.alive_count(R) == total, #R.queue + run.alive_count(R))
  local logged = false
  for _, l in ipairs(R.logs) do if l:find("could not spawn .*bad spec field") then logged = true end end
  check("spawn error logged with its reason", logged)
  tick(R, 10)
  check("enemy spawned after the failures pass", g.count("spawn") >= 3 and run.alive_count(R) >= 1)
end
do
  -- a spawn that always fails is dropped only after its tries, with a log line
  local R, g = new_run({ spawn_fails = 1000 })
  run.start(R, "FAIL02") tick(R, data.systems.countdown_s + 0.2) tick(R, 60)
  local dropped = false
  for _, l in ipairs(R.logs) do if l:find("dropped after .* failed spawns") then dropped = true end end
  check("always-failing spawn dropped with a log line", dropped)
end

-- 2. seeds: same seed -> same islands, waves and first shop; different seed differs
do
  local function fingerprint(seed)
    local R = new_run()
    run.start(R, seed)
    local s = {}
    for _, st in ipairs(R.stage_order) do s[#s + 1] = st.id end
    for w = 1, 6 do for _, e in ipairs((run.compose(R, w))) do s[#s + 1] = e.id end end
    R.wave = 1 shop.open(R)
    for _, c in ipairs(R.shop.cards) do s[#s + 1] = c and c.id or "-" end
    return table.concat(s, ",")
  end
  check("seed deterministic", fingerprint("ZZ99AB") == fingerprint("ZZ99AB"))
  check("seeds differ", fingerprint("ZZ99AB") ~= fingerprint("HJK234"))
end

-- 3. seed entry from the over screen
do
  local R = new_run()
  run.start(R, "AAAAAA") run.finish(R, "quit")
  run.input(R, "seed_entry")
  for c in ("Q7WX"):gmatch(".") do run.input(R, "seed_char", c) end
  run.input(R, "seed_back")
  for c in ("XYZ"):gmatch(".") do run.input(R, "seed_char", c) end
  check("seed typed", R.seed_input == "Q7WXYZ", R.seed_input)
  run.input(R, "continue")
  check("seeded run started", R.state == "countdown" and R.seed == "Q7WXYZ")
  run.input(R, "end_run")
  check("quit ends run", R.state == "over" and R.last.why == "quit")
  run.input(R, "new_run")
  check("new random run", R.state == "countdown" and #R.seed == 6)
end

-- 4. records the game doesn't have are skipped, never spawned or sold
do
  local bad = { ["Character.maxtac_rifle_ma_elite"] = true, ["Items.StrongArms"] = true }
  local R = new_run({ bad = bad })
  run.start(R, "BADREC")
  for w = 1, 20 do for _, e in ipairs((run.compose(R, w))) do check("bad enemy skipped", not bad[e.record]) end end
  for _ = 1, 30 do R.wave = 6 shop.open(R) local c = R.shop.cards[4] check("bad cyberware skipped", not (c and bad[c.row.record])) end
end

-- 5. navmesh not ready: spawns wait instead of failing
do
  local R, g = new_run({ navfail = 12 })
  run.start(R, "NAVNAV") tick(R, data.systems.countdown_s + 0.2)
  tick(R, 3)
  check("spawn retried after navmesh miss", g.count("spawn") >= 1)
end

-- 6. perks: stat perks add modifiers, discounts lower prices, crystal perks pay, auras hit nearby enemies
do
  local R, g = new_run()
  run.start(R, "PERKS1")
  perks.add(R.perks, "Vitality") perks.add(R.perks, "Vitality")
  check("vitality stacks", g.count("add_stat") == 2)
  R.wave = 1 shop.open(R)
  local c = R.shop.cards[5] local p0 = c.price
  perks.add(R.perks, "ValuedCustomer")
  check("discount", shop.price(R, c) < p0)
  perks.add(R.perks, "BonusCrystals")
  check("bonus crystals", run.gain(R, 10) == 12)
  perks.add(R.perks, "FireAura")
  local en = { { handle = {}, pos = { x = 1, y = 0, z = 0 } }, { handle = {}, pos = { x = 50, y = 0, z = 0 } } }
  perks.tick(R.perks, 5, en, { x = 0, y = 0, z = 0 })
  check("aura hits near only", g.count("status") == 1)
  for i = 1, 5 do perks.add(R.perks, "Regenerator") end
  check("max stacks", not perks.can_take(R.perks, "Regenerator"))
end

-- 7. ledger: a save made mid-run gives its items back on the next session
do
  local tmp = os.tmpname()
  local g = mock.new()
  local R = run.new({ data = data, game = g, files = { ledger = tmp, best = tmp .. ".best" } })
  run.validate(R) run.start(R, "LEDGER")
  local R2 = run.new({ data = data, game = g, files = { ledger = tmp, best = tmp .. ".best" } })
  local n = run.cleanup_stale(R2)
  check("ledger lists run items", n == 1, n)
  check("ledger items removed", g.count("remove_record") == 1)
  check("ledger cleared", run.cleanup_stale(R2) == 0)
  os.remove(tmp) os.remove(tmp .. ".best")
end

print(string.format("%d passed, %d failed", pass, fail))
os.exit(fail == 0 and 0 or 1)
