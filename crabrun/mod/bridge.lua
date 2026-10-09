-- File channel to CrabRunBridge.exe (CET only lets Lua touch files inside its own mod folder, so the
-- bridge, which Melty starts, meets us there).
--   io/events.txt  Lua -> bridge: one run event per line ("crystal", "buy", ...); the bridge plays the Crab sound
--   io/keys.txt    bridge -> Lua: "<seq> <action> [char]" lines for keys pressed while Cyberpunk is in front
--   io/alive.txt   bridge -> Lua: unix time, rewritten every second while the bridge runs
local util = require("util")
local M = { seq = 0, poll = 0, pending = {} }

function M.init()
  util.write_file("io/events.txt", "")
  M.seq = 0
  local s = util.read_file("io/keys.txt")
  if s then for n in s:gmatch("(%d+) [^\n]*\n") do M.seq = math.max(M.seq, tonumber(n)) end end
end

function M.emit(ev)
  M.pending[#M.pending + 1] = ev
end

function M.flush()
  if #M.pending == 0 then return end
  local f = io.open("io/events.txt", "a")
  if f then
    f:write(table.concat(M.pending, "\n") .. "\n")
    f:close()
  end
  M.pending = {}
end

-- returns list of {action, char}
function M.read_keys(dt)
  M.poll = M.poll + dt
  if M.poll < 0.05 then return {} end
  M.poll = 0
  local s = util.read_file("io/keys.txt")
  local out = {}
  if not s then return out end
  local maxseq = 0
  for n, action, char in s:gmatch("(%d+) (%S+) ?(%S*)\n") do
    n = tonumber(n)
    maxseq = math.max(maxseq, n)
    if n > M.seq then out[#out + 1] = { action = action, char = char ~= "" and char or nil }; M.seq = n end
  end
  if maxseq < M.seq then M.seq = maxseq end   -- bridge restarted and began counting again
  return out
end

function M.alive()
  local s = util.read_file("io/alive.txt")
  local t = s and tonumber(s:match("%d+"))
  return t ~= nil and math.abs(os.time() - t) < 5
end

return M
