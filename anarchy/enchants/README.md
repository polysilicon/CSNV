# crispy_enchants

`gen.py` generates the `crispy_enchants` datapack: AdvancedEnchantments' custom enchantments (from the plugin's
`enchantments.yml`) rebuilt as native data-driven enchantments, the XP Enchanter, and the migration of old AE items.

```
python3 gen.py <outdir>      # -> <outdir>/data/crispy_enchants/...
```

It runs on Anarchy (`CrispyAnarchy01`) and PvP (`CrispyPvP01`), in `world/datapacks/crispy_enchants`.

## Migration of old AE items
Every 2 seconds `migrate/all` checks every player's inventory, armour and ender chest. Items carrying AE's
`ae_enchantment;<name>` custom_data keys get the matching native enchantments, AE's lore lines stripped, and their
custom_data cleared.

`migrate/has_ae` makes sure only real AE items are touched. Before it existed, any item with 1-15 custom_data keys
counted as an AE item, so cyberware implants lost their lore and Pack-a-Punch tiers (then kept in custom_data) were
wiped every 2 seconds.
