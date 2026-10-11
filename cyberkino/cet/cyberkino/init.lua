-- Cyberpunk Kino: Black Ops-style Zombies in Megabuilding H10.
-- Press F7 (CET binding "start") on V's floor: barricades close the corridors in rings, wall-buys go on the
-- walls, the Mystery Box in the open, and Scavenger and Maelstrom zombies come in rounds. V starts with only a
-- Unity; everything V is carrying comes back when the match ends. Data comes from data.lua (generated from
-- sheets/*.json by tools/build.py). Every step is written to cyberkino.log next to this file.

local data = require("data")
local rules = data.rules

local S = { active = false }
local layout = { rows = {} } -- the arena layout (see the layout section)
local hud = { msg = "", msgUntil = 0, prompt = "" }

-- ---------------------------------------------------------------- log

local function log(fmt, ...)
	local line = os.date("%H:%M:%S ") .. string.format(fmt, ...)
	print("[CyberKino] " .. line)
	local f = io.open("cyberkino.log", "a")
	if f then
		f:write(line .. "\n")
		f:close()
	end
end

local function say(text, seconds)
	hud.msg = text
	hud.msgUntil = os.clock() + (seconds or 4)
	log("say: %s", text)
end

local function try(what, fn, ...)
	local ok, a, b = pcall(fn, ...)
	if not ok then
		log("%s failed: %s", what, tostring(a))
		return nil
	end
	return a, b
end

-- ---------------------------------------------------------------- vectors and world

local function v4(x, y, z) return Vector4.new(x, y, z, 1) end
local function pos(e) local p = e:GetWorldPosition() return v4(p.x, p.y, p.z) end
local function flat(a, b) local dx, dy = a.x - b.x, a.y - b.y return math.sqrt(dx * dx + dy * dy) end
local function along(c, dir, d, dz) return v4(c.x + dir.x * d, c.y + dir.y * d, c.z + (dz or 0)) end
local function yawOf(dir) return math.deg(math.atan2(dir.y, dir.x)) - 90 end

local function transform(p, yaw)
	local t = WorldTransform.new()
	t:SetPosition(p)
	t:SetOrientationEuler(EulerAngles.new(0, 0, yaw or 0))
	return t
end

local function spawnProp(id, p, yaw)
	local path = data.props[id]
	local eid = try("spawn " .. id, function() return exEntitySpawner.Spawn(path, transform(p, yaw)) end)
	return eid
end

local function despawn(eid)
	if not eid then return end
	local e = Game.FindEntityByID(eid)
	if e then try("despawn", function() exEntitySpawner.Despawn(e) end) end
end

-- ---------------------------------------------------------------- inventory

local function player() return Game.GetPlayer() end

local function equipmentSystem()
	return Game.GetScriptableSystemsContainer():Get(CName.new("EquipmentSystem"))
end

local function itemIDs()
	local ids = {}
	local ok, list = Game.GetTransactionSystem():GetItemList(player())
	if ok and list then
		for _, item in ipairs(list) do
			ids[#ids + 1] = item:GetID()
		end
	end
	return ids
end

local function idKey(id)
	return tostring(id.id.hash) .. ":" .. tostring(id.rngSeed)
end

-- gives one record and returns the new item's ItemID (the one that wasn't there before)
local function give(record, qty)
	local before = {}
	for _, id in ipairs(itemIDs()) do before[idKey(id)] = true end
	Game.AddToInventory(record, qty or 1)
	local want = TweakDBID.new(record).hash
	for _, id in ipairs(itemIDs()) do
		if not before[idKey(id)] and id.id.hash == want then
			return id
		end
	end
	return nil
end

local function equip(itemID, slot)
	try("equip", function()
		local req = GameplayEquipRequest.new()
		req.owner = player()
		req.itemID = itemID
		req.addToInventory = false
		req.forceEquipWeapon = true
		if slot then req.slotIndex = slot end
		equipmentSystem():QueueRequest(req)
	end)
end

local function remove(itemID)
	try("remove item", function() Game.GetTransactionSystem():RemoveItem(player(), itemID, 1) end)
end

-- remembers and takes off V's weapons and cyberware, so a match starts with the Unity only and the
-- chips are V's only cyberware; restoreLoadout puts it all back
local function stashLoadout()
	S.stashed = {}
	local pd = try("player data", function() return equipmentSystem():GetPlayerData(player()) end)
	if not pd then return end
	local areas = { { name = "Weapon", slots = 3 } }
	for _, a in ipairs(data.cyberwareAreas) do areas[#areas + 1] = { name = a, slots = 4 } end
	local counts = {}
	for _, a in ipairs(areas) do
		local area = gamedataEquipmentArea[a.name]
		for slot = 0, a.slots - 1 do
			local id = area and try("slot " .. a.name, function() return pd:GetItemInEquipSlot(area, slot) end)
			if id and ItemID.IsValid(id) then
				S.stashed[#S.stashed + 1] = { id = id, slot = slot, area = a.name }
				counts[#counts + 1] = a.name .. "#" .. slot
				try("unequip " .. a.name, function()
					local req = UnequipRequest.new()
					req.owner = player()
					req.areaType = area
					req.slotIndex = slot
					req.force = true
					equipmentSystem():QueueRequest(req)
				end)
			end
		end
	end
	log("took off %d items: %s", #S.stashed, table.concat(counts, ", "))
end

-- V's weapons go into V's own stash (in the apartment, recorded in the layout) for the match, and come back
-- after it; if the stash can't be found they are only taken off, never deleted
local function stashEntity()
	local r
	for _, row in ipairs(layout.rows) do if row.kind == "stash" then r = row end end
	if not r or not r.entity or r.entity == "none" then return nil end
	local h = try("stash id", function() return loadstring("return " .. r.entity)() end)
	local id = h and try("stash entity id", function() return entEntityID.new({ hash = h }) end)
	return id and Game.FindEntityByID(id) or nil
end

local function isWeapon(id)
	local ok, cat = pcall(function() return RPGManager.GetItemCategory(id) end)
	if ok and cat ~= nil then return cat == gamedataItemCategory.Weapon end
	local ok2, t = pcall(function() return TweakDBInterface.GetItemRecord(id.id):ItemCategory():Type() end)
	return ok2 and t == gamedataItemCategory.Weapon
end

local function stashWeapons()
	S.inStash = {}
	local st = stashEntity()
	if not st then
		log("V's stash not found: weapons are only taken off")
		return
	end
	local ts = Game.GetTransactionSystem()
	for _, id in ipairs(itemIDs()) do
		if isWeapon(id) then
			local moved = try("move to stash", function() return ts:TransferItem(player(), st, id, 1) end)
			if moved ~= false then S.inStash[#S.inStash + 1] = id end
		end
	end
	log("moved %d weapons into V's stash", #S.inStash)
end

local function unstashWeapons()
	if not S.inStash or #S.inStash == 0 then return end
	local st = stashEntity()
	if not st then
		log("V's stash not found: weapons stay in it")
		say("Your weapons are waiting in V's stash", 6)
		return
	end
	for _, id in ipairs(S.inStash) do
		try("back from stash", function() Game.GetTransactionSystem():TransferItem(st, player(), id, 1) end)
	end
	log("moved %d weapons back from V's stash", #S.inStash)
end

local function restoreLoadout()
	for _, it in ipairs(S.stashed or {}) do equip(it.id, it.slot) end
	log("put back %d items", #(S.stashed or {}))
end

local function giveGun(w)
	local id = give(w.record, 1)
	Game.AddToInventory(w.ammo, w.ammo_amount)
	if id then
		S.given[#S.given + 1] = id
		equip(id)
		S.owned[w.id] = true
	else
		log("gave %s but could not find it in the inventory", w.record)
	end
end

-- ---------------------------------------------------------------- cyberware

local function installCyber(c)
	S.cyber[c.id] = true
	if c.effect == "stat" then
		local mod = try("stat modifier", function()
			local m = RPGManager.CreateStatModifier(gamedataStatType[c.params.stat], gameStatModifierType.Additive, c.params.value)
			Game.GetStatsSystem():AddModifier(player():GetEntityID(), m)
			return m
		end)
		if mod then S.mods[#S.mods + 1] = mod end
	elseif c.effect == "item" then
		local id = give(c.params.record, 1)
		if id then
			S.given[#S.given + 1] = id
			equip(id)
		end
	end
	say(c.name .. " installed. " .. c.how_to_use, 6)
end

local function removeCyber()
	for _, m in ipairs(S.mods or {}) do
		try("remove stat modifier", function() Game.GetStatsSystem():RemoveModifier(player():GetEntityID(), m) end)
	end
	S.mods = {}
	try("end slow-mo", function() Game.GetTimeSystem():UnsetTimeDilation(CName.new("cyberkino")) end)
end

local function sandevistan()
	local c = data.cyberwareById.sandevistan
	if not S.active or not S.cyber.sandevistan then return end
	local now = os.clock()
	if now < (S.sandeReady or 0) then
		say(string.format("Sandevistan recharging (%ds)", math.ceil(S.sandeReady - now)), 2)
		return
	end
	S.sandeReady = now + c.params.duration_s + c.params.cooldown_s
	S.sandeEnd = now + c.params.duration_s
	try("slow-mo", function()
		Game.GetTimeSystem():SetTimeDilation(CName.new("cyberkino"), c.params.timescale)
		Game.GetTimeSystem():SetIgnoreTimeDilationOnLocalPlayerZero(true)
	end)
	say("SANDEVISTAN", 2)
end

-- ---------------------------------------------------------------- arena

local function weightedBoxPick()
	local pool, total = {}, 0
	for _, w in ipairs(data.weapons) do
		if (w.role == "box" or w.role == "rare") and not S.owned[w.id] then
			local wt = w.role == "rare" and rules.rare_weight or 3
			pool[#pool + 1] = { w = w, wt = wt }
			total = total + wt
		end
	end
	if total == 0 then return nil end
	local r = math.random() * total
	for _, p in ipairs(pool) do
		r = r - p.wt
		if r <= 0 then return p.w end
	end
	return pool[#pool].w
end

-- ---------------------------------------------------------------- layout
-- The arena is a fixed layout: rows (kind, x, y, z, yaw, zone, weapon, inside_x/y/z, entity) made with the
-- in-game layout editor (CET overlay) and saved to layout.json; once sent in, it is built into data.layout.
-- kinds: start (where F7 teleports V), barricade (closes zone -> zone + 1; inside_* is the side V stands on),
-- wallbuy (weapon = weapons sheet id), box (Mystery Box spots, it moves between them), spawn (zombie window,
-- active once its zone is open), stash (V's stash container, entity = its EntityID hash).

local LAYOUT_FILE = "layout.json"

local function loadLayout()
	local f = io.open(LAYOUT_FILE, "r")
	if f then
		local text = f:read("*a")
		f:close()
		local ok, t = pcall(json.decode, text)
		if ok and t and t.rows then
			layout = t
			log("layout: %d rows from %s (your own layout)", #layout.rows, LAYOUT_FILE)
			return
		end
		log("layout: %s could not be read", LAYOUT_FILE)
	end
	layout = { rows = data.layout or {} }
	log("layout: %d rows built into the mod", #layout.rows)
end

local function saveLayout()
	local f = io.open(LAYOUT_FILE, "w")
	if not f then say("Could not save " .. LAYOUT_FILE, 4) return end
	f:write(json.encode(layout))
	f:close()
	log("layout saved: %d rows", #layout.rows)
end

local function rowsOf(kind)
	local out = {}
	for _, r in ipairs(layout.rows) do if r.kind == kind then out[#out + 1] = r end end
	return out
end

local function rowPos(r) return v4(r.x, r.y, r.z) end

local function buildArena()
	S.zone = 1
	S.barricades = {} -- zone -> list of {eid, pos, inside}
	S.buys = {}       -- {kind, pos, eid, weapon|ring}
	local maxZone = 1
	for _, r in ipairs(rowsOf("barricade")) do
		S.barricades[r.zone] = S.barricades[r.zone] or {}
		local p = rowPos(r)
		table.insert(S.barricades[r.zone], { eid = spawnProp("barricade", p, r.yaw), pos = p, inside = v4(r.inside_x, r.inside_y, r.inside_z), yaw = r.yaw })
		S.buys[#S.buys + 1] = { kind = "door", ring = r.zone, pos = p }
		maxZone = math.max(maxZone, r.zone + 1)
	end
	S.maxZone = maxZone
	for _, r in ipairs(rowsOf("wallbuy")) do
		local w = data.weaponsById[r.weapon]
		if w then
			local p = rowPos(r)
			S.buys[#S.buys + 1] = { kind = "wall", weapon = w, pos = p, eid = spawnProp("wallbuy", p, r.yaw) }
		else
			log("layout: wall-buy for unknown gun %s", tostring(r.weapon))
		end
	end
	S.boxSpots = rowsOf("box")
	S.boxUses = 0
	S.boxSpot = math.random(math.max(#S.boxSpots, 1))
	local spot = S.boxSpots[S.boxSpot]
	if spot then
		S.buys[#S.buys + 1] = { kind = "box", pos = rowPos(spot), eid = spawnProp("box", rowPos(spot), spot.yaw) }
	end
	S.spawns = rowsOf("spawn")
	log("arena: %d barricades, %d wall-buys, %d box spots, %d zombie spawns, %d zones",
		#rowsOf("barricade"), #rowsOf("wallbuy"), #S.boxSpots, #S.spawns, maxZone)
end

-- after a few uses the Mystery Box moves to another spot, as in Kino
local function moveBox()
	if #S.boxSpots < 2 then return end
	for i, b in ipairs(S.buys) do
		if b.kind == "box" then despawn(b.eid) table.remove(S.buys, i) break end
	end
	local next = S.boxSpot
	while next == S.boxSpot do next = math.random(#S.boxSpots) end
	S.boxSpot = next
	local spot = S.boxSpots[next]
	S.buys[#S.buys + 1] = { kind = "box", pos = rowPos(spot), eid = spawnProp("box", rowPos(spot), spot.yaw) }
	say("The Mystery Box moved", 3)
end

local function openRing(ring)
	for _, b in ipairs(S.barricades[ring] or {}) do despawn(b.eid) end
	S.barricades[ring] = {}
	S.zone = math.max(S.zone, ring + 1)
	for i = #S.buys, 1, -1 do
		if S.buys[i].kind == "door" and S.buys[i].ring == ring then table.remove(S.buys, i) end
	end
end

local function doorCost(ring) return rules.door_cost_first + (ring - 1) * rules.door_cost_step end

-- ---------------------------------------------------------------- zombies

local function zombiePool(round)
	local pool = {}
	for _, z in ipairs(data.zombies) do
		if z.pool ~= "boss" and z.from_round <= round then pool[#pool + 1] = z end
	end
	return pool
end

local function spawnPoint()
	local open = {}
	for _, r in ipairs(S.spawns) do if r.zone <= S.zone then open[#open + 1] = r end end
	if #open == 0 then open = S.spawns end
	local r = open[math.random(#open)]
	-- a little spread so a crowd doesn't stack on one point
	local a = math.random() * 2 * math.pi
	return v4(r.x + math.cos(a) * 0.8, r.y + math.sin(a) * 0.8, r.z + 0.2), { x = math.cos(math.rad(r.yaw + 90)), y = math.sin(math.rad(r.yaw + 90)) }
end

local function spawnZombie(z, special)
	local p, d = spawnPoint()
	local t = transform(p, yawOf(d) + 180)
	local eid = try("spawn " .. z.record, function() return exEntitySpawner.SpawnRecord(z.record, t) end)
	if not eid then
		eid = try("prevention spawn " .. z.record, function()
			return Game.GetPreventionSpawnSystem():RequestUnitSpawn(TweakDBID.new(z.record), t)
		end)
	end
	if not eid then return false end
	S.zombies[#S.zombies + 1] = { eid = eid, z = z, special = special, born = os.clock(), hostile = false, last = p }
	return true
end

local function makeHostile(zb, e)
	try("make hostile", function()
		local aa = e:GetAttitudeAgent()
		aa:SetAttitudeGroup(CName.new("hostile"))
		aa:SetAttitudeTowards(player():GetAttitudeAgent(), EAIAttitude.AIA_Hostile)
	end)
	zb.hostile = true
end

local function dropChip(p)
	S.chips[#S.chips + 1] = { pos = p, eid = spawnProp("chip", v4(p.x, p.y, p.z + 0.8), 0), born = os.clock() }
	say("A zombie dropped a cyberware chip", 3)
end

-- ---------------------------------------------------------------- match

local function startRound()
	S.round = S.round + 1
	S.toSpawn = rules.round_base + (S.round - 1) * rules.round_step
	S.bossPending = (S.round % rules.boss_every == 0)
	S.specialPending = true
	S.nextSpawn = os.clock() + 1
	S.state = "round"
	say("ROUND " .. S.round, 4)
	log("round %d: %d zombies%s", S.round, S.toSpawn, S.bossPending and " + boss" or "")
end

local function startMatch()
	local p = player()
	if not p then return end
	local c = pos(p)
	log("F7 at %.2f %.2f %.2f", c.x, c.y, c.z)
	S = { active = true, round = 0, points = rules.start_points, zombies = {}, chips = {}, given = {}, owned = {},
		cyber = {}, mods = {}, stashed = {} }
	math.randomseed(os.time())
	if #rowsOf("wallbuy") == 0 or #rowsOf("spawn") == 0 then
		say("No arena layout yet: open the CET overlay and use the Cyberpunk Kino layout window to place one.", 8)
		S.active = false
		return
	end
	local start = rowsOf("start")[1] or data.arena.h10
	local target = v4(start.x, start.y, start.z)
	try("teleport", function() Game.GetTeleportationFacility():Teleport(p, target, EulerAngles.new(0, 0, start.yaw)) end)
	S.state = "teleport"
	S.settleAt = os.clock() + rules.teleport_settle_s
	S.target = target
	say("Heading to V's apartment...", 3)
end

local function stopMatch(reason)
	if not S.active then return end
	log("match ends: %s (round %d, %d points)", reason, S.round or 0, S.points or 0)
	for _, zb in ipairs(S.zombies or {}) do despawn(zb.eid) end
	for _, ring in pairs(S.barricades or {}) do for _, b in ipairs(ring) do despawn(b.eid) end end
	for _, b in ipairs(S.buys or {}) do despawn(b.eid) end
	for _, ch in ipairs(S.chips or {}) do despawn(ch.eid) end
	removeCyber()
	for _, id in ipairs(S.given or {}) do remove(id) end
	unstashWeapons()
	restoreLoadout()
	S.active = false
	say(reason, 8)
end

local function nearestBuy()
	local p = pos(player())
	local best, bestD
	for _, b in ipairs(S.buys) do
		local d = flat(p, b.pos)
		if d <= rules.buy_radius_m and (not bestD or d < bestD) then best, bestD = b, d end
	end
	for _, ch in ipairs(S.chips) do
		local d = flat(p, ch.pos)
		if d <= rules.buy_radius_m and (not bestD or d < bestD) then best, bestD = { kind = "chip", chip = ch }, d end
	end
	return best
end

local function promptFor(b)
	if b.kind == "wall" then
		local cost = S.owned[b.weapon.id] and math.floor(b.weapon.cost / 2) or b.weapon.cost
		return string.format("[F] %s %s (%d)", S.owned[b.weapon.id] and "Ammo for" or "Buy", b.weapon.name, cost)
	elseif b.kind == "door" then
		return string.format("[F] Clear the barricade (%d)", doorCost(b.ring))
	elseif b.kind == "box" then
		return S.boxBusy and "Mystery Box..." or string.format("[F] Mystery Box (%d)", rules.box_cost)
	elseif b.kind == "chip" then
		return "[F] Install the cyberware chip"
	end
	return ""
end

local function pay(cost)
	if S.points < cost then
		say("Not enough points", 2)
		return false
	end
	S.points = S.points - cost
	return true
end

local function use()
	if not S.active then return end
	local b = nearestBuy()
	if not b then return end
	if b.kind == "wall" then
		local w = b.weapon
		if S.owned[w.id] then
			if pay(math.floor(w.cost / 2)) then Game.AddToInventory(w.ammo, w.ammo_amount) say(w.name .. " ammo", 2) end
		elseif pay(w.cost) then
			giveGun(w)
			say(w.name, 2)
		end
	elseif b.kind == "door" then
		if pay(doorCost(b.ring)) then
			openRing(b.ring)
			say("Barricade cleared: zone " .. S.zone, 3)
		end
	elseif b.kind == "box" and not S.boxBusy then
		local w = weightedBoxPick()
		if not w then say("You have every gun the box holds", 3) return end
		if pay(rules.box_cost) then
			S.boxBusy = { w = w, at = os.clock() + 2.5 }
			say("The Mystery Box is spinning...", 2.5)
		end
	elseif b.kind == "chip" then
		local nextC
		for _, c in ipairs(data.cyberware) do
			if not S.cyber[c.id] then nextC = nextC or {} nextC[#nextC + 1] = c end
		end
		if not nextC then say("All cyberware installed", 3) return end
		installCyber(nextC[math.random(#nextC)])
		despawn(b.chip.eid)
		for i, ch in ipairs(S.chips) do if ch == b.chip then table.remove(S.chips, i) break end end
	end
end

local function health()
	return try("health", function()
		return Game.GetStatPoolsSystem():GetStatPoolValue(player():GetEntityID(), gamedataStatPoolType.Health, true)
	end) or 100
end

local function tick()
	if not S.active then return end
	local p = player()
	if not p then return end
	local now = os.clock()

	if S.state == "teleport" then
		if now < S.settleAt then return end
		local here = pos(p)
		log("after the teleport V is at %.2f %.2f %.2f (%.1f m from the target)", here.x, here.y, here.z, flat(here, S.target))
		stashLoadout()
		stashWeapons()
		giveGun(data.weaponsById[data.startWeapon])
		buildArena()
		S.state = "break"
		S.nextRound = now + 4
		say("Cyberpunk Kino: survive. [F] buys, F7 ends the match.", 6)
		return
	end

	if S.sandeEnd and now >= S.sandeEnd then
		S.sandeEnd = nil
		try("end slow-mo", function() Game.GetTimeSystem():UnsetTimeDilation(CName.new("cyberkino")) end)
	end

	if health() < rules.end_health_pct then
		stopMatch(string.format("You went down on round %d with %d points.", S.round, S.points))
		try("heal", function()
			Game.GetStatPoolsSystem():RequestSettingStatPoolValue(p:GetEntityID(), gamedataStatPoolType.Health, 100, p, false)
		end)
		return
	end

	-- closed barricades hold: walking into one pushes V back to its inside, one step away
	local here = pos(p)
	for zone, list in pairs(S.barricades) do
		for _, bar in ipairs(list) do
			if flat(here, bar.pos) < rules.barricade_hold_m and math.abs(here.z - bar.pos.z) < 2.5 then
				local dx, dy = bar.inside.x - bar.pos.x, bar.inside.y - bar.pos.y
				local len = math.max(math.sqrt(dx * dx + dy * dy), 0.01)
				local back = v4(bar.pos.x + dx / len * (rules.barricade_hold_m + 0.3), bar.pos.y + dy / len * (rules.barricade_hold_m + 0.3), here.z)
				try("barricade push", function() Game.GetTeleportationFacility():Teleport(p, back, EulerAngles.new(0, 0, bar.yaw + 180)) end)
				if now > (S.pushSaid or 0) then say("Buy the barricade to get through", 2) S.pushSaid = now + 3 end
			end
		end
	end

	if S.boxBusy and now >= S.boxBusy.at then
		giveGun(S.boxBusy.w)
		say("Mystery Box: " .. S.boxBusy.w.name, 3)
		S.boxBusy = nil
		S.boxUses = S.boxUses + 1
		if S.boxUses >= rules.box_moves_after then S.boxUses = 0 moveBox() end
	end

	-- zombies: hostility, deaths, points
	for i = #S.zombies, 1, -1 do
		local zb = S.zombies[i]
		local e = Game.FindEntityByID(zb.eid)
		if e then
			if not zb.hostile then makeHostile(zb, e) end
			if e:IsDead() then
				if not zb.counted then
					zb.counted = true
					zb.deadAt = now
					S.points = S.points + rules.kill_points + (zb.special and rules.special_points or 0) + (zb.z.pool == "boss" and rules.boss_points or 0)
					if zb.special then dropChip(zb.last) end
				end
				if now - zb.deadAt > 4 then despawn(zb.eid) table.remove(S.zombies, i) end
			else
				zb.last = pos(e)
			end
		elseif now - zb.born > 15 then
			log("zombie %s never appeared; spawning another", zb.z.record)
			table.remove(S.zombies, i)
			S.toSpawn = S.toSpawn + 1
		end
	end
	local alive = 0
	for _, zb in ipairs(S.zombies) do if not zb.counted then alive = alive + 1 end end

	for i = #S.chips, 1, -1 do
		if now - S.chips[i].born > rules.chip_lifetime_s then
			despawn(S.chips[i].eid)
			table.remove(S.chips, i)
		end
	end

	if S.state == "break" and now >= S.nextRound then
		startRound()
	elseif S.state == "round" then
		if (S.toSpawn > 0 or S.bossPending) and alive < rules.max_active and now >= S.nextSpawn then
			S.nextSpawn = now + rules.spawn_interval_s
			if S.bossPending then
				if spawnZombie(data.boss, false) then S.bossPending = false say("A cyberpsycho is here", 3) end
			else
				local pool = zombiePool(S.round)
				if spawnZombie(pool[math.random(#pool)], S.specialPending) then
					S.toSpawn = S.toSpawn - 1
					S.specialPending = false
				end
			end
		elseif S.toSpawn <= 0 and not S.bossPending and alive == 0 then
			S.state = "break"
			S.nextRound = now + rules.round_break_s
			say("Round " .. S.round .. " survived", 3)
		end
	end

	local b = nearestBuy()
	hud.prompt = b and promptFor(b) or ""
end

-- ---------------------------------------------------------------- layout editor (CET overlay)

local ed = { open = false, zone = 1, gun = 1, preview = {} }

local function wallGuns()
	local list = {}
	for _, w in ipairs(data.weapons) do if w.role == "wall" then list[#list + 1] = w end end
	return list
end

local function propFor(kind)
	return ({ barricade = "barricade", wallbuy = "wallbuy", box = "box", spawn = "chip" })[kind]
end

local function facing()
	local p = player()
	local here = pos(p)
	local f = try("forward", function() return p:GetWorldForward() end) or { x = 0, y = 1 }
	local len = math.max(math.sqrt(f.x * f.x + f.y * f.y), 0.001)
	local dir = { x = f.x / len, y = f.y / len }
	return here, dir, yawOf(dir)
end

local function addRow(kind, ahead, extra)
	local here, dir, yaw = facing()
	local at = along(here, dir, ahead or 0)
	local n = #rowsOf(kind) + 1
	local row = { id = kind .. "_" .. n, kind = kind, x = at.x, y = at.y, z = at.z, yaw = yaw, zone = ed.zone,
		weapon = "none", inside_x = here.x, inside_y = here.y, inside_z = here.z, entity = "none" }
	for k, v in pairs(extra or {}) do row[k] = v end
	if kind == "start" or kind == "stash" then
		for i = #layout.rows, 1, -1 do if layout.rows[i].kind == kind then table.remove(layout.rows, i) end end
	end
	layout.rows[#layout.rows + 1] = row
	if propFor(kind) then ed.preview[#ed.preview + 1] = { row = row, eid = spawnProp(propFor(kind), at, yaw) } end
	saveLayout()
	say(string.format("Placed %s (zone %d)", row.id, ed.zone), 2)
end

local function undoRow()
	local row = table.remove(layout.rows)
	if not row then return end
	for i = #ed.preview, 1, -1 do
		if ed.preview[i].row == row then despawn(ed.preview[i].eid) table.remove(ed.preview, i) end
	end
	saveLayout()
	say("Removed " .. row.id, 2)
end

local function drawEditor()
	if not ImGui.Begin("Cyberpunk Kino layout") then ImGui.End() return end
	ImGui.Text(string.format("start %d | barricades %d | wall-buys %d | box spots %d | spawns %d | stash %d",
		#rowsOf("start"), #rowsOf("barricade"), #rowsOf("wallbuy"), #rowsOf("box"), #rowsOf("spawn"), #rowsOf("stash")))
	ImGui.Separator()
	if ImGui.Button("Match start: where V stands now") then addRow("start", 0) end
	ImGui.Text("Zone " .. ed.zone .. " (barricades open zone " .. (ed.zone + 1) .. "; spawns wake when their zone opens)")
	ImGui.SameLine()
	if ImGui.Button(" - ") then ed.zone = math.max(1, ed.zone - 1) end
	ImGui.SameLine()
	if ImGui.Button(" + ") then ed.zone = ed.zone + 1 end
	if ImGui.Button("Barricade 1.5 m in front of V (stand on the zone " .. ed.zone .. " side)") then addRow("barricade", 1.5) end
	local guns = wallGuns()
	ed.gun = math.max(1, math.min(ed.gun, #guns))
	if ImGui.Button(" < ") then ed.gun = (ed.gun - 2) % #guns + 1 end
	ImGui.SameLine()
	ImGui.Text(guns[ed.gun].name .. " (" .. guns[ed.gun].cost .. ")")
	ImGui.SameLine()
	if ImGui.Button(" > ") then ed.gun = ed.gun % #guns + 1 end
	if ImGui.Button("Wall-buy: face the wall, 0.6 m in front of V") then addRow("wallbuy", 0.6, { weapon = guns[ed.gun].id }) end
	if ImGui.Button("Mystery Box spot 1 m in front of V") then addRow("box", 1.0) end
	if ImGui.Button("Zombie spawn where V stands (zone " .. ed.zone .. ")") then addRow("spawn", 0) end
	if ImGui.Button("V's stash: look at it, then click") then
		local obj = try("look at", function() return Game.GetTargetingSystem():GetLookAtObject(player(), false, false) end)
		if obj then
			local h = tostring(obj:GetEntityID().hash)
			local op = pos(obj)
			addRow("stash", 0, { entity = h, x = op.x, y = op.y, z = op.z })
			log("stash recorded: %s (%s)", h, tostring(obj:GetClassName()))
		else
			say("Look straight at V's stash first", 3)
		end
	end
	ImGui.Separator()
	if ImGui.Button("Undo last") then undoRow() end
	ImGui.SameLine()
	ImGui.Text("Saved to mods\\cyberkino\\layout.json after every change.")
	ImGui.End()
end

-- ---------------------------------------------------------------- CET

registerHotkey("start", "Start / stop Zombies", function()
	if S.active then stopMatch("Match ended.") else startMatch() end
end)
registerHotkey("use", "Buy / pick up", use)
registerHotkey("sandevistan", "Sandevistan", sandevistan)

registerForEvent("onOverlayOpen", function() ed.open = true end)
registerForEvent("onOverlayClose", function()
	ed.open = false
	for _, pv in ipairs(ed.preview) do despawn(pv.eid) end
	ed.preview = {}
end)

registerForEvent("onInit", function()
	loadLayout()
	log("Cyberpunk Kino %s loaded (%d guns, %d zombie types)", data.version, #data.weapons, #data.zombies)
end)

registerForEvent("onUpdate", function()
	local ok, err = pcall(tick)
	if not ok then log("tick error: %s", tostring(err)) end
end)

registerForEvent("onDraw", function()
	if ed.open and not S.active then
		local ok, err = pcall(drawEditor)
		if not ok then log("layout editor error: %s", tostring(err)) end
	end
	if not S.active and os.clock() > hud.msgUntil then return end
	ImGui.SetNextWindowPos(30, 260, ImGuiCond.Always)
	ImGui.PushStyleColor(ImGuiCol.WindowBg, 0, 0, 0, 0.45)
	if ImGui.Begin("Cyberpunk Kino", ImGuiWindowFlags.NoTitleBar + ImGuiWindowFlags.AlwaysAutoResize + ImGuiWindowFlags.NoMove + ImGuiWindowFlags.NoInputs) then
		if S.active then
			ImGui.SetWindowFontScale(1.6)
			ImGui.TextColored(0.9, 0.15, 0.15, 1, "ROUND " .. tostring(S.round))
			ImGui.SetWindowFontScale(1.2)
			ImGui.Text(tostring(S.points) .. " points")
			local list = {}
			for _, c in ipairs(data.cyberware) do if S.cyber[c.id] then list[#list + 1] = c.name end end
			if #list > 0 then ImGui.TextColored(0.35, 1, 0.9, 1, table.concat(list, " / ")) end
			if hud.prompt ~= "" then ImGui.TextColored(1, 0.85, 0.3, 1, hud.prompt) end
		end
		if os.clock() < hud.msgUntil then ImGui.Text(hud.msg) end
		ImGui.SetWindowFontScale(1.0)
	end
	ImGui.End()
	ImGui.PopStyleColor(1)
end)

registerForEvent("onShutdown", function()
	pcall(stopMatch, "CET shut down")
end)
