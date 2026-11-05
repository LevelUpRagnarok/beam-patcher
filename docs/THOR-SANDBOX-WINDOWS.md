# BEAM THOR sandbox — test-only Windows binary

This command-line executable uses the BEAM Rust client-file installer to test one *local loose-client THOR* in a newly created OS temporary directory. It checks the SHA-256 supplied as an argument, applies the contents, compares every file's final bytes and tests removals, then deletes its temporary directory.

**It never accepts a Ragnarok installation directory**, has no download feature, and does not run the game. It rejects GRF-merging THORs. This is **not** a production patcher.

## Example: ROenglishRE 2022 Hybrid test archive

Download the original THOR from https://github.com/b1glord/ROenglishRE/releases/tag/rpatchur-2022-hybrid-test and put it in the same folder as the EXE.

```powershell
.\thor_smoke.exe .\turkuaz-2022-hybrid-8cfc3211f8eb.thor e18d5368f44feaa1569c1b2f7893b4d51167bd6bb03ab93e4d6ae108a147b2c8
```

The file fingerprint must match or the tool exits before extracting anything. The CI itself runs the same test on GitHub-hosted Windows and stores a 7-day test artifact.

