# vendor/

`jip_nvse.dll` (JIP LN NVSE, by jazzisparis, GPL-3.0) goes here before `tools/build.py` packages a release.
The build copies it to `Data/NVSE/Plugins/` and `JIP-LN-NVSE-LICENSE.txt` next to the launcher.

JIP LN NVSE has no GitHub releases; the built DLL is published on Nexus Mods (needs a free Nexus login):
https://www.nexusmods.com/newvegas/mods/58277 . Source: https://github.com/jazzisparis/JIP-LN-NVSE .
Commit `jip_nvse.dll` here (GPL-3.0 allows redistributing it with its license and a source link, both included):
the release workflow builds from the repository, and `tools/build.py --release` refuses to package without it.
Record the JIP LN version you committed in CREDITS.md.

Committed: JIP LN NVSE 57.30 (Nexus file JIP_LN_NVSE_Plugin-58277-57-30), unmodified: `jip_nvse.dll`
(sha256 9d2779647ed0ce63043390f47fc978e3234af8e558dc6cb6bcb231478a2d74d4) and `textinput/texteditmenu.xml`.
The debug symbols (`jip_nvse.pdb`) are left out.
