-- Loads init.lua the way CET does (in the mod folder, with registerForEvent/ImGui/Observe), drives a session,
-- and checks the HUD keeps ImGui Begin/End and Push/Pop balanced in every state.
package.path = "./?.lua;lib/?.lua;" .. package.path
json = require("json")
local mock = dofile("mockgame.lua")
local TESTS = io.popen("pwd"):read("*l")
local tmp = os.tmpname() os.remove(tmp)
os.execute("mkdir -p " .. tmp .. "/io " .. tmp .. "/crab/icons && cp ../mod/*.lua " .. tmp .. "/")
-- run from inside a scratch copy of the mod folder, as CET does
local handlers, observers = {}, {}
function registerForEvent(ev, f) handlers[ev] = f end
function Observe(cls, fn, f) observers[cls .. "." .. fn] = f end
local depth, styles, vars, begun = 0, 0, 0, 0
ImGuiWindowFlags = setmetatable({}, { __index = function() return 1 end })
ImGuiCol = setmetatable({}, { __index = function() return 1 end })
ImGuiStyleVar = setmetatable({}, { __index = function() return 1 end })
ImGuiCond = { Always = 1 }
ImVec2 = { new = function(x, y) return { x = x, y = y } end }
ImGui = {
  Begin = function() depth = depth + 1 begun = begun + 1 return true end,
  End = function() depth = depth - 1 end,
  PushStyleColor = function() styles = styles + 1 end, PopStyleColor = function(n) styles = styles - (n or 1) end,
  PushStyleVar = function() vars = vars + 1 end, PopStyleVar = function(n) vars = vars - (n or 1) end,
  SetNextWindowPos = function() end, SetWindowFontScale = function() end, Text = function() end,
  SameLine = function() end, Separator = function() end, Image = function() end,
  LoadTexture = function(p) local f = io.open(p) if f then f:close() return { p = p } end return nil end,
}
function GetDisplayResolution() return 1920, 1080 end
local g = mock.new()
package.loaded.game = g
local cwd_ok = package.path
package.path = tmp .. "/?.lua;" .. package.path
-- CET resolves relative io paths against the mod folder: emulate by chdir via a wrapper
local real_open = io.open
io.open = function(p, m) if not p:match("^/") then p = tmp .. "/" .. p end return real_open(p, m) end

local function put(p, s, m) local f = io.open(p, m or "w") f:write(s) f:close() end
local pass, fail = 0, 0
local function check(n, c, m) if c then pass = pass + 1 else fail = fail + 1 print("FAIL " .. n .. (m and (": " .. tostring(m)) or "")) end end

-- the bridge's extracted content and a live heartbeat
local f = io.open("crab/crab_data.json", "w")
f:write(json.encode({ ok = true, source = "test", perks = { Vitality = { name = "Vitality", desc = "More health", icon = "crab/icons/Vitality.png" } },
  art = { crystal_icon = "crab/art/crystal_icon.png" } })) f:close()
local f2 = io.open("crab/icons/Vitality.png", "w") if f2 then f2:write("x") f2:close() end
put("io/alive.txt", tostring(os.time()))

dofile(tmp .. "/init.lua")
check("events registered", handlers.onInit and handlers.onUpdate and handlers.onDraw and handlers.onShutdown)
handlers.onInit()
check("observer", observers["PlayerPuppet.OnGameAttached"] ~= nil)
local function frame(dt) handlers.onUpdate(dt) handlers.onDraw()
  check("balanced", depth == 0 and styles == 0 and vars == 0, depth .. "/" .. styles .. "/" .. vars) end
for _ = 1, 40 do frame(0.1) end -- 3s settle then the run starts
local log = io.open("crabrun.log"):read("*a")
check("run started", log:find("run started, seed") ~= nil, log)
check("crab content read", log:find("Crab Champions content: 1 perks") ~= nil, log)
for _ = 1, 80 do frame(0.1) end
check("hud drew windows", begun > 10)
-- keys relayed by the bridge: end the run, then start a new one
put("io/keys.txt", "1 end_run\n")
for _ = 1, 3 do frame(0.1) end
local ev = io.open("io/events.txt"):read("*a")
check("events written for bridge", ev:find("portal") ~= nil, ev)
put("io/keys.txt", "2 new_run\n", "a")
for _ = 1, 3 do frame(0.1) end
-- reload: OnGameAttached resets and starts a fresh run after settling
observers["PlayerPuppet.OnGameAttached"]()
for _ = 1, 40 do frame(0.1) end
local n = 0 for _ in io.open("crabrun.log"):read("*a"):gmatch("run started") do n = n + 1 end
check("fresh run on reload", n == 2, n)
handlers.onShutdown()
os.execute("rm -rf " .. tmp)
print(string.format("%d passed, %d failed", pass, fail))
os.exit(fail == 0 and 0 or 1)
