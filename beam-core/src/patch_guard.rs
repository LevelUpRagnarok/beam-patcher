//! Region/channel-bound patch preflight for deployments that opt into the guard.
 //!
 //! IMPORTANT: a patchlist or checksum alone is not trusted proof of origin.
 //! Deployers must protect the config and manifest from untrusted modification.

use crate::{Config, Error, Result};
use serde::Deserialize;
use sha2::{Digest, Sha256};
use std::collections::HashMap;
use std::fs::File;
use std::io::Read;
use std::path::{Path, PathBuf};

#[derive(Debug, Deserialize)]
struct PatchManifest {
    schema: String,
    profile_id: String,
    region: String,
    channel: String,
    client_exe_sha256: String,
    target_grf: String,
    patches: Vec<PatchEntry>,
}

#[derive(Debug, Deserialize)]
struct PatchEntry {
    filename: String,
    sha256: String,
}

pub(crate) struct PatchCompatibilityGuard {
    allowed_patches: HashMap<String, String>,
}

fn reject(reason: impl Into<String>) -> Error {
    Error::PatchFailed(format!("Region/channel patch guard: {}", reason.into()))
}

fn safe_basename(value: &str) -> bool {
    !value.is_empty()
        && value != "."
        && value != ".."
        && !value.contains("..")
        && !value.starts_with('.')
        && value
            .bytes()
            .all(|c| c.is_ascii_alphanumeric() || matches!(c, b'.' | b'-' | b'_'))
}

fn valid_sha256(value: &str) -> bool {
    value.len() == 64 && value.bytes().all(|c| c.is_ascii_hexdigit())
}

fn digest(path: &Path) -> Result<String> {
    let mut input = File::open(path)?;
    let mut hasher = Sha256::new();
    let mut buffer = [0u8; 65536];
    loop {
        let len = input.read(&mut buffer)?;
        if len == 0 {
            break;
        }
        hasher.update(&buffer[..len]);
    }
    Ok(format!("{:x}", hasher.finalize()))
}

impl PatchCompatibilityGuard {
    pub(crate) fn new(config: &Config) -> Result<Option<Self>> {
        let Some(ref policy) = config.patcher.compatibility_guard else {
            return Ok(None);
        };

        if !safe_basename(&policy.profile_id)
            || !safe_basename(&policy.manifest_file)
            || !safe_basename(&config.app.client_exe)
            || !safe_basename(&config.patcher.target_grf)
            || !valid_sha256(&policy.client_exe_sha256)
        {
            return Err(reject("invalid profile, executable, GRF, hash or manifest path"));
        }

        match (policy.region.as_str(), policy.channel.as_str()) {
            ("levelupgt", "custom")
            | ("kro", "main")
            | ("kro", "sakray")
            | ("iro", "main")
            | ("iro", "sakray") => {}
            _ => return Err(reject("unknown or cross-region channel pair")),
        }

        let directory = match &config.app.game_directory {
            Some(dir) => PathBuf::from(dir),
            None => crate::get_executable_dir()?,
        };
        let manifest_path = directory.join(&policy.manifest_file);
        let source = std::fs::read_to_string(&manifest_path)?;
        let manifest: PatchManifest = serde_json::from_str(&source)
            .map_err(|e| reject(format!("invalid JSON manifest: {e}")))?;

        if manifest.schema != "levelupgt.beam-regional-patch-manifest.v1"
            || manifest.profile_id != policy.profile_id
            || manifest.region != policy.region
            || manifest.channel != policy.channel
            || !manifest.client_exe_sha256.eq_ignore_ascii_case(&policy.client_exe_sha256)
            || !manifest.target_grf.eq_ignore_ascii_case(&config.patcher.target_grf)
        {
            return Err(reject("manifest is for a different profile, channel, executable or GRF"));
        }

        let exe_path = directory.join(&config.app.client_exe);
        let real_exe_hash = digest(&exe_path)?;
        if !real_exe_hash.eq_ignore_ascii_case(&policy.client_exe_sha256) {
            return Err(reject("client executable SHA256 differs from protected profile"));
        }

        if manifest.patches.is_empty() || manifest.patches.len() > 4096 {
            return Err(reject("manifest patch count outside safe bounds"));
        }
        let mut allowed_patches = HashMap::new();
        for entry in manifest.patches {
            if !safe_basename(&entry.filename)
                || !valid_sha256(&entry.sha256)
                || !matches!(
                    Path::new(&entry.filename)
                        .extension()
                        .and_then(|x| x.to_str())
                        .map(|x| x.to_ascii_lowercase())
                        .as_deref(),
                    Some("beam" | "thor" | "rgz" | "gpf")
                )
            {
                return Err(reject("unsafe patch filename, extension or SHA256"));
            }
            let key = entry.filename.to_ascii_lowercase();
            if allowed_patches
                .insert(key, entry.sha256.to_ascii_lowercase())
                .is_some()
            {
                return Err(reject("duplicate or case-colliding patch filename"));
            }
        }
        Ok(Some(Self { allowed_patches }))
    }

