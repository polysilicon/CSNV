-- Crab Champions-style HUD and shop, drawn with CET's ImGui. Icons are the PNGs the bridge extracted from
-- the player's own Crab Champions paks (crab/...); they load lazily because ImGui.LoadTexture only works in onDraw.
local shop = require("shop")
local perks = require("perks")
local M = { tex = {}, missing = {} }

local FLAGS
local function flags()
  if not FLAGS then
    FLAGS = ImGuiWindowFlags.NoDecoration + ImGuiWindowFlags.NoInputs + ImGuiWindowFlags.NoNav
          + ImGuiWindowFlags.NoSavedSettings + ImGuiWindowFlags.AlwaysAutoResize + ImGuiWindowFlags.NoFocusOnAppearing
  end
  return FLAGS
end

-- Crab Champions palette: sea blue panels, crystal cyan, sand yellow
local C = {
  panel = { 0.03, 0.18, 0.33, 0.82 }, crystal = { 0.35, 0.95, 1.0, 1 }, sand = { 1.0, 0.86, 0.32, 1 },
  white = { 1, 1, 1, 1 }, red = { 1.0, 0.36, 0.33, 1 }, dim = { 0.75, 0.85, 0.95, 1 }, sold = { 0.5, 0.5, 0.5, 1 },
}

function M.texture(path)
  if not path or M.missing[path] then return nil end
  local t = M.tex[path]
  if t then return t end
  local ok, tex = pcall(ImGui.LoadTexture, path)
  if ok and tex then M.tex[path] = tex return tex end
  M.missing[path] = true
  return nil
end

local function text(col, s)
  ImGui.PushStyleColor(ImGuiCol.Text, col[1], col[2], col[3], col[4])
  ImGui.Text(s)
  ImGui.PopStyleColor(1)
end

local function begin_panel(name, x, y, pivotx, pivoty, scale)
  ImGui.SetNextWindowPos(x, y, ImGuiCond.Always, pivotx or 0, pivoty or 0)
  ImGui.PushStyleColor(ImGuiCol.WindowBg, C.panel[1], C.panel[2], C.panel[3], C.panel[4])
  ImGui.PushStyleVar(ImGuiStyleVar.WindowRounding, 14)
  ImGui.PushStyleVar(ImGuiStyleVar.WindowPadding, 14, 10)
  local open = ImGui.Begin(name, flags())
  ImGui.SetWindowFontScale(scale or 1.6)
  return open
end

local function end_panel()
  ImGui.End()
  ImGui.PopStyleVar(2)
  ImGui.PopStyleColor(1)
end

local function icon(path, size)
  local t = M.texture(path)
  if t then ImGui.Image(t, ImVec2.new(size, size)) ImGui.SameLine() return true end
  return false
end

local function fmt_time(t)
  t = math.floor(t or 0)
  return string.format("%d:%02d", math.floor(t / 60), t % 60)
end

