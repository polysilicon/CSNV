-- Every Cyberpunk call Crab Run makes goes through here (sheets/hooks.json lists each one and where its
-- signature was checked). Each call is guarded: a failure is logged once and the run carries on.
local M = { errors = {} }

local function try(name, f, ...)
  local ok, a, b = pcall(f, ...)
  if not ok then
    if not M.errors[name] then
      M.errors[name] = true
      print("[CrabRun] " .. name .. " failed: " .. tostring(a))
    end
    return nil
  end
  return a, b
end
M.try = try

function M.player() return Game.GetPlayer() end

function M.session_ok()
  return try("session", function()
    local p = Game.GetPlayer()
    if not p then return false end
    local h = Game.GetSystemRequestsHandler()
    if h and h:IsPreGame() then return false end
    return true
  end) or false
end

function M.is_paused()
  return try("paused", function() return Game.GetTimeSystem():IsPausedState() end) or false
end

local function v3(v) return { x = v.x, y = v.y, z = v.z } end

function M.player_pos()
  return try("player_pos", function() return v3(Game.GetPlayer():GetWorldPosition()) end)
end

function M.player_yaw()
  return try("player_yaw", function() return Game.GetPlayer():GetWorldOrientation():ToEulerAngles().yaw end) or 0
end

function M.health_pct()
  return try("health", function()
    local p = Game.GetPlayer()
    return Game.GetStatPoolsSystem():GetStatPoolValue(p:GetEntityID(), gamedataStatPoolType.Health, true)
  end) or 100
end

function M.heal_pct(pct)
  try("heal", function()
    local p = Game.GetPlayer()
    Game.GetStatPoolsSystem():RequestChangingStatPoolValue(p:GetEntityID(), gamedataStatPoolType.Health, pct, p, false, true)
  end)
end

function M.set_immortal(on)
  try("godmode", function()
    local id = Game.GetPlayer():GetEntityID()
    local gm = Game.GetGodModeSystem()
    if on then gm:AddGodMode(id, gameGodModeType.Immortal, CName.new("CrabRun"))
    else gm:RemoveGodMode(id, gameGodModeType.Immortal, CName.new("CrabRun")) end
  end)
end

function M.teleport_player(x, y, z, yaw)
  try("teleport", function()
    Game.GetTeleportationFacility():Teleport(Game.GetPlayer(), Vector4.new(x, y, z, 1), EulerAngles.new(0, 0, yaw or 0))
  end)
end

-- a point on the human navmesh roughly `r` metres from center in direction `angle` (radians)
function M.find_spawn_point(center, angle, r)
  return try("navmesh", function()
    local probe = Vector4.new(center.x + math.cos(angle) * r, center.y + math.sin(angle) * r, center.z + 1.5, 1)
    local res = Game.GetNavigationSystem():FindPointInSphereOnlyHumanNavmesh(probe, 6.0, NavGenAgentSize.Human, false)
    if res and res.status == worldNavigationRequestStatus.OK then
      return v3(res.point)
    end
    return nil
  end)
end

function M.spawn_npc(record, pos, yaw)
  return try("spawn", function()
    local spec = DynamicEntitySpec.new()
    spec.recordID = record
    spec.position = Vector4.new(pos.x, pos.y, pos.z, 1)
    spec.orientation = EulerAngles.new(0, 0, yaw or 0):ToQuat()
    spec.alwaysSpawned = true
    spec.tags = { "CrabRun" }
    return Game.GetDynamicEntitySystem():CreateEntity(spec)
  end)
end

function M.get_entity(id)
  return try("get_entity", function() return Game.GetDynamicEntitySystem():GetEntity(id) end)
end

function M.despawn(id)
  try("despawn", function() Game.GetDynamicEntitySystem():DeleteEntity(id) end)
end

