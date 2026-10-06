# vendor/

`jip_nvse.dll` (JIP LN NVSE, by jazzisparis, GPL-3.0) goes here before `tools/build.py` packages a release.
The build copies it to `Data/NVSE/Plugins/` and `JIP-LN-NVSE-LICENSE.txt` next to the launcher.

JIP LN NVSE has no GitHub releases; the built DLL is published on Nexus Mods (needs a free Nexus login):
https://www.nexusmods.com/newvegas/mods/58277 . Source: https://github.com/jazzisparis/JIP-LN-NVSE .
Commit `jip_nvse.dll` here (GPL-3.0 allows redistributing it with its license and a source link, both included):
the release workflow builds from the repository, and `tools/build.py --release` refuses to package without it.
Record the JIP LN version you committed in CREDITS.md.