function M.draw(R, crab, bridge_ok)
  local W, H = GetDisplayResolution()
  local s = R.state
  local crystal_icon = crab and crab.art and crab.art.crystal_icon

  if s ~= "idle" and s ~= "over" then
    -- top left: island / wave / time
    if begin_panel("##crabrun_wave", 24, 24) then
      local st = R.stage_order and R.stage_order[R.stage_i]
      text(C.sand, string.format("ISLAND %d  ·  WAVE %d", R.stage_i or 1, math.max(R.wave, 1)))
      text(C.dim, (st and st.name or "") .. "   " .. fmt_time(R.time))
      if s == "wave" then
        text(C.white, string.format("Enemies left: %d", #R.queue + require("run").alive_count(R)))
      end
      text(C.dim, "Seed " .. tostring(R.seed))
    end
    end_panel()
    -- top right: crystals
    if begin_panel("##crabrun_crystals", W - 24, 24, 1, 0, 2.0) then
      icon(crystal_icon, 40)
      text(C.crystal, tostring(R.crystals))
    end
    end_panel()
    -- bottom left: owned Crab perks with stacks
    local owned = {}
    for _, row in ipairs(R.data.crab_perks) do
      local n = perks.stacks(R.perks, row.key)
      if n > 0 then owned[#owned + 1] = { row = row, n = n } end
    end
    if #owned > 0 and begin_panel("##crabrun_perks", 24, H - 24, 0, 1, 1.2) then
      for i, o in ipairs(owned) do
        local p = crab and crab.perks and crab.perks[o.row.key]
        if not icon(p and p.icon, 36) then text(C.sand, "*") ImGui.SameLine() end
        text(C.white, (p and p.name or o.row.fallback_name) .. (o.n > 1 and (" x" .. o.n) or ""))
        if i % 4 ~= 0 and i < #owned then ImGui.SameLine() end
      end
    end
    if #owned > 0 then end_panel() end
  end

  if s == "countdown" and R.t then
    if begin_panel("##crabrun_count", W / 2, H * 0.32, 0.5, 0.5, 4.0) then
      text(C.sand, tostring(math.max(1, math.ceil(R.t))))
    end
    end_panel()
  end

  if s == "shop" and R.shop then M.draw_shop(R, crab, W, H, crystal_icon) end

  if R.banner then
    if begin_panel("##crabrun_banner", W / 2, H * 0.18, 0.5, 0.5, 3.0) then
      text(C.sand, R.banner.text)
      if R.banner.sub then ImGui.SetWindowFontScale(1.6) text(C.white, R.banner.sub) end
    end
    end_panel()
  end

  if s == "over" and R.last then
    if begin_panel("##crabrun_over", W / 2, H * 0.62, 0.5, 0.5, 1.6) then
      text(C.sand, string.format("Reached wave %d  ·  %d kills  ·  %s", R.last.wave, R.last.kills, fmt_time(R.last.time)))
      text(C.dim, string.format("Best: wave %d (seed %s)", R.best.wave or 0, tostring(R.best.seed or "-")))
      text(C.white, "F8  new run      F7  type a friend's seed")
    end
    end_panel()
  end

  if R.seed_input then
    if begin_panel("##crabrun_seed", W / 2, H * 0.45, 0.5, 0.5, 2.2) then
      text(C.sand, "SEED: " .. R.seed_input .. string.rep("_", R.data.systems.seed_length - #R.seed_input))
      ImGui.SetWindowFontScale(1.3)
      text(C.dim, "Type the code, Enter to start, F7 to cancel")
    end
    end_panel()
  end

  if not bridge_ok and s ~= "idle" then
    if begin_panel("##crabrun_nobridge", W / 2, H - 24, 0.5, 1, 1.2) then
      text(C.red, "Crab Run's launcher isn't running: start Crab Run from Melty for shop keys and Crab sounds.")
    end
    end_panel()
  end
end

function M.draw_shop(R, crab, W, H, crystal_icon)
  if not begin_panel("##crabrun_shop", W / 2, H / 2, 0.5, 0.5, 1.5) then end_panel() return end
  ImGui.SetWindowFontScale(2.2)
  text(C.sand, "CRYSTAL SHOP")
  ImGui.SameLine()
  icon(crystal_icon, 32)
  text(C.crystal, tostring(R.crystals))
  ImGui.SetWindowFontScale(1.4)
  for slot, c in ipairs(R.shop.cards) do
    ImGui.Separator()
    if not c then
      text(C.dim, string.format("[%d]  -", slot))
    else
      local name, desc, ic
      if c.kind == "perk" then
        local p = crab and crab.perks and crab.perks[c.id]
        name = p and p.name or c.row.fallback_name
        desc = p and p.desc or ""
        ic = p and p.icon
      else
        name = R.names[c.row.record] or c.id
        desc = c.kind == "cyberware" and "Cyberpunk cyberware" or (c.row.iconic and "Iconic Cyberpunk weapon" or "Cyberpunk weapon")
      end
      local col = c.sold and C.sold or (R.crystals >= c.price and C.white or C.red)
      text(C.sand, string.format("[%d]", slot)) ImGui.SameLine()
      icon(ic, 40)
      text(col, name .. (c.sold and "  (bought)" or ""))
      ImGui.SameLine()
      text(C.crystal, "   " .. c.price)
      if desc ~= "" then
        ImGui.SetWindowFontScale(1.1) text(C.dim, "      " .. desc) ImGui.SetWindowFontScale(1.4)
      end
    end
  end
  ImGui.Separator()
  text(C.white, string.format("1-6 buy   R reroll (%d)   Enter continue   %ds", shop.reroll_price(R), math.ceil(R.shop.t)))
  end_panel()
end

return M
