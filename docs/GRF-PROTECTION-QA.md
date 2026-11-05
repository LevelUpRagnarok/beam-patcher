<!--
Dosya Yolu: docs/GRF-PROTECTION-QA.md
Amac: LevelUpGT custom tdata1.grf koruma prototipinin sinirlari ve sonraki kapilar
Modul - Markdown
Version: 0.1.0-experimental
Aciklama: Gercek 20220406 istemciye yuklenmez; sadece offline Rust QA
Bagimli Oldugu Katman: beam-formats/src/protected_grf_qa.rs | grf.rs
-->

# Protected GRF for LevelUpGT — QA prototype, not a game client release

## Decision

- **Preserve** stock `data.grf`, `rdata.grf`, `ragnardata.grf` and 2015 legacy assets.
- Only consider protection for our separate **`tdata1.grf` custom asset overlay**.
- Do **not** change the already-validated `custom-maps.beam` v1 package.
- The real 20220406 Ragexe and its `DATA.INI` loading behavior remain unaudited.

## What was implemented (actual Rust library, QA only)

`beam-formats/src/protected_grf_qa.rs` implements a versioned wrapper
named **LUGRFQA1** with **AES-256-GCM** authenticated encryption of an
ENTIRE standard 0x200 GRF. Keys are 32 bytes, passed only by the caller;
no production key is stored in the repository. Each envelope has a
fresh random 96-bit nonce, public 16-byte key identifier, 64-bit
plaintext byte count and authenticated header as AES-GCM AAD. Altered
metadata, ciphertext, wrong key or truncation fail closed.

**Critical limitation:** the output begins with `LUGRFQA1`, **not**
the standard `Master of Magic` GRF header. A standard Ragnarok client
**cannot load it**, so it is not and must not be renamed to
`tdata1.grf` or referenced from DATA.INI. It is also not a new
Beam .beam format. There is intentionally **no automatic installation,
player patch, self-update, key distributor or release binary**.

The Rust unit test demonstrates the eventual patch algorithm on SYNTHETIC
sources in an isolated temporary directory:

1. Create regular 0x200 QA GRF, seal in memory with AES-256-GCM.
2. Decrypt to a separate QA file, apply two synthetic map-file changes
   with the existing `Grf` reader/writer, reseal with a new nonce.
3. Reopen to confirm changed bytes; reject wrong key, changed ciphertext,
   metadata tampering and unsupported 0x300 version.

The simulated plaintext intermediate file is limited to the
OS temp directory in the UNIT TEST. A production updater needs a
memory-only or protected staging strategy, secure cleanup, crash-safe
rollback and a trusted release manifest; the test is not production
security. This QA API caps source size to 64 MiB to bound memory usage.

Existing `Grf::open()` preserves legacy 0x101 read support and **rejects**
unverified protected/encrypted 0x102/0x103/0x300 parsing. `Grf::save()`
supports only the verified regular 0x200 writer. Prior behavior risked corrupting
"encrypted" archives by treating compressed bytes as decrypted data.

Further GRF 0x200 hardening: `0x200` header by itself does NOT prove every
entry is plaintext. GRF records can use per-entry encrypted flags
`0x02` / `0x04`. `Grf::extract_file()` now refuses such entries rather
than interpreting ciphertext as zlib, and `Grf::save()` rejects any
modification of a GRF containing encrypted/unknown entry flags until a
verified decrypt/re-encrypt writer is implemented. This protects the
existing game and avoids silently stripping encryption.

## Gates to an actually protected, usable GRF

1. Determine the **exact** local 20220406 Ragexe binary SHA-256, PE
   version, supported GRF format and `DATA.INI` priority.
2. Choose a genuinely loader-compatible mechanism; either a correctly
   documented, legally and technically compatible supported GRF
   encryption feature, or a custom client loader that decrypts our
   isolated overlay. Never assume changing the GRF version header alone
   provides working encryption.
3. Validate Beam Patcher runtime with authenticated manifest, external
   key provisioning/rotation, no downgrade, update failure rollback and
   byte-for-byte encrypted/decrypted/GRF readback.
4. Isolate and smoke-test all five Overlook maps. No changes to
   existing game GRFs, legacy THOR aliases or the 2022 public feed.
5. Explicit release authorization before publishing to
   `b1glord/ragnarokclientpatch/2022/data/`.

**Security expectation:** encryption makes offline extraction harder,
but any client capable of decrypting local assets can be reverse
engineered. Never promise absolute copy prevention.

## Offline test

```powershell
cargo test --manifest-path E:\Github\beam-patcher\Cargo.toml -p beam-formats protected_grf_qa -- --nocapture
cargo test --manifest-path E:\Github\beam-patcher\Cargo.toml -p beam-formats protected_version_rejection_tests
```

No CLI accepts production keys in this phase. The public 2022
distribution policy stays `ready: false`, `publish_allowed: false`.