    /// Call *before downloading* to stop unknown or traversal filenames.
    pub(crate) fn validate_name(&self, name: &str) -> Result<()> {
        if !safe_basename(name) || !self.allowed_patches.contains_key(&name.to_ascii_lowercase()) {
            return Err(reject(format!("patch is not approved for this profile: {name}")));
        }
        Ok(())
    }

    /// Call *before touching GRF* to bind downloaded bytes to the profile manifest.
    pub(crate) fn validate_file(&self, path: &Path) -> Result<()> {
        let name = path
            .file_name()
            .and_then(|n| n.to_str())
            .ok_or_else(|| reject("missing UTF8 patch filename"))?;
        self.validate_name(name)?;
        let expected = &self.allowed_patches[&name.to_ascii_lowercase()];
        if !digest(path)?.eq_ignore_ascii_case(expected) {
            return Err(reject(format!("patch SHA256 mismatches the active profile: {name}")));
        }
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn rejects_traversal_and_case_collisions() {
        for bad in ["../client.thor", r"..\client.thor", ".hidden.thor", "foo/evil.grf", ""] {
            assert!(!safe_basename(bad));
        }
        assert!(safe_basename("translate-System.thor"));
    }

    #[test]
    fn wrong_region_name_is_denied_before_io() {
        let guard = PatchCompatibilityGuard {
            allowed_patches: HashMap::from([("kro-main.thor".to_owned(), "0".repeat(64))]),
        };
        assert!(guard.validate_name("kro-main.thor").is_ok());
        assert!(guard.validate_name("iro-main.thor").is_err());
        assert!(guard.validate_name("../kro-main.thor").is_err());
    }

    #[test]
    fn guarded_deployment_checks_exe_channel_and_patch_bytes() {
        use crate::config::CompatibilityGuardConfig;
        let test_dir = std::env::temp_dir()
            .join(format!("beam-region-test-{}-{}", std::process::id(), std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH).unwrap().as_nanos()));
        std::fs::create_dir_all(&test_dir).unwrap();
        let result = (|| {
            let exe_path = test_dir.join("game.exe");
            let patch_path = test_dir.join("custom.thor");
            std::fs::write(&exe_path, b"verified-binary").unwrap();
            std::fs::write(&patch_path, b"verified-patch").unwrap();
            let exe_digest = digest(&exe_path).unwrap();
            let patch_digest = digest(&patch_path).unwrap();
            let json = serde_json::json!({
                "schema": "levelupgt.beam-regional-patch-manifest.v1",
                "profile_id": "levelupgt-custom-20220406",
                "region": "levelupgt",
                "channel": "custom",
                "client_exe_sha256": exe_digest,
                "target_grf": "ragnardata.grf",
                "patches": [{"filename":"custom.thor","sha256":patch_digest}]
            });
            std::fs::write(test_dir.join("regional-patches.json"), json.to_string()).unwrap();

            let mut config = Config::default();
            config.app.game_directory = Some(test_dir.to_string_lossy().into_owned());
            config.app.client_exe = "game.exe".to_owned();
            config.patcher.target_grf = "ragnardata.grf".to_owned();
            config.patcher.compatibility_guard = Some(CompatibilityGuardConfig {
                profile_id: "levelupgt-custom-20220406".to_owned(),
                region: "levelupgt".to_owned(),
                channel: "custom".to_owned(),
                client_exe_sha256: exe_digest.clone(),
                manifest_file: "regional-patches.json".to_owned(),
            });
            let guard = PatchCompatibilityGuard::new(&config).unwrap().unwrap();
            assert!(guard.validate_name("custom.thor").is_ok());
            assert!(guard.validate_file(&patch_path).is_ok());
            std::fs::write(&patch_path, b"different-region-data").unwrap();
            assert!(guard.validate_file(&patch_path).is_err());

            config.patcher.compatibility_guard.as_mut().unwrap().channel =
                "sakray".to_owned();
            assert!(PatchCompatibilityGuard::new(&config).is_err());
            config.patcher.compatibility_guard.as_mut().unwrap().channel =
                "custom".to_owned();
            config.patcher.compatibility_guard.as_mut().unwrap().client_exe_sha256 =
                "a".repeat(64);
            assert!(PatchCompatibilityGuard::new(&config).is_err());
            Ok::<(), Box<dyn std::error::Error>>(())
        })();
        let _ = std::fs::remove_dir_all(&test_dir);
        result.unwrap();
    }

    #[test]
    fn hash_syntax_requires_full_256_bit_digest() {
        assert!(!valid_sha256("abcd"));
        assert!(valid_sha256(&"a".repeat(64)));
    }
}
