// File Path: /beam-core/examples/thor_smoke.rs
// Purpose: Offline SHA-256 verified THOR smoke-test in a disposable OS-temp root
// Module: beam-core - example binary (Windows test artifact)
// Version: 0.1.0
// Description: No game directory arguments, no network and no live client mutations
// Dependency Layer: Tool

use beam_core::patcher::smoke_test_loose_thor;
use sha2::{Digest, Sha256};
use std::error::Error;
use std::io::Read;
use std::path::Path;

fn main() {
    if let Err(error) = run() {
        eprintln!("BEAM THOR sandbox FAILED: {error}");
        std::process::exit(1);
    }
}

fn run() -> Result<(), Box<dyn Error>> {
    let mut args = std::env::args_os();
    let _exe = args.next();
    let path = args.next();
    let digest = args.next();
    if path.is_none() || digest.is_none() || args.next().is_some() {
        return Err(
            "Usage: thor_smoke.exe <path-to-local-loose-file.thor> <expected-sha256>\n\
             The archive is only tested in an automatically created disposable directory.\n\
             It does NOT apply patches to any installed Ragnarok game."
                .into(),
        );
    }
    let path = path.unwrap();
    let digest = digest.unwrap();
    let path = Path::new(&path);
    let expected = digest
        .to_str()
        .ok_or("SHA-256 argument must be plain hexadecimal ASCII")?
        .to_ascii_lowercase();
    if expected.len() != 64 || !expected.bytes().all(|b| b.is_ascii_hexdigit()) {
        return Err("SHA-256 must have exactly 64 hexadecimal characters".into());
    }

    let mut file = std::fs::File::open(path)?;
    let mut hash = Sha256::new();
    let mut buffer = [0u8; 64 * 1024];
    loop {
        let count = file.read(&mut buffer)?;
        if count == 0 {
            break;
        }
        hash.update(&buffer[..count]);
    }
    let actual = format!("{:x}", hash.finalize());
    if actual != expected {
        return Err(format!(
            "THOR SHA-256 mismatch: expected {expected}, received {actual}"
        )
        .into());
    }

    println!("THOR SHA-256 verified: {actual}");
    let report = smoke_test_loose_thor(path)?;
    println!(
        "BEAM disposable test PASS: {} installed files, {} removals, no GRF written: {}",
        report.verified_files, report.deleted_files, report.no_grf_written
    );
    println!("Real Ragnarok client files were not accessed or changed.");
    Ok(())
}
