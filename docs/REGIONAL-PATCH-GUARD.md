# Region / channel patch guard (opt-in)

This guard is designed for the LevelUpGT Ragnarok client compatibility profiles.
It keeps kRO Main, kRO Sakray, iRO and LevelUpGT custom patches distinct
**after the installer/operator explicitly opts in**.

The upstream Beam patcher can be used by other game communities, so this
change does not silently enable an incompatible policy for every deployment.
If `patcher.compatibility_guard` is absent, the existing Beam behavior
remains unchanged. **Absent means unprotected against cross-region mixing.**

## Required identity

- The selected profile ID (e.g. `levelupgt-renewal-20220406`)
- Source region: `kro`, `iro` or `levelupgt`
- Channel: `main`, `sakray` or `custom` (only valid pairs)
- SHA-256 of the actual verified game client EXE
- Target GRF filename, e.g. `ragnardata.grf`
- A protected local JSON manifest containing only approved patch filenames
  and **SHA-256 of the exact patch bytes**

Example **config.yml fragment**, under the existing `patcher:` section:

```yaml
compatibility_guard:
  profile_id: "levelupgt-renewal-20220406"
  region: "levelupgt"
  channel: "custom"
  client_exe_sha256: "REPLACE_WITH_VERIFIED_64_HEX_EXE_HASH"
  manifest_file: "regional-patches.json"
```

Place `regional-patches.json` alongside the client EXE in
`app.game_directory`. Example schema:

```json
{
  "schema": "levelupgt.beam-regional-patch-manifest.v1",
  "profile_id": "levelupgt-renewal-20220406",
  "region": "levelupgt",
  "channel": "custom",
  "client_exe_sha256": "REPLACE_WITH_VERIFIED_64_HEX_EXE_HASH",
  "target_grf": "ragnardata.grf",
  "patches": [
    { "filename": "translate-System.thor", "sha256": "REPLACE_WITH_VERIFIED_PATCH_HASH" }
  ]
}
```

These placeholders are deliberately invalid: **do not put invented
hashes in production.** The actual checksum must be computed on verified,
licensed local EXE and patch bytes before enabling the guard.

## Enforcement points

- Guarded `Patcher::new` checks the profile, channel, EXE hash,
  target GRF and manifest *before* creating a downloader or temp dir.
- For single and batch downloads, every patch filename must be explicitly
  allowlisted *before any download or GRF opening*.
- Before patch bytes modify the in-memory GRF, Beam verifies the downloaded
  file SHA-256 against the profile manifest. Unknown patches and changed bytes
  are rejected. Existing THOR header/GRF target validation remains in place.
- Unknown Sakray or iRO client binaries cannot have invented hash matches
  or implicit kRO Main compatibility.

The match check is not a digital signature or trusted update publisher
attestation. Protect the config and manifest from unauthorized writes;
a malicious actor who controls *both* can replace allowlist and expected
hashes. TLS, signature and deployment policy are separate requirements.

## Limitations / release gate

- No new EXE, GRF, Lua/LUB or THOR binary is downloaded or published by this PR.
- No existing 2015 archive or THOR patch is reclassified as kRO Main or Sakray.
- Our S2 20220406 client binary hash is not yet verified on the frozen
  baseline; therefore the LevelUpGT production guard cannot be enabled yet.
- Client compatibility profile metadata is in
  [RagnarokClient](https://github.com/LevelUpGT/RagnarokClient)
  `config/compatibility/client-profiles.json`.
- Server protocol/game mode candidate is in
  [RagnarokServer](https://github.com/LevelUpGT/RagnarokServer)
  `config/compatibility/server-contracts.json`.
- iRO Wiki is a player-guide reference, **not** a patch-binary authority.
- This is preflight protection **when configured**, not proof of gameplay,
  login, GRF corruption recovery or an installer release.

Run `cargo test -p beam-core --lib` and `cargo check -p beam-core`.
Existing THOR safety tests must remain green.
