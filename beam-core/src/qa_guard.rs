// Dosya Yolu: beam-core/src/qa_guard.rs
// Amac: Yalniz izole test klasorune yazilmasina izin veren QA politikasi
// Modul - Rust safety policy
// Version: 0.1.0-candidate
// Aciklama: Gercek Ragnarok kurulumlarini, junction/symlink ve dis HTTP yayinini reddeder
// Bagimli Oldugu Katman: beam-core/src/config.rs | beam-core/src/patcher.rs

use crate::{Config, Error, Result};
use std::fs;
use std::path::Path;

pub(crate) const QA_APP_NAME: &str = "Turkuaz Ragnarok Online QA";
// Legacy identifier is intentionally retained so existing unsigned QA installs
// cannot escape the isolated workspace guard by upgrading to the new brand.
pub(crate) const LEGACY_QA_APP_NAME: &str = "LevelUp Games Beam QA";

pub(crate) fn is_qa_app_name(name: &str) -> bool {
    name == QA_APP_NAME || name == LEGACY_QA_APP_NAME
}
const QA_GRF: &str = "levelup-qa.grf";

fn qa_reject(reason: impl AsRef<str>) -> Error {
    Error::InvalidConfig(format!("QA isolation: {}", reason.as_ref()))
}

/// Validate a local-only test configuration, including its selected workspace.
/// This prevents accidental production modifications, not a malicious operator
/// changing source code or opting out of the QA profile.
pub fn validate_qa_config(config: &Config) -> Result<()> {
    if !config.patcher.qa_only {
        return Ok(());
    }
    if config.patcher.target_grf != QA_GRF
        || config.app.client_exe != "NO_CLIENT_CONFIGURED.exe"
        || !config.patcher.verify_checksums
        || config.updater.as_ref().is_some_and(|updater| updater.enabled || updater.auto_update)
    {
        return Err(qa_reject("unsafe target GRF, client EXE, checksum, or updater"));
    }
    for url in std::iter::once(config.patcher.patch_list_url.as_str())
        .chain(config.patcher.mirrors.iter().map(|mirror| mirror.url.as_str()))
    {
        let parsed = reqwest::Url::parse(url)
            .map_err(|_| qa_reject("invalid loopback patch URL"))?;
        if parsed.scheme() != "http"
            || parsed.host_str() != Some("127.0.0.1")
            || !parsed.username().is_empty()
            || parsed.password().is_some()
        {
            return Err(qa_reject("QA patch URL must be HTTP on 127.0.0.1"));
        }
    }

    if let Some(directory) = config.app.game_directory.as_deref() {
        validate_qa_directory(Path::new(directory))?;
    }
    Ok(())
}

/// Reject occupied game installations even when selected through a native
/// folder dialog. Reparse/symlink path components are not allowed.
pub fn validate_qa_directory(path: &Path) -> Result<()> {
    if !path.is_absolute() || !path.is_dir() {
        return Err(qa_reject("select an existing absolute QA directory"));
    }

    for ancestor in path.ancestors() {
        let metadata = fs::symlink_metadata(ancestor)?;
        if metadata.file_type().is_symlink() {
            return Err(qa_reject("symlink or junction workspace is not allowed"));
        }
    }

    for entry in fs::read_dir(path)? {
        let entry = entry?;
        let name = entry.file_name();
        let name = name.to_string_lossy();
        let metadata = fs::symlink_metadata(entry.path())?;
        if metadata.file_type().is_symlink() {
            return Err(qa_reject("workspace contains a symlink/junction"));
        }
        match name.as_ref() {
            ".patch_cache" if metadata.is_dir() => {
                for cache_entry in fs::read_dir(entry.path())? {
                    let cache_entry = cache_entry?;
                    let cache_meta = fs::symlink_metadata(cache_entry.path())?;
                    if cache_meta.file_type().is_symlink() || !cache_meta.is_file() {
                        return Err(qa_reject("unsafe patch cache contents"));
                    }
                    if cache_entry.file_name() != "applied_patches.txt" {
                        return Err(qa_reject("unexpected patch cache contents"));
                    }
                }
            }
            QA_GRF if metadata.is_file() => {}
            _ => return Err(qa_reject(format!(
                "workspace has non-QA content: {}", name
            ))),
        }
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::time::{SystemTime, UNIX_EPOCH};

    #[test]
    fn empty_workspace_is_allowed_but_live_client_files_are_denied() {
        let root = std::env::temp_dir().join(format!(
            "beam-qa-dir-{}-{}", std::process::id(),
            SystemTime::now().duration_since(UNIX_EPOCH).unwrap().as_nanos()
        ));
        fs::create_dir(&root).unwrap();
        let result = (|| -> Result<()> {
            validate_qa_directory(&root)?;
            fs::write(root.join("DATA.INI"), b"data=production")?;
            assert!(validate_qa_directory(&root).is_err());
            fs::remove_file(root.join("DATA.INI"))?;
            fs::write(root.join(QA_GRF), b"synthetic-grf")?;
            validate_qa_directory(&root)?;
            fs::create_dir(root.join(".patch_cache"))?;
            fs::write(root.join(".patch_cache/applied_patches.txt"), b"qa.beam\n")?;
            validate_qa_directory(&root)?;
            Ok(())
        })();
        let _ = fs::remove_dir_all(&root);
        result.unwrap();
    }

    #[test]
    fn qa_profile_rejects_remote_urls_or_real_game_target() {
        let mut config = Config::default();
        config.patcher.qa_only = true;
        config.patcher.target_grf = QA_GRF.to_owned();
        config.app.client_exe = "NO_CLIENT_CONFIGURED.exe".to_owned();
        config.updater = None;
        config.patcher.patch_list_url = "http://127.0.0.1:9/disabled/patchlist.txt".into();
        config.patcher.mirrors[0].url = "http://127.0.0.1:9/disabled".into();
        assert!(validate_qa_config(&config).is_ok());
        config.patcher.patch_list_url = "https://example.com/patchlist.txt".into();
        assert!(validate_qa_config(&config).is_err());
        config.patcher.patch_list_url = "http://127.0.0.1:9/patchlist.txt".into();
        config.patcher.target_grf = "data.grf".into();
        assert!(validate_qa_config(&config).is_err());
    }
}
