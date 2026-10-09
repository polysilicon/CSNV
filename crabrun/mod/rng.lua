-- Seeded RNG (xorshift32) so a run seed gives the same waves, islands and shop rolls everywhere.
local bit = bit32 or require("bit")  -- CET provides bit32; plain LuaJIT has bit
local U32 = 4294967296
local function u32(x) return x % U32 end
local M = {}
M.__index = M

local function hash(s)
  local h = 5381
  for i = 1, #s do
    h = (h * 33 + s:byte(i)) % U32          -- djb2, kept below 2^38 so doubles stay exact
  end
  h = u32(bit.bxor(h, bit.rshift(h, 16)))
  if h == 0 then h = 1 end
  return h
end
M.hash = hash

function M.new(seed)
  return setmetatable({ s = hash(seed) }, M)
end

function M:next()
  local x = self.s
  x = u32(bit.bxor(x, u32(bit.lshift(x, 13))))
  x = u32(bit.bxor(x, bit.rshift(x, 17)))
  x = u32(bit.bxor(x, u32(bit.lshift(x, 5))))
  self.s = x
  return x / U32   -- [0,1)
end

function M:int(a, b) return a + math.floor(self:next() * (b - a + 1)) end
function M:range(a, b) return a + self:next() * (b - a) end
function M:pick(t) if #t == 0 then return nil end return t[self:int(1, #t)] end

function M:shuffle(t)
  local r = {}
  for i, v in ipairs(t) do r[i] = v end
  for i = #r, 2, -1 do
    local j = self:int(1, i)
    r[i], r[j] = r[j], r[i]
  end
  return r
end

-- a fresh random seed string from the clock
function M.random_seed(alphabet, len, entropy)
  local r = M.new(tostring(entropy or os.time()) .. tostring(os.clock()))
  local s = {}
  for i = 1, len do
    local k = r:int(1, #alphabet)
    s[i] = alphabet:sub(k, k)
  end
  return table.concat(s)
end

return M
