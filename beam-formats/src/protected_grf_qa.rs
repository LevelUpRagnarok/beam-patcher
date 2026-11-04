// Dosya Yolu: beam-formats/src/protected_grf_qa.rs
// Amac: Deneysel tdata1 GRF gizliligi icin AEAD wrapper, oyun tarafina baglanmamis
// Modul - Rust / isolated QA only
// Version: 0.1.0-qa
// Aciklama: Tam GRF'i AES-256-GCM ile bellekte muhafaza eder; GERCEK .grf degildir.
// Bagimli Oldugu Katman: beam-formats/src/grf.rs | RustCrypto aes-gcm
//! Experimental authenticated *envelope* for a regular GRF 0x200.
//!
//! WARNING: This is NOT a Ragnarok-readable encrypted GRF; bytes begin
//! with "LUGRFQA1", not "Master of Magic". Never rename it to tdata1.grf,
//! add it to DATA.INI or publish to the 2022 patch feed.
//! No keys are embedded, stored or logged. The real client would need an
//! independently tested compatible decrypting loader before deployment.

use crate::{Error, Result};
use aes_gcm::{
    aead::{Aead, AeadCore, KeyInit, OsRng, Payload},
    Aes256Gcm,
};

const MAGIC: &[u8; 8] = b"LUGRFQA1";
const VERSION: u32 = 1;
const HEADER_SIZE: usize = 8 + 4 + 16 + 12 + 8;
const TAG_SIZE: usize = 16;
const MAX_PLAINTEXT_QA: usize = 64 * 1024 * 1024;
const GRF_HEADER_SIZE: usize = 46;
const KEY_ID_START: usize = 12;
const NONCE_START: usize = 28;
const LENGTH_START: usize = 40;

fn rejected(reason: &'static str) -> Error {
    Error::Unsupported(format!("protected GRF QA: {reason}"))
}

fn verified_regular_grf(data: &[u8]) -> Result<()> {
    if !(GRF_HEADER_SIZE..=MAX_PLAINTEXT_QA).contains(&data.len())
        || &data[..15] != b"Master of Magic"
        || u32::from_le_bytes(data[42..46].try_into().expect("checked length")) != 0x200
    {
        return Err(rejected("only bounded regular GRF 0x200 source is accepted"));
    }
    Ok(())
}

/// Authenticated encryption of an *entire* small GRF in memory, QA ONLY.
/// Caller must supply a secret 32-byte key sourced outside the repository.
/// key_id is a public non-secret identifier used to select the right key.
pub fn seal_qa(plain_grf: &[u8], key: &[u8; 32], key_id: &[u8; 16]) -> Result<Vec<u8>> {
    verified_regular_grf(plain_grf)?;

    let cipher = Aes256Gcm::new_from_slice(key)
        .map_err(|_| rejected("invalid secret key length"))?;
    let nonce = Aes256Gcm::generate_nonce(&mut OsRng);

    let mut header = Vec::with_capacity(HEADER_SIZE);
    header.extend_from_slice(MAGIC);
    header.extend_from_slice(&VERSION.to_le_bytes());
    header.extend_from_slice(key_id);
    header.extend_from_slice(nonce.as_slice());
    header.extend_from_slice(&(plain_grf.len() as u64).to_le_bytes());
    debug_assert_eq!(header.len(), HEADER_SIZE);

    let ciphertext = cipher
        .encrypt(
            &nonce,
            Payload {
                msg: plain_grf,
                aad: &header,
            },
        )
        .map_err(|_| rejected("encrypt operation failed"))?;
    let mut sealed = header;
    sealed.extend_from_slice(&ciphertext);
    Ok(sealed)
}