-- AMM's SetHostileRole / TriggerCombatAgainst, trimmed to "fight V"
function M.make_hostile(h)
  return try("hostile", function()
    local player = Game.GetPlayer()
    h:GetAIControllerComponent():SetAIRole(AIRole.new())
    h:GetAIControllerComponent():OnAttach()
    h:GetAttitudeAgent():SetAttitudeGroup(CName.new("hostile"))
    h:GetAttitudeAgent():SetAttitudeTowards(player:GetAttitudeAgent(), EAIAttitude.AIA_Hostile)
    local preset = TweakDBInterface.GetReactionPresetRecord(TweakDBID.new("ReactionPresets.Ganger_Aggressive"))
    if preset then h.reactionComponent:SetReactionPreset(preset) end
    h.reactionComponent:TriggerCombat(player)
    return true
  end) or false
end

function M.is_dead(h)
  return try("is_dead", function() return h:IsDead() or h:IsDefeated() end) or false
end

function M.entity_pos(h)
  return try("entity_pos", function() return v3(h:GetWorldPosition()) end)
end

function M.apply_status(h, status)
  try("status", function()
    Game.GetStatusEffectSystem():ApplyStatusEffect(h:GetEntityID(), TweakDBID.new(status))
  end)
end

function M.add_stat(stat, mod, value)
  return try("stat_mod", function()
    local m = RPGManager.CreateStatModifier(gamedataStatType[stat], gameStatModifierType[mod], value)
    Game.GetStatsSystem():AddModifier(Game.GetPlayer():GetEntityID(), m)
    return m
  end)
end

function M.remove_stat(m)
  try("stat_mod_remove", function() Game.GetStatsSystem():RemoveModifier(Game.GetPlayer():GetEntityID(), m) end)
end

function M.record_ok(rec)
  return try("record", function() return TweakDB:GetRecord(rec) ~= nil end) or false
end

function M.item_name(rec)
  return try("item_name", function()
    local r = TweakDB:GetRecord(rec)
    local n = r and Game.GetLocalizedTextByKey(r:DisplayName())
    if n and n ~= "" then return n end
    return nil
  end)
end

function M.give_item(rec)
  return try("give_item", function()
    local id = ItemID.FromTDBID(TweakDBID.new(rec))
    Game.GetTransactionSystem():GiveItem(Game.GetPlayer(), id, 1)
    return id
  end)
end

function M.remove_item(itemID)
  try("remove_item", function() Game.GetTransactionSystem():RemoveItem(Game.GetPlayer(), itemID, 1) end)
end

function M.remove_record(rec)
  try("remove_record", function()
    local ts, p = Game.GetTransactionSystem(), Game.GetPlayer()
    local id = ItemID.FromTDBID(TweakDBID.new(rec))
    if ts:GetItemQuantity(p, id) > 0 then ts:RemoveItem(p, id, 1) end
  end)
end

local function eqsys() return Game.GetScriptableSystemsContainer():Get("EquipmentSystem") end

function M.equip(itemID)
  try("equip", function()
    local req = EquipRequest.new()
    req.owner = Game.GetPlayer()
    req.itemID = itemID
    req.addToInventory = false
    eqsys():QueueRequest(req)
  end)
end

function M.unequip(area, slot)
  try("unequip", function()
    local req = UnequipRequest.new()
    req.owner = Game.GetPlayer()
    req.areaType = gamedataEquipmentArea[area]
    req.slotIndex = slot
    eqsys():QueueRequest(req)
  end)
end

-- {slot = ItemID} for an equipment area
function M.equipped(area)
  return try("equip_query", function()
    local data = EquipmentSystem.GetData(Game.GetPlayer())
    local a = gamedataEquipmentArea[area]
    local out = {}
    for i = 0, data:GetNumberOfSlots(a) - 1 do
      local id = data:GetItemInEquipSlot(a, i)
      if id and ItemID.IsValid(id) then out[i] = id end
    end
    return out
  end) or {}
end

function M.time_dilation(on, value)
  try("time_dilation", function()
    local ts = Game.GetTimeSystem()
    if on then ts:SetTimeDilation(CName.new("CrabRunShop"), value)
    else ts:UnsetTimeDilation(CName.new("CrabRunShop")) end
  end)
end

return M
