local M = {}

function M.index(rows, key)
  local t = {}
  for _, r in ipairs(rows) do t[r[key]] = r end
  return t
end

function M.filter(rows, f)
  local t = {}
  for _, r in ipairs(rows) do if f(r) then t[#t + 1] = r end end
  return t
end

function M.clamp(v, a, b) if v < a then return a elseif v > b then return b end return v end

function M.dist(a, b)
  local dx, dy, dz = a.x - b.x, a.y - b.y, a.z - b.z
  return math.sqrt(dx * dx + dy * dy + dz * dz)
end

function M.write_file(path, text)
  local f = io.open(path, "w")
  if not f then return false end
  f:write(text)
  f:close()
  return true
end

function M.read_file(path)
  local f = io.open(path, "r")
  if not f then return nil end
  local s = f:read("*a")
  f:close()
  return s
end

-- JSON files (CET provides a global json with encode/decode)
function M.load_json(path)
  local s = M.read_file(path)
  if not s or s == "" then return nil end
  local ok, v = pcall(json.decode, s)
  if ok then return v end
  return nil
end

function M.save_json(path, v)
  return M.write_file(path, json.encode(v))
end

return M