/// Authenticated in-memory decryption. Never saves plaintext to disk.
/// Wrong key, key id, or any changed header/ciphertext must fail closed.
pub fn open_qa(envelope: &[u8], key: &[u8; 32], expected_key_id: &[u8; 16]) -> Result<Vec<u8>> {
    if envelope.len() < HEADER_SIZE + TAG_SIZE
        || envelope.len() > HEADER_SIZE + MAX_PLAINTEXT_QA + TAG_SIZE
        || &envelope[..8] != MAGIC
        || u32::from_le_bytes(envelope[8..12].try_into().expect("checked length")) != VERSION
    {
        return Err(rejected("invalid QA envelope header, version or size"));
    }
    if &envelope[KEY_ID_START..NONCE_START] != expected_key_id {
        return Err(rejected("wrong key identifier"));
    }
    let expected_size = u64::from_le_bytes(
        envelope[LENGTH_START..HEADER_SIZE].try_into().expect("checked length")
    );
    if expected_size < GRF_HEADER_SIZE as u64
        || expected_size > MAX_PLAINTEXT_QA as u64
        || envelope.len() != HEADER_SIZE + expected_size as usize + TAG_SIZE
    {
        return Err(rejected("invalid authenticated plaintext size"));
    }
    let cipher = Aes256Gcm::new_from_slice(key)
        .map_err(|_| rejected("invalid secret key length"))?;
    let nonce = aes_gcm::Nonce::from_slice(&envelope[NONCE_START..LENGTH_START]);
    let plaintext = cipher
        .decrypt(
            nonce,
            Payload {
                msg: &envelope[HEADER_SIZE..],
                aad: &envelope[..HEADER_SIZE],
            },
        )
        .map_err(|_| rejected("wrong key or tampered ciphertext / metadata"))?;
    verified_regular_grf(&plaintext)?;
    Ok(plaintext)
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::grf::Grf;
    use std::fs;
    use std::path::PathBuf;
    use std::time::{SystemTime, UNIX_EPOCH};

    // This is a synthetic public TEST VECTOR, never a production secret.
    const TEST_KEY: [u8; 32] = [0x42; 32];
    const TEST_KEY_ID: [u8; 16] = [0x33; 16];

    struct TestGrfFile(PathBuf);
    impl Drop for TestGrfFile {
        fn drop(&mut self) {
            let _ = fs::remove_file(&self.0);
            let _ = fs::remove_file(self.0.with_extension("grf.tmp"));
            let _ = fs::remove_file(self.0.with_extension("grf.bak"));
        }
    }
    fn temp_grf() -> TestGrfFile {
        let now = SystemTime::now().duration_since(UNIX_EPOCH).unwrap().as_nanos();
        TestGrfFile(std::env::temp_dir().join(format!(
            "beam-protected-qa-{}-{now}.grf",
            std::process::id()
        )))
    }
    fn make_grf() -> (TestGrfFile, Vec<u8>) {
        let file = temp_grf();
        let mut grf = Grf::create_new(&file.0).unwrap();
        grf.patch_file("data\\iz_dun00t.rsw", b"GRSW_qa_original").unwrap();
        grf.save().unwrap();
        let source = fs::read(&file.0).unwrap();
        assert!(Grf::open(&file.0).unwrap().get_entry("data\\iz_dun00t.rsw").is_some());
        (file, source)
    }

    #[test]
    fn protected_grf_qa_roundtrip_is_opaque_and_uses_fresh_nonce() {
        let (_file, plain) = make_grf();
        let first = seal_qa(&plain, &TEST_KEY, &TEST_KEY_ID).unwrap();
        let second = seal_qa(&plain, &TEST_KEY, &TEST_KEY_ID).unwrap();
        assert_ne!(first, second, "fresh nonce required for AES-GCM");
        assert_eq!(&first[..8], MAGIC);
        assert_ne!(&first[..15], b"Master of Magic");
        assert!(!first.windows(b"data\\iz_dun00t.rsw".len())
            .any(|window| window == b"data\\iz_dun00t.rsw"));
        assert_eq!(open_qa(&first, &TEST_KEY, &TEST_KEY_ID).unwrap(), plain);
    }

    #[test]
    fn protected_grf_qa_rejects_wrong_key_and_key_identifier() {
        let (_file, plain) = make_grf();
        let sealed = seal_qa(&plain, &TEST_KEY, &TEST_KEY_ID).unwrap();
        assert!(open_qa(&sealed, &[0x55; 32], &TEST_KEY_ID).is_err());
        assert!(open_qa(&sealed, &TEST_KEY, &[0x44; 16]).is_err());
    }

    #[test]
    fn protected_grf_qa_detects_ciphertext_header_and_truncation() {
        let (_file, plain) = make_grf();
        let envelope = seal_qa(&plain, &TEST_KEY, &TEST_KEY_ID).unwrap();
        let mut tampered = envelope.clone();
        *tampered.last_mut().unwrap() ^= 0x01;
        assert!(open_qa(&tampered, &TEST_KEY, &TEST_KEY_ID).is_err());
        let mut tampered = envelope.clone();
        tampered[LENGTH_START] ^= 0x01;
        assert!(open_qa(&tampered, &TEST_KEY, &TEST_KEY_ID).is_err());
        assert!(open_qa(&envelope[..envelope.len()-1], &TEST_KEY, &TEST_KEY_ID).is_err());
        assert!(open_qa(b"not a GRF", &TEST_KEY, &TEST_KEY_ID).is_err());
    }

    #[test]
    fn protected_grf_qa_can_patch_and_reseal_in_isolated_memory_workflow() {
        let (file, plain) = make_grf();
        let encrypted = seal_qa(&plain, &TEST_KEY, &TEST_KEY_ID).unwrap();

        // QA simulates what a future authenticated loader/updater must do:
        // decrypt -> stage a separate QA GRF -> patch -> reseal new bytes.
        // This does not mutate the real client and is NOT wired into Patcher.
        let decrypted = open_qa(&encrypted, &TEST_KEY, &TEST_KEY_ID).unwrap();
        fs::write(&file.0, &decrypted).unwrap();
        let mut grf = Grf::open(&file.0).unwrap();
        grf.patch_file("data\\iz_dun00t.rsw", b"GRSW_qa_updated").unwrap();
        grf.patch_file("data\\iz_dun01t.rsw", b"GRSW_qa_new").unwrap();
        grf.save().unwrap();

        let updated = fs::read(&file.0).unwrap();
        let encrypted_update = seal_qa(&updated, &TEST_KEY, &TEST_KEY_ID).unwrap();
        assert_ne!(encrypted, encrypted_update);
        assert_eq!(open_qa(&encrypted_update, &TEST_KEY, &TEST_KEY_ID).unwrap(), updated);
        let reopened = Grf::open(&file.0).unwrap();
        assert_eq!(reopened.extract_file("data\\iz_dun00t.rsw").unwrap(), b"GRSW_qa_updated");
        assert_eq!(reopened.extract_file("data\\iz_dun01t.rsw").unwrap(), b"GRSW_qa_new");
    }

    #[test]
    fn protected_grf_qa_refuses_fake_encrypted_grf_version() {
        let (_file, mut plain) = make_grf();
        plain[42..46].copy_from_slice(&0x300u32.to_le_bytes());
        assert!(seal_qa(&plain, &TEST_KEY, &TEST_KEY_ID).is_err());
    }
}
