# crispy_enchants

`gen.py` generates the `crispy_enchants` datapack: AdvancedEnchantments' custom enchantments (from the plugin's
`enchantments.yml`) rebuilt as native data-driven enchantments, the XP Enchanter, and the migration of old AE items.

```
python3 gen.py <outdir>      # -> <outdir>/data/crispy_enchants/...
```

It runs on Anarchy (`CrispyAnarchy01`) and PvP (`CrispyPvP01`), in `world/datapacks/crispy_enchants`.

## The Enchanter

Sells random enchantment books by tier and the Heroic upgrade for XP points (`enchanter/buy`). Buying needs you within
8 blocks of the Enchanter, and `enchanter/pay` returns 0 when you can't afford it. Before the fix it ended with
`return run tellraw`, which returns 1, so failed payments counted as paid and people got books without the XP.
On Anarchy the `crispy-anarchy` mod (`anarchy/mod`) shows it as a chest menu (tiers from storage `crispy_enchants:shop`,
written by `enchanter/shop_data` on load); elsewhere the dialog opens.

## Migration of old AE items
Every 2 seconds `migrate/all` checks every player's inventory, armour and ender chest. Items carrying AE's
`ae_enchantment;<name>` custom_data keys get the matching native enchantments, AE's lore lines stripped, and their
custom_data cleared.

`migrate/has_ae` makes sure only real AE items are touched. Before it existed, any item with 1-15 custom_data keys
counted as an AE item, so cyberware implants lost their lore and Pack-a-Punch tiers (then kept in custom_data) were
wiped every 2 seconds.
