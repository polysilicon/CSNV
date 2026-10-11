-- Cyberpunk Kino: Black Ops-style Zombies in Megabuilding H10.
-- Press F7 (CET binding "start") on V's floor: barricades close the corridors in rings, wall-buys go on the
-- walls, the Mystery Box in the open, and Scavenger and Maelstrom zombies come in rounds. V starts with only a
-- Unity; everything V is carrying comes back when the match ends. Data comes from data.lua (generated from
-- sheets/*.json by tools/build.py). Every step is written to cyberkino.log next to this file.

local data = require("data")
local rules = data.rules

local S = { active = false }
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

local DIRS = {}
for i = 0, 15 do
	local a = i * math.pi / 8
	DIRS[#DIRS + 1] = { x = math.cos(a), y = math.sin(a) }
end

-- distance to the first static obstacle from c along dir (chest height), or nil within maxd
local function rayDist(c, dir, maxd)
	local from = v4(c.x, c.y, c.z + 1.0)
	local to = v4(c.x + dir.x * maxd, c.y + dir.y * maxd, c.z + 1.0)
	local hit, res = try("raycast", function()
		return Game.GetSpatialQueriesSystem():SyncRaycastByCollisionGroup(from, to, CName.new("Static"), false, false)
	end)
	if hit and res and res.position then
		local p = res.position
		return math.sqrt((p.x - from.x) ^ 2 + (p.y - from.y) ^ 2)
	end
	return nil
end

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

local function equip(itemID)
	try("equip", function()
		local req = EquipRequest.new()
		req.owner = player()
		req.itemID = itemID
		equipmentSystem():QueueRequest(req)
	end)
end

local function remove(itemID)
	try("remove item", function() Game.GetTransactionSystem():RemoveItem(player(), itemID, 1) end)
end

-- remembers and takes off V's weapons, so the match starts with the Unity only
local function stashWeapons()
	S.stashed = {}
	local pd = try("player data", function() return equipmentSystem():GetPlayerData(player()) end)
	for slot = 0, 2 do
		local id = pd and try("weapon slot", function() return pd:GetItemInEquipSlot(gamedataEquipmentArea.Weapon, slot) end)
		if id and ItemID.IsValid(id) then
			S.stashed[#S.stashed + 1] = id
			try("unequip", function()
				local req = UnequipRequest.new()
				req.owner = player()
				req.areaType = gamedataEquipmentArea.Weapon
				req.slotIndex = slot
				equipmentSystem():QueueRequest(req)
			end)
		end
	end
	log("took off %d weapons", #S.stashed)
end

local function restoreWeapons()
	for _, id in ipairs(S.stashed or {}) do equip(id) end
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

local function zoneRadius(z) return rules.zone_radius_1 + (z - 1) * rules.zone_radius_step end

local function buildArena(c)
	S.center = c
	S.zone = 1
	S.barricades = {} -- ring -> list of {eid, pos}
	S.buys = {}       -- {kind, pos, eid, weapon|ring}
	local wallGuns = {}
	for _, w in ipairs(data.weapons) do if w.role == "wall" then wallGuns[#wallGuns + 1] = w end end

	local free = {}
	for i, d in ipairs(DIRS) do
		free[i] = rayDist(c, d, zoneRadius(rules.zones) + rules.spawn_max_m) or 999
	end
	-- barricades where a ring crosses an opening
	for ring = 1, rules.zones - 1 do
		local r = zoneRadius(ring)
		S.barricades[ring] = {}
		for i, d in ipairs(DIRS) do
			if free[i] > r + 0.5 then
				local p = along(c, d, r)
				local eid = spawnProp("barricade", p, yawOf(d))
				table.insert(S.barricades[ring], { eid = eid, pos = p })
			end
		end
		if #S.barricades[ring] > 0 then
			S.buys[#S.buys + 1] = { kind = "door", ring = ring, pos = S.barricades[ring][1].pos }
		end
	end
	-- a ring with no opening needs no barricade: the zones on both sides of it are one
	while S.zone < rules.zones and #(S.barricades[S.zone] or {}) == 0 do
		S.zone = S.zone + 1
	end
	-- wall-buys on walls found inside the zones, nearest zone first
	local spots = {}
	for i, d in ipairs(DIRS) do
		if free[i] < zoneRadius(rules.zones) then
			spots[#spots + 1] = { d = d, dist = free[i] }
		end
	end
	table.sort(spots, function(a, b) return a.dist < b.dist end)
	for k, w in ipairs(wallGuns) do
		local s = spots[k]
		local p, yaw
		if s then
			p = along(c, s.d, math.max(s.dist - 0.6, 1.0))
			yaw = yawOf(s.d)
		else
			local d = DIRS[(k * 5) % #DIRS + 1]
			p = along(c, d, math.min(3 + k, zoneRadius(1) - 1))
			yaw = yawOf(d)
		end
		local eid = spawnProp("wallbuy", p, yaw)
		S.buys[#S.buys + 1] = { kind = "wall", weapon = w, pos = p, eid = eid }
	end
	-- the Mystery Box in the most open direction of zone 1
	local best, bestFree = DIRS[1], -1
	for i, d in ipairs(DIRS) do
		if free[i] > bestFree then best, bestFree = d, free[i] end
	end
	local bp = along(c, best, math.min(bestFree * 0.5, zoneRadius(1) - 2))
	S.buys[#S.buys + 1] = { kind = "box", pos = bp, eid = spawnProp("box", bp, yawOf(best)) }
	S.free = free
	log("arena at %.1f %.1f %.1f: openings per ring %s, %d walls found, box %.1fm out",
		c.x, c.y, c.z, (function()
			local t = {}
			for ring = 1, rules.zones - 1 do t[#t + 1] = tostring(#S.barricades[ring]) end
			return table.concat(t, "/")
		end)(), #spots, bestFree)
end

local function openRing(ring)
	for _, b in ipairs(S.barricades[ring] or {}) do despawn(b.eid) end
	S.barricades[ring] = {}
	S.zone = math.max(S.zone, ring + 1)
	while S.zone < rules.zones and #(S.barricades[S.zone] or {}) == 0 do
		S.zone = S.zone + 1
	end
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
	local c, r = S.center, zoneRadius(S.zone)
	local tries = {}
	for i, d in ipairs(DIRS) do
		if S.free[i] > r + rules.spawn_min_m then tries[#tries + 1] = { d = d, max = S.free[i] } end
	end
	if #tries == 0 then
		for _, d in ipairs(DIRS) do tries[#tries + 1] = { d = d, max = r + rules.spawn_max_m } end
	end
	local t = tries[math.random(#tries)]
	local dist = math.min(r + rules.spawn_min_m + math.random() * (rules.spawn_max_m - rules.spawn_min_m), t.max - 1)
	return along(c, t.d, math.max(dist, r + 1), 0.2), t.d
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
	local h10 = data.arena.h10
	local away = flat(c, v4(h10.x, h10.y, h10.z))
	log("F7 at %.2f %.2f %.2f (%.0f m from the H10 anchor)", c.x, c.y, c.z, away)
	if away > rules.h10_radius_m then
		say("Cyberpunk Kino is made for Megabuilding H10 (V's floor). Starting here anyway.", 6)
	end
	S = { active = true, round = 0, points = rules.start_points, zombies = {}, chips = {}, given = {}, owned = {},
		cyber = {}, mods = {}, stashed = {} }
	math.randomseed(os.time())
	stashWeapons()
	giveGun(data.weaponsById[data.startWeapon])
	buildArena(c)
	S.state = "break"
	S.nextRound = os.clock() + 4
	say("Cyberpunk Kino: survive. [F] buys, F7 ends the match.", 6)
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
	restoreWeapons()
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

	-- keep V inside the open zones
	local here = pos(p)
	local r = zoneRadius(S.zone)
	local d = flat(here, S.center)
	if d > r + 1.5 then
		local dir = { x = (here.x - S.center.x) / d, y = (here.y - S.center.y) / d }
		try("keep in zone", function()
			Game.GetTeleportationFacility():Teleport(p, along(S.center, dir, r - 0.5, here.z - S.center.z), EulerAngles.new(0, 0, yawOf(dir) + 180))
		end)
		say("A barricade blocks the way: buy it to go further", 2)
	end

	if S.boxBusy and now >= S.boxBusy.at then
		giveGun(S.boxBusy.w)
		say("Mystery Box: " .. S.boxBusy.w.name, 3)
		S.boxBusy = nil
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

-- ---------------------------------------------------------------- CET

registerHotkey("start", "Start / stop Zombies", function()
	if S.active then stopMatch("Match ended.") else startMatch() end
end)
registerHotkey("use", "Buy / pick up", use)
registerHotkey("sandevistan", "Sandevistan", sandevistan)

registerForEvent("onInit", function()
	log("Cyberpunk Kino %s loaded (%d guns, %d zombie types)", data.version, #data.weapons, #data.zombies)
end)

registerForEvent("onUpdate", function()
	local ok, err = pcall(tick)
	if not ok then log("tick error: %s", tostring(err)) end
end)

registerForEvent("onDraw", function()
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
