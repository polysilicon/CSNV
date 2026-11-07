# Wasteland Merchant (Anarchy)

A shop villager in the market (`crispy:market`, -102.5 95 -68.5, on the street just outside the bank's east door)
that only trades with players **wearing** the rare **[Wastelander]** tag (lobby tag `wastelander`).

The tag comes from the **Wasteland Legend** advancement (`anarchy:wasteland_legend`, Adventure tab, in this
datapack): kill the Ender Dragon, kill the Wither, have all four netherite armor pieces, and stand 10,000 blocks
from spawn in the Overworld (any direction). Anyone can earn it; each part counts once and progress is kept. The
lobby sees it through `cosmetics.earned-sources` (Anarchy's advancements) and lists the tag under Achievements.

The gate is the chat-tags mod's: the villager is tagged `needtag.wastelander`, so anyone not wearing it gets
"This Wasteland Merchant needs [Wastelander] equipped", with a click to equip it once they've earned it.

Trades (Gold Coins, the market currency): Wasteland Blade (netherite sword, Sharpness V, Looting III) 48, Wasteland
Pickaxe (Efficiency V, Fortune III) 48, Wasteland Wings (elytra) 32, Mending book 16, enchanted golden apple 12,
totem 8, Wasteland Stash (shulker box) 10, 64 rockets 4.

- Install: `datapack/` as `world/datapacks/crispy_og`, `/reload`, then `/function og:place`.
- The market's own `spawn_shops`/reinstall kills every `crispy_shop` villager, so run `/function og:place` again after.
- `/function og:remove` takes it away.
