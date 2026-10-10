# Sources of the bundled tools

The release bundles these programs unmodified, as separate programs the launcher runs. Each is
downloaded from its official release by `tools/build.py --release` and checked by SHA-256
(`sheets/tools.json`).

- **OpenAssetTools v0.33.0** (GPL-3.0): https://github.com/Laupetin/OpenAssetTools/releases/tag/v0.33.0,
  source https://github.com/Laupetin/OpenAssetTools/tree/v0.33.0. Licence: `OpenAssetTools-LICENSE.txt`.
- **WolvenKit 9.1.0 console** (GPL-3.0): https://github.com/WolvenKit/WolvenKit/releases/tag/9.1.0,
  source https://github.com/WolvenKit/WolvenKit/tree/9.1.0. Licence: `WolvenKit-LICENSE.txt`.
- **.NET runtime 10.0.12** (MIT): https://dotnet.microsoft.com/download/dotnet/10.0, source
  https://github.com/dotnet/runtime. Licence and notices: `tools/dotnet/LICENSE.txt` and `ThirdPartyNotices.txt`.
