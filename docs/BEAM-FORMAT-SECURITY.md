<!--
Dosya Yolu: docs/BEAM-FORMAT-SECURITY.md
Amac: BEAM v1 compression and integrity vs encryption; safe v2 design gates
Modul - Markdown Documentation
Version: 0.1.0-candidate
Aciklama: Design-only, NO binary format change or player deployment
Bagimli Oldugu Katman: beam-formats/src/beam.rs | beam-core/src/patch_guard.rs
-->

# BEAM archive security: present facts and future encryption

## Current implementation: BEAM v1

Source of truth is `beam-formats/src/beam.rs` in this repository:

- 64-byte `BEAM` v1 header, plaintext entry names and table metadata.
- Individual payloads compressed with **zlib**, not Zstd.
- Per-entry **MD5** is checked after decompression. MD5 is a legacy wire
  compatibility check, **not** a signature and not a secure proof of origin.
- The deployment guard can match an expected **SHA-256** package digest to a
  manifest, but unsigned editable manifests do not on their own prove
  publisher authenticity.
- No BEAM archive encryption, password-derived key, AES, ChaCha20 or archive
  content confidentiality is implemented. A recipient can extract assets.
- GRF version descriptions mentioning encryption do **not** mean that
  `.beam` files are encrypted.

**The 20220406 Overlook custom map candidate is unencrypted BEAM v1.**
Its current SHA-256 can validate exact bytes; do not call it a secret archive.

## Proposed BEAM v2 (NOT IMPLEMENTED)

A distinct versioned wire format, behind a new feature gate, should use:

1. A **new BEAM v2 magic/version contract**, not silent changes to v1, with
   clear fail-closed errors for unknown versions and no automatic downgrade.
2. Authenticated encryption such as **AES-256-GCM** or **ChaCha20-Poly1305**,
   with nonce uniqueness across packages, authenticated metadata, strict
   sizes/count bounds and anti-path-traversal checks.
3. Clear key management: versioned key identifiers and rotation rules; never
   commit keys, passphrases, secrets or decrypted payloads to public GitHub.
4. A separately authenticated publisher identity, e.g. **Ed25519 signature**
   over canonical manifest and archive hash, plus pinned trusted public key.
   Encryption alone does not establish who produced a patch.
5. Tests for wrong keys, nonces, tampering, truncation, decompression bombs,
   downgrade attempts and rollback after failed GRF updates.
6. Interoperability across Rust decoder, Python or Rust encoder, Beam UI and
   actual GRF save/readback; then signed isolated real client smoke tests.

**Client-side limits:** Decryption keys must reach the player client if the
client can decrypt patches. A determined user can eventually retrieve keys or
plaintext. Protect keys and avoid false claims about preventing asset copying.

Status: **design discussion only**. No encrypted `.beam` archive or v2 release
is currently created, deployed or supported by Beam Patcher.
