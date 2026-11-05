use crate::{Config, Downloader, Error, Result};
use crate::downloader::PatchInfo;
use crate::patch_guard::PatchCompatibilityGuard;
use beam_formats::{grf::Grf, gpf::Gpf, rgz::Rgz, thor::{Thor, ThorEntry, validate_client_path}, beam::BeamArchive};
use std::path::{Path, PathBuf};
use std::sync::{Arc, Mutex};
use tracing::{debug, info, warn};


fn validate_thor_destination(thor: &Thor, configured_grf: &str) -> Result<()> {
    if !thor.use_grf_merging {
        // Do not mistake a loose-file translation pack for GRF data.
        return Err(Error::PatchFailed(
            "THOR requires loose client file installation. \
             BEAM's transaction-safe client writer is not yet available; \
             use rPatchur for the Hybrid test channel."
                .to_string(),
        ));
    }
    if let Some(target) = &thor.target_grf_name {
        if !target.eq_ignore_ascii_case(configured_grf) {
            return Err(Error::PatchFailed(format!(
                "THOR target GRF '{}' does not match configured '{}'",
                target, configured_grf
            )));
        }
    }
    Ok(())
}


/// Cross-process single-writer lock for each Ragnarok client root. It is held
/// through patch application and released automatically when the process exits.
fn try_lock_client_root(root: &Path) -> Result<std::fs::File> {
    use fs2::FileExt;

    let path = root.join(".beam-patch.lock");
    match std::fs::symlink_metadata(&path) {
        Ok(meta) => {
            if !meta.is_file() || meta.file_type().is_symlink() {
                return Err(Error::PatchFailed("Unsafe client patch lock file".to_string()));
            }
            #[cfg(windows)]
            {
                use std::os::windows::fs::MetadataExt;
                if meta.file_attributes() & 0x400 != 0 {
                    return Err(Error::PatchFailed("Reparse-point patch lock rejected".to_string()));
                }
            }
        }
        Err(err) if err.kind() == std::io::ErrorKind::NotFound => {}
        Err(err) => return Err(err.into()),
    }
    let file = std::fs::OpenOptions::new()
        .create(true).read(true).write(true).open(path)?;
    file.try_lock_exclusive().map_err(|e| Error::PatchFailed(format!(
        "Another BEAM instance is already updating this client: {e}"
    )))?;
    Ok(file)
}

/// Remote filenames must not create arbitrary paths inside the shared temp folder.
fn validate_patch_filename(name: &str) -> Result<()> {
    validate_client_path(name)?;
    if (name.contains('/') || name.contains('\\')) || name.len() > 255 {
        return Err(Error::PatchFailed("Unsafe patch archive filename".to_string()));
    }
    let lower = name.to_ascii_lowercase();
    if ![".thor", ".beam", ".gpf", ".rgz"]
        .iter()
        .any(|suffix| lower.ends_with(suffix))
    {
        return Err(Error::PatchFailed("Unknown patch extension".to_string()));
    }
    Ok(())
}

/// A target must be a regular file or absent; no symlinks, junctions, or
/// non-directory ancestors, regardless of the OS running the patcher.
fn checked_client_destination(root: &Path, name: &str) -> Result<PathBuf> {
    validate_client_path(name)?;
    let normalized = name.replace('\\', "/");
    let first_segment = normalized.split('/').next().unwrap_or("");
    if first_segment.starts_with(TXN_PREFIX) || (first_segment.eq_ignore_ascii_case(".patch_cache") || first_segment.eq_ignore_ascii_case(".beam-patch.lock")) {
        return Err(Error::PatchFailed("Protected patcher metadata path".to_string()));
    }
    let segments: Vec<_> = normalized.split('/').collect();
    let mut path = root.to_path_buf();
    for (index, segment) in segments.iter().enumerate() {
        path.push(segment);
        match std::fs::symlink_metadata(&path) {
            Ok(metadata) => {
                #[cfg(windows)]
                {
                    use std::os::windows::fs::MetadataExt;
                    if metadata.file_attributes() & 0x400 != 0 {
                        return Err(Error::PatchFailed(
                            "Refusing Windows reparse-point path".to_string()
                        ));
                    }
                }
                if metadata.file_type().is_symlink()
                    || (index + 1 == segments.len() && !metadata.is_file())
                    || (index + 1 < segments.len() && !metadata.is_dir())
                {
                    return Err(Error::PatchFailed(format!(
                        "Refusing symlink or non-file client path: {}", name
                    )));
                }
            }
            Err(e) if e.kind() == std::io::ErrorKind::NotFound => {}
            Err(e) => return Err(e.into()),
        }
    }
    Ok(path)
}


// Persistent recovery metadata lives only in the transaction directory.
// No remote THOR entry is allowed to write to this reserved directory.
#[derive(serde::Serialize, serde::Deserialize)]
struct ClientRecoveryJournal {
    version: u32,
    entries: Vec<ClientRecoveryEntry>,
}

#[derive(serde::Serialize, serde::Deserialize)]
struct ClientRecoveryEntry {
    relative_path: String,
    had_original: bool,
}

const TXN_PREFIX: &str = ".beam-patch-txn-";

fn sync_file(path: &Path) -> Result<()> {
    std::fs::OpenOptions::new().write(true).open(path)?.sync_all()?;
    Ok(())
}

fn recovery_marker(path: &Path, marker: &str) -> Result<()> {
    let marker_path = path.join(marker);
    let mut file = std::fs::OpenOptions::new()
        .write(true).create_new(true).open(marker_path)?;
    std::io::Write::write_all(&mut file, marker.as_bytes())?;
    file.sync_all()?;
    Ok(())
}

fn store_recovery_journal(path: &Path, changes: &[ClientChange], root: &Path) -> Result<()> {
    let mut entries = Vec::with_capacity(changes.len());
    for item in changes {
        let relative = item.destination.strip_prefix(root)
            .map_err(|_| Error::PatchFailed("Unsafe recovery destination".to_string()))?;
        let value = relative.to_str().ok_or_else(|| Error::PatchFailed(
            "Recovery destination has invalid encoding".to_string()
        ))?.replace('\\', "/");
        validate_client_path(&value)?;
        entries.push(ClientRecoveryEntry {
            relative_path: value,
            had_original: item.backup.is_some(),
        });
    }
    let journal = ClientRecoveryJournal { version: 1, entries };
    let raw = serde_json::to_vec(&journal)
        .map_err(|e| Error::PatchFailed(format!("Journal serialization failed: {e}")))?;
    let file_path = path.join("journal.json");
    let mut file = std::fs::OpenOptions::new()
        .create_new(true).write(true).open(file_path)?;
    std::io::Write::write_all(&mut file, &raw)?;
    file.sync_all()?;
    Ok(())
}

fn recover_interrupted_client_transactions(root: &Path) -> Result<()> {
    for item in std::fs::read_dir(root)? {
        let item = item?;
        let file_name = item.file_name();
        let Some(name) = file_name.to_str() else { continue };
        if !name.starts_with(TXN_PREFIX) {
            continue;
        }
        let txn = item.path();
        let metadata = std::fs::symlink_metadata(&txn)?;
        if !metadata.is_dir() || metadata.file_type().is_symlink() {
            return Err(Error::PatchFailed(format!(
                "Unsafe interrupted transaction path: {}", txn.display()
            )));
        }

        // COMMITTED means files were replaced successfully; only garbage
        // collection was interrupted. Do not undo already applied files.
        if txn.join("COMMITTED").exists() {
            std::fs::remove_dir_all(&txn)?;
            continue;
        }

        if txn.join("COMMITTING").exists() {
            let raw = std::fs::read(txn.join("journal.json"))?;
            let journal: ClientRecoveryJournal = serde_json::from_slice(&raw)
                .map_err(|e| Error::PatchFailed(format!(
                    "Invalid recovery journal {}: {e}", txn.display()
                )))?;
            if journal.version != 1 || journal.entries.is_empty() || journal.entries.len() > 100_000 {
                return Err(Error::PatchFailed("Unsafe recovery journal version/count".to_string()));
            }

            // Check ALL recorded files and backups before writing any of them.
            let mut restored = Vec::with_capacity(journal.entries.len());
            let mut seen = std::collections::HashSet::new();
            for (index, record) in journal.entries.iter().enumerate() {
                let destination = checked_client_destination(root, &record.relative_path)?;
                if !seen.insert(record.relative_path.replace('\\', "/").to_lowercase()) {
                    return Err(Error::PatchFailed("Duplicate recovery destination".to_string()));
                }
                let backup = txn.join(format!("backup-{index}"));
                if record.had_original {
                    let metadata = std::fs::symlink_metadata(&backup)?;
                    if !metadata.is_file() || metadata.file_type().is_symlink() {
                        return Err(Error::PatchFailed(
                            "Recovery backup is not a regular file".to_string()
                        ));
                    }
                }
                restored.push((destination, record.had_original.then_some(backup)));
            }

            for (destination, backup) in restored.iter().rev() {
                if destination.exists() {
                    std::fs::remove_file(destination)?;
                }
                if let Some(backup) = backup {
                    if let Some(parent) = destination.parent() {
                        std::fs::create_dir_all(parent)?;
                    }
                    std::fs::copy(backup, destination)?;
                    sync_file(destination)?;
                }
            }
            // Safe for another interrupted recovery: backups remain untouched
            // until all restores finish, then the directory can be removed.
            std::fs::remove_dir_all(&txn)?;
            info!("Recovered and rolled back interrupted BEAM transaction");
        } else if txn.join("PREPARING").exists() {
            // Nothing was written to the client before COMMITTING existed.
            std::fs::remove_dir_all(&txn)?;
        } else {
            return Err(Error::PatchFailed(format!(
                "Unknown patch transaction state in {}. Manual recovery required.",
                txn.display()
            )));
        }
    }
    Ok(())
}

struct ClientChange {
    destination: PathBuf,
    staged: Option<PathBuf>,
    backup: Option<PathBuf>,
}

/// All loose-client changes are staged and backed up on the same volume.
/// On ordinary errors the installer attempts to restore every original file.
/// A power cut may still interrupt this best-effort rollback; production use
/// needs a persistent recovery journal (see Phase B acceptance documentation).
fn apply_loose_thors(game_root: &Path, archives: &[Thor]) -> Result<()> {
    use std::collections::BTreeMap;
    use std::time::{SystemTime, UNIX_EPOCH};

    let root = std::fs::canonicalize(game_root)?;
    if !root.is_dir() {
        return Err(Error::PatchFailed("Game root is not a directory".to_string()));
    }
    // Recover (or refuse) leftovers before preparing a new patch.
    recover_interrupted_client_transactions(&root)?;

    // Keys are Windows case-insensitive, even when validating on Linux.
    let mut plan: BTreeMap<String, (PathBuf, Option<Vec<u8>>)> = BTreeMap::new();
    let mut planned_bytes: usize = 0;
    for archive in archives {
        if archive.use_grf_merging || archive.target_grf_name.is_some() {
            return Err(Error::PatchFailed(
                "GRF archive cannot enter loose-file transaction".to_string()
            ));
        }
        for entry in archive.get_entries() {
            let (name, payload) = match entry {
                ThorEntry::Add { filename, data } => (filename, Some(data.clone())),
                ThorEntry::Remove { filename } => (filename, None),
            };
            let dest = checked_client_destination(&root, name)?;
            let key = name.replace('\\', "/").to_lowercase();
            if let Some((previous, _)) = plan.get(&key) {
                if previous != &dest {
                    return Err(Error::PatchFailed(format!(
                        "Conflicting client path casing: {}", name
                    )));
                }
            }
            if let Some(ref bytes) = payload {
                planned_bytes = planned_bytes.checked_add(bytes.len())
                    .ok_or_else(|| Error::PatchFailed("Patch payload size overflow".to_string()))?;
                if planned_bytes > 512 * 1024 * 1024 {
                    return Err(Error::PatchFailed(
                        "Loose THOR batch exceeds 512 MiB safety budget".to_string()
                    ));
                }
            }
            plan.insert(key, (dest, payload));
        }
    }
    if plan.is_empty() {
        return Ok(());
    }

    let timestamp = SystemTime::now().duration_since(UNIX_EPOCH)
        .map_err(|e| Error::PatchFailed(e.to_string()))?.as_nanos();
    let staging_root = root.join(format!(
        ".beam-patch-txn-{}-{timestamp}", std::process::id()
    ));
    std::fs::create_dir(&staging_root)?;
    recovery_marker(&staging_root, "PREPARING")?;

    let prepared: Result<Vec<ClientChange>> = (|| {
        let mut changes = Vec::with_capacity(plan.len());
        for (index, (_, (dest, contents))) in plan.iter().enumerate() {
            // Re-check before touching any destination; reject pre-existing
            // symlinks rather than following them during copy/restore.
            let relative = dest.strip_prefix(&root)
                .map_err(|_| Error::PatchFailed("Destination escaped game root".to_string()))?;
            let relative_name = relative.to_string_lossy().replace('\\', "/");
            checked_client_destination(&root, &relative_name)?;

            let backup = if dest.exists() {
                let path = staging_root.join(format!("backup-{index}"));
                std::fs::copy(dest, &path)?;
                sync_file(&path)?;
                Some(path)
            } else {
                None
            };
            let staged = if let Some(bytes) = contents {
                let path = staging_root.join(format!("new-{index}"));
                std::fs::write(&path, bytes)?;
                sync_file(&path)?;
                Some(path)
            } else {
                None
            };
            changes.push(ClientChange {
                destination: dest.clone(), backup, staged
            });
        }
        Ok(changes)
    })();

    let changes = match prepared {
        Ok(changes) => changes,
        Err(error) => {
            let _ = std::fs::remove_dir_all(&staging_root);
            return Err(error);
        }
    };
    // Only permit client writes after durable metadata and all backups exist.
    if let Err(error) = store_recovery_journal(&staging_root, &changes, &root)
        .and_then(|()| recovery_marker(&staging_root, "COMMITTING"))
    {
        let _ = std::fs::remove_dir_all(&staging_root);
        return Err(error);
    }
    let mut touched = Vec::new();
    let mut failure = None;
    for (idx, item) in changes.iter().enumerate() {
        let attempt: Result<()> = (|| {
            let relative = item.destination.strip_prefix(&root)
                .map_err(|_| Error::PatchFailed("Destination escaped root".to_string()))?;
            checked_client_destination(&root, &relative.to_string_lossy())?;
            if let Some(parent) = item.destination.parent() {
                std::fs::create_dir_all(parent)?;
            }
            // Include the current entry before any operation so rollback can
            // recover it if removing/replacing the destination fails midway.
            touched.push(idx);
            if item.destination.exists() {
                std::fs::remove_file(&item.destination)?;
            }
            if let Some(ref staged) = item.staged {
                std::fs::rename(staged, &item.destination)?;
            }
            Ok(())
        })();
        if let Err(error) = attempt {
            failure = Some(error);
            break;
        }
    }

    if failure.is_none() {
        // A successful batch receives its own durable state marker; on the
        // next run, interrupted cleanup will not undo completed updates.
        if let Err(error) = recovery_marker(&staging_root, "COMMITTED") {
            failure = Some(error);
        }
    }

    if let Some(error) = failure {
        let mut rollback_error = None;
        for idx in touched.into_iter().rev() {
            let change = &changes[idx];
            let restore: Result<()> = (|| {
                if change.destination.exists() {
                    std::fs::remove_file(&change.destination)?;
                }
                if let Some(ref backup) = change.backup {
                    std::fs::copy(backup, &change.destination)?;
                    sync_file(&change.destination)?;
                }
                Ok(())
            })();
            if let Err(e) = restore {
                rollback_error = Some(e);
            }
        }
        if let Some(rollback_failure) = rollback_error {
            return Err(Error::PatchFailed(format!(
                "{error}; rollback also failed: {rollback_failure}. \
                 Preserve recovery backups in {}",
                staging_root.display()
            )));
        }
        let _ = std::fs::remove_dir_all(&staging_root);
        return Err(error);
    }

    // Successful commit; original bytes remain in backup until this point.
    let _ = std::fs::remove_dir_all(staging_root);
    Ok(())
}


/// Each BEAM patcher instance owns a unique temporary download directory.
/// Never share a fixed OS-temp patch filename between independent clients.
fn create_patch_temp_dir() -> Result<PathBuf> {
    use std::time::{SystemTime, UNIX_EPOCH};
    let temporary_root = std::env::temp_dir();
    for attempt in 0..16u32 {
        let nanos = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .map_err(|e| Error::PatchFailed(format!("Clock error: {e}")))?
            .as_nanos();
        let path = temporary_root.join(format!(
            "beam-patcher-{}-{}-{attempt}",
            std::process::id(),
            nanos
        ));
        match std::fs::create_dir(&path) {
            Ok(()) => return Ok(path),
            Err(err) if err.kind() == std::io::ErrorKind::AlreadyExists => continue,
            Err(err) => return Err(err.into()),
        }
    }
    Err(Error::PatchFailed(
        "Unable to allocate an isolated temporary patch directory".to_string()
    ))
}

/// Offline, user-safe THOR acceptance check.
/// NEVER targets a real Ragnarok directory. A fresh OS temporary directory
/// is allocated by this function and removed when the test ends.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct ThorSandboxReport {
    pub verified_files: usize,
    pub deleted_files: usize,
    pub no_grf_written: bool,
}

struct ThorSandboxGuard(PathBuf);

impl Drop for ThorSandboxGuard {
    fn drop(&mut self) {
        let _ = std::fs::remove_dir_all(&self.0);
    }
}

/// Verify the actual BEAM client installer against a THOR without mutating
/// anything outside a uniquely allocated, disposable OS-temp directory.
pub fn smoke_test_loose_thor(patch_path: &Path) -> Result<ThorSandboxReport> {
    use std::collections::BTreeMap;

    let archive = Thor::open(patch_path)?;
    if archive.use_grf_merging || archive.target_grf_name.is_some() {
        return Err(Error::PatchFailed(
            "Sandbox test accepts loose-client THOR only (GRF merging forbidden)".to_string()
        ));
    }
    if archive.entries.is_empty() {
        return Err(Error::PatchFailed("Empty THOR is not a valid smoke fixture".into()));
    }

    // Collect expected final state. The parser already validates paths and
    // duplicate entries; this table also makes removal verification explicit.
    let mut expected: BTreeMap<String, Option<Vec<u8>>> = BTreeMap::new();
    for entry in archive.get_entries() {
        match entry {
            ThorEntry::Add { filename, data } => {
                validate_client_path(filename)?;
                expected.insert(filename.replace('\\', "/"), Some(data.clone()));
            }
            ThorEntry::Remove { filename } => {
                validate_client_path(filename)?;
                expected.insert(filename.replace('\\', "/"), None);
            }
        }
    }

    let sandbox = create_patch_temp_dir()?;
    let _cleanup = ThorSandboxGuard(sandbox.clone());
    // Test delete operations on an existing file, as well as new additions.
    for (name, content) in &expected {
        if content.is_none() {
            let target = checked_client_destination(&sandbox, name)?;
            if let Some(parent) = target.parent() {
                std::fs::create_dir_all(parent)?;
            }
            std::fs::write(target, b"dummy pre-existing file for THOR removal")?;
        }
    }

    let _lock = try_lock_client_root(&sandbox)?;
    apply_loose_thors(&sandbox, &[archive])?;
    let mut added = 0usize;
    let mut removed = 0usize;
    for (name, content) in &expected {
        let target = checked_client_destination(&sandbox, name)?;
        match content {
            Some(data) => {
                if std::fs::read(&target)? != *data {
                    return Err(Error::PatchFailed(format!(
                        "Sandbox result differs from THOR: {name}"
                    )));
                }
                added += 1;
            }
            None => {
                if target.exists() {
                    return Err(Error::PatchFailed(format!(
                        "Sandbox THOR removal failed: {name}"
                    )));
                }
                removed += 1;
            }
        }
    }

    // No GRF should ever appear in a loose-client patch smoke test.
    let mut no_grf = true;
    for item in std::fs::read_dir(&sandbox)? {
        let entry = item?;
        if entry.path().extension().and_then(|ext| ext.to_str()).is_some_and(|ext| ext.eq_ignore_ascii_case("grf")) {
            no_grf = false;
        }
    }
    if !no_grf {
        return Err(Error::PatchFailed(
            "Loose-client smoke test unexpectedly wrote a GRF".into()
        ));
    }
    Ok(ThorSandboxReport {
        verified_files: added,
        deleted_files: removed,
        no_grf_written: no_grf,
    })
}

pub struct Patcher {
    config: Config,
    downloader: Downloader,
    temp_dir: PathBuf,
    compatibility_guard: Option<PatchCompatibilityGuard>,
}

impl Drop for Patcher {
    fn drop(&mut self) {
        // Never wipe a shared temp directory; only the per-instance path.
        let _ = std::fs::remove_dir_all(&self.temp_dir);
    }
}

impl Patcher {
    pub fn new(config: Config) -> Result<Self> {
        // Refuse unregistered custom overlays before touching the downloader or temp files.
        crate::grf_layer_guard::require_tdata1_layer_ready(&config)?;
        // Validate the protected client identity before downloader or temp writes.
        let compatibility_guard = PatchCompatibilityGuard::new(&config)?;
        let downloader = Downloader::new(config.clone())?;
        let temp_dir = create_patch_temp_dir()?;

        Ok(Patcher {
            config,
            downloader,
            temp_dir,
            compatibility_guard,
        })
    }

    pub async fn check_available_patches(&self) -> Result<usize> {
        info!("Checking for available patches");

        self.ensure_recovered_client_state()?;
        let patches = self.downloader.download_patch_list().await?;
        let patch_count = patches.len();

        if patch_count > 0 {
            info!("Found {} patches available for download", patch_count);
        } else {
            info!("No patches available, client is up to date");
        }

        Ok(patch_count)
    }

    pub async fn get_patch_list(&self) -> Result<Vec<PatchInfo>> {
        self.ensure_recovered_client_state()?;
        self.downloader.download_patch_list().await
    }

    /// Apply a single patch with download progress, opening + saving the GRF
    /// for just this patch. Prefer `download_and_apply_patches` when you have
    /// more than one patch to apply — the batched form opens the GRF once and
    /// rebuilds it once, which is dramatically faster on large GRF files.
    pub async fn download_and_apply_patch<F>(
        &self,
        patch: &PatchInfo,
        progress_callback: F,
    ) -> Result<()>
    where
        F: FnMut(u64, u64) + Send + 'static,
    {
        if let Some(guard) = &self.compatibility_guard {
            guard.validate_name(&patch.filename)?;
        }
        self.ensure_recovered_client_state()?;
        validate_patch_filename(&patch.filename)?;
        let patch_path = self.temp_dir.join(&patch.filename);

        self.downloader
            .download_file_with_progress(&patch.filename, &patch_path, progress_callback)
            .await?;

        // Reject a short or oversized download before archive parsing or disk writes.
        if let Some(expected) = patch.size {
            let actual = tokio::fs::metadata(&patch_path).await?.len();
            if actual != expected {
                return Err(Error::PatchFailed(format!(
                    "Patch '{}' size mismatch: got {}, expected {}",
                    patch.filename, actual, expected
                )));
            }
        }
        if let Some(checksum) = &patch.checksum {
            if !self.downloader.verify_checksum(&patch_path, checksum).await? {
                return Err(Error::PatchFailed(format!(
                    "Checksum mismatch for {}",
                    patch.filename
                )));
            }
        }

        self.apply_patch(&patch_path).await?;

        self.downloader.mark_patch_applied(&patch.filename)?;

        tokio::fs::remove_file(&patch_path).await?;

        Ok(())
    }

    /// Downloads/verifies everything before writing. GRF patches stay batched;
    /// loose-client THOR packages form one recoverable file transaction.
    /// Mixed GRF/loose batches are rejected pending tested ordering semantics.
    pub async fn download_and_apply_patches<F>(
        &self,
        patches: &[PatchInfo],
        progress: F,
    ) -> Result<()>
    where
        F: FnMut(usize, usize, u64, u64) + Send + 'static,
    {
        // Refuse unknown regional/channel patches before any lock or download.
        if let Some(guard) = &self.compatibility_guard {
            for patch in patches {
                guard.validate_name(&patch.filename)?;
            }
        }
        // Guard both GRF and loose file updates with a single client lock.
        // This includes the empty-list path: recover unfinished updates first.
        let client_root = self.get_game_root()?;
        let _lock = try_lock_client_root(&client_root)?;
        crate::grf_layer_guard::require_tdata1_layer_ready(&self.config)?;
        recover_interrupted_client_transactions(&client_root)?;
        if patches.is_empty() {
            return Ok(());
        }

        let total = patches.len();
        let progress = Arc::new(Mutex::new(progress));
        let mut staged = Vec::with_capacity(total);
        let mut loose_thors = Vec::new();
        let mut has_grf_patch = false;

        // Preflight archives and checksums without writing any game file.
        for (idx, patch) in patches.iter().enumerate() {
            info!("Preflighting patch {}/{}: {}", idx + 1, total, patch.filename);
            validate_patch_filename(&patch.filename)?;
            let patch_path = self.temp_dir.join(&patch.filename);
            let progress_for_dl = Arc::clone(&progress);
            self.downloader
                .download_file_with_progress(
                    &patch.filename,
                    &patch_path,
                    move |downloaded, total_bytes| {
                        if let Ok(mut callback) = progress_for_dl.lock() {
                            (*callback)(idx, total, downloaded, total_bytes);
                        }
                    },
                )
                .await?;

            if let Some(expected) = patch.size {
                let actual = tokio::fs::metadata(&patch_path).await?.len();
                if actual != expected {
                    return Err(Error::PatchFailed(format!(
                        "Patch '{}' size mismatch: got {}, expected {}",
                        patch.filename, actual, expected
                    )));
                }
            }

            if let Some(checksum) = &patch.checksum {
                if !self.downloader.verify_checksum(&patch_path, checksum).await? {
                    return Err(Error::PatchFailed(format!(
                        "Checksum mismatch for {}", patch.filename
                    )));
                }
            }

            // Bind archive bytes to the protected region/channel manifest before
            // parsing or applying either loose-client THOR or GRF patches.
            if let Some(guard) = &self.compatibility_guard {
                guard.validate_file(&patch_path)?;
            }
            let is_thor = patch_path.extension()
                .and_then(|extension| extension.to_str())
                .is_some_and(|extension| extension.eq_ignore_ascii_case("thor"));
            if is_thor {
                let archive = Thor::open(&patch_path)?;
                if archive.use_grf_merging {
                    has_grf_patch = true;
                    validate_thor_destination(&archive, &self.config.patcher.target_grf)?;
                } else {
                    if archive.target_grf_name.is_some() {
                        return Err(Error::PatchFailed(
                            "Loose THOR cannot name a GRF destination".to_string()
                        ));
                    }
                    loose_thors.push(archive);
                }
            } else {
                has_grf_patch = true;
            }
            staged.push((patch.filename.clone(), patch_path));
        }

        if has_grf_patch && !loose_thors.is_empty() {
            return Err(Error::PatchFailed(
                "Mixed GRF and loose-client patches must be published in separate \
                 ordered feeds until BEAM's mixed-mode transaction gate is tested."
                    .to_string(),
            ));
        }

        if has_grf_patch {
            let grf_path = self.get_grf_path()?;
            let mut grf = self.open_or_create_grf(&grf_path)?;
            for (_, path) in &staged {
                self.apply_patch_into_grf(path, &mut grf).await?;
            }
            // Re-check DATA.INI and registered overlay immediately before GRF save.
            crate::grf_layer_guard::require_tdata1_layer_ready(&self.config)?;
            grf.save()?;
        } else if !loose_thors.is_empty() {
            let root = self.get_game_root()?;
            apply_loose_thors(&root, &loose_thors)?;
        }

        // Record progress only after the entire batch has been persisted.
        for (name, path) in &staged {
            self.downloader.mark_patch_applied(name)?;
            let _ = tokio::fs::remove_file(path).await;
        }
        Ok(())
    }

    pub async fn run_full_patch(&self) -> Result<()> {
        info!("Starting full patch process");

        let patches = self.downloader.download_patch_list().await?;
        info!("Found {} patches to apply", patches.len());

        self.download_and_apply_patches(&patches, |idx, total, _, _| {
            debug!("Patch {}/{}", idx + 1, total);
        }).await?;

        info!("All patches applied successfully");
        Ok(())
    }

    /// One-shot apply: opens its own GRF, applies, saves.
    pub async fn apply_patch(&self, patch_path: &Path) -> Result<()> {
        if let Some(guard) = &self.compatibility_guard {
            guard.validate_file(patch_path)?;
        }
        let client_root = self.get_game_root()?;
        let _lock = try_lock_client_root(&client_root)?;
        crate::grf_layer_guard::require_tdata1_layer_ready(&self.config)?;
        recover_interrupted_client_transactions(&client_root)?;
        if patch_path.extension()
            .and_then(|extension| extension.to_str())
            .is_some_and(|extension| extension.eq_ignore_ascii_case("thor"))
        {
            let archive = Thor::open(patch_path)?;
            if !archive.use_grf_merging {
                if archive.target_grf_name.is_some() {
                    return Err(Error::PatchFailed(
                        "Loose THOR cannot name a GRF destination".to_string()
                    ));
                }
                return apply_loose_thors(&self.get_game_root()?, &[archive]);
            }
            validate_thor_destination(&archive, &self.config.patcher.target_grf)?;
        }
        let grf_path = self.get_grf_path()?;
        let mut grf = self.open_or_create_grf(&grf_path)?;
        self.apply_patch_into_grf(patch_path, &mut grf).await?;
        crate::grf_layer_guard::require_tdata1_layer_ready(&self.config)?;
        grf.save()?;
        Ok(())
    }

    /// Internal: stage the patch contents into a caller-owned GRF without saving.
    async fn apply_patch_into_grf(&self, patch_path: &Path, grf: &mut Grf) -> Result<()> {
        crate::grf_layer_guard::require_tdata1_layer_ready(&self.config)?;
        if let Some(guard) = &self.compatibility_guard {
            guard.validate_file(patch_path)?;
        }
        let extension = patch_path
            .extension()
            .and_then(|s| s.to_str())
            .unwrap_or("")
            .to_ascii_lowercase();

        info!("Applying patch: {:?} (type: {})", patch_path, extension);

        match extension.as_str() {
            "beam" => self.apply_beam_into(patch_path, grf),
            "thor" => self.apply_thor_into(patch_path, grf),
            "rgz"  => self.apply_rgz_into(patch_path, grf),
            "gpf"  => self.apply_gpf_into(patch_path, grf),
            other => {
                warn!("Unknown patch format: {}", other);
                Err(Error::PatchFailed(format!("Unknown patch format: {}", other)))
            }
        }
    }

    fn apply_beam_into(&self, patch_path: &Path, grf: &mut Grf) -> Result<()> {
        info!("Applying BEAM patch with MD5 verification");
        let beam = BeamArchive::open(patch_path)?;

        for filename in beam.list_files() {
            info!("Extracting and verifying: {}", filename);

            if !beam.verify_file(filename)? {
                return Err(Error::PatchFailed(format!(
                    "MD5 verification failed for: {}",
                    filename
                )));
            }

            let data = beam.extract_file(filename)?;

            let entry = beam.get_entry(filename)
                .ok_or_else(|| Error::PatchFailed(format!("Entry not found: {}", filename)))?;

            let grf_filename = entry.grf_path.as_ref().unwrap_or(&entry.filename);

            info!("Patching file: {} -> {} ({} bytes)", filename, grf_filename, data.len());
            grf.patch_file(grf_filename, &data)?;
        }
        Ok(())
    }

    fn apply_thor_into(&self, patch_path: &Path, grf: &mut Grf) -> Result<()> {
        let thor = Thor::open(patch_path)?;

        validate_thor_destination(&thor, &self.config.patcher.target_grf)?;

        for entry in thor.get_entries() {
            match entry {
                beam_formats::thor::ThorEntry::Add { filename, data } => {
                    info!("Adding/updating file: {}", filename);
                    grf.patch_file(filename, data)?;
                }
                beam_formats::thor::ThorEntry::Remove { filename } => {
                    info!("Removing file: {}", filename);
                    grf.remove_file(filename)?;
                }
            }
        }
        Ok(())
    }

    fn apply_rgz_into(&self, patch_path: &Path, grf: &mut Grf) -> Result<()> {
        let rgz = Rgz::open(patch_path)?;

        for entry in rgz.get_entries() {
            match entry {
                beam_formats::rgz::RgzEntry::File { name, data } => {
                    info!("Adding file: {}", name);
                    grf.patch_file(name, data)?;
                }
                beam_formats::rgz::RgzEntry::Directory { name } => {
                    debug!("Creating directory: {}", name);
                }
            }
        }
        Ok(())
    }

    fn apply_gpf_into(&self, patch_path: &Path, grf: &mut Grf) -> Result<()> {
        let gpf = Gpf::open(patch_path)?;

        for filename in gpf.list_files() {
            info!("Patching file: {}", filename);
            let data = gpf.extract_file(filename)?;
            grf.patch_file(filename, &data)?;
        }
        Ok(())
    }

    pub async fn manual_patch(&self, patch_path: &Path) -> Result<()> {
        if !self.config.patcher.allow_manual_patch {
            return Err(Error::PatchFailed(
                "Manual patching is disabled".to_string()
            ));
        }

        info!("Applying manual patch: {:?}", patch_path);
        self.apply_patch(patch_path).await
    }

    fn ensure_recovered_client_state(&self) -> Result<()> {
        let root = self.get_game_root()?;
        let _lock = try_lock_client_root(&root)?;
        crate::grf_layer_guard::require_tdata1_layer_ready(&self.config)?;
        recover_interrupted_client_transactions(&root)
    }

    fn get_game_root(&self) -> Result<PathBuf> {
        match &self.config.app.game_directory {
            Some(path) => Ok(std::fs::canonicalize(path)?),
            None => Ok(std::fs::canonicalize(crate::get_executable_dir()?)?),
        }
    }

    fn get_grf_path(&self) -> Result<PathBuf> {
        let grf_filename = &self.config.patcher.target_grf;

        if let Some(game_dir) = &self.config.app.game_directory {
            Ok(Path::new(game_dir).join(grf_filename))
        } else {
            let exe_dir = crate::get_executable_dir()?;
            Ok(exe_dir.join(grf_filename))
        }
    }

    fn open_or_create_grf(&self, path: &Path) -> Result<Grf> {
        if path.exists() {
            info!("Opening existing GRF: {:?}", path);
            Ok(Grf::open(path)?)
        } else {
            info!("GRF not found, creating new: {:?}", path);
            Ok(Grf::create_new(path)?)
        }
    }
}


#[cfg(test)]
mod thor_guards_tests {
    use super::*;




    /// End-to-end fixture supplied by CI from a pinned official release asset.
    /// No Ragnarok installation, GRF, network or launcher is touched by this test.
    #[test]
    fn real_roenglishre_2022_hybrid_thor_installs_in_disposable_directory() {
        let path = match std::env::var("BEAM_REAL_HYBRID_THOR") {
            Ok(path) => path,
            Err(_) => {
                eprintln!("SKIPPED: no pinned Hybrid THOR fixture provided");
                return;
            }
        };
        let archive = Thor::open(path).expect("decode published 2022 Hybrid THOR");
        assert!(!archive.use_grf_merging, "Hybrid THOR must not target a GRF");
        assert!(archive.target_grf_name.is_none(), "Hybrid THOR must not specify a GRF");
        assert!(!archive.entries.is_empty(), "Hybrid THOR cannot be empty");
        let file_paths: Vec<_> = archive.entries.iter().filter_map(|entry| match entry {
            ThorEntry::Add { filename, .. } => Some(filename.as_str()),
            ThorEntry::Remove { .. } => None,
        }).collect();
        assert!(
            file_paths.iter().any(|filename| filename.starts_with("SystemEN/") ||
                filename.starts_with("SystemEN\\")),
            "Hybrid fixture must contain SystemEN translation files"
        );
        assert!(
            file_paths.iter().any(|filename| filename.starts_with("data/") ||
                filename.starts_with("data\\")),
            "Hybrid fixture must contain data translation files"
        );

        let root = std::env::temp_dir().join(format!(
            "beam-hybrid-live-fixture-{}-{}",
            std::process::id(),
            std::time::SystemTime::now().duration_since(std::time::UNIX_EPOCH)
                .unwrap().as_nanos()
        ));
        std::fs::create_dir_all(&root).unwrap();
        apply_loose_thors(&root, &[archive]).expect("apply real Hybrid THOR to empty test root");
        assert!(!root.join("ragnardata.grf").exists(), "GRF must remain untouched");
        let mut checked = 0;
        for entry in Thor::open(std::env::var("BEAM_REAL_HYBRID_THOR").unwrap())
            .unwrap().entries.iter()
        {
            if let ThorEntry::Add { filename, data } = entry {
                let target = root.join(filename.replace('\\', "/"));
                assert_eq!(std::fs::read(&target).expect("installed client file"), *data);
                checked += 1;
            }
        }
        assert!(checked > 0, "at least one installed file must be compared");
        std::fs::remove_dir_all(root).expect("cleanup disposable fixture root");
        eprintln!("Hybrid THOR loose-client fixture: verified {checked} files");
    }

    #[test]
    fn patcher_instances_use_distinct_download_directories() {
        let first = create_patch_temp_dir().expect("first patcher temp dir");
        let second = create_patch_temp_dir().expect("second patcher temp dir");
        assert_ne!(first, second, "separate updater instances cannot share downloads");
        assert!(first.is_dir() && second.is_dir());
        assert!(!first.parent().unwrap().join("beam_patcher").is_dir()
            || first != second);
        std::fs::remove_dir_all(first).unwrap();
        std::fs::remove_dir_all(second).unwrap();
    }

    #[test]
    fn client_lock_rejects_parallel_updaters() {
        let root = std::env::temp_dir().join(format!(
            "beam-loose-lock-{}-{}", std::process::id(), 806
        ));
        let _ = std::fs::remove_dir_all(&root);
        std::fs::create_dir_all(&root).unwrap();
        let first = try_lock_client_root(&root).expect("first writer gets lock");
        assert!(try_lock_client_root(&root).is_err(), "second writer must fail");
        drop(first);
        let second = try_lock_client_root(&root).expect("released lock can be obtained");
        drop(second);
        assert!(checked_client_destination(&root, ".beam-patch.lock").is_err());
        std::fs::remove_dir_all(root).unwrap();
    }

    #[test]
    fn recovers_interrupted_client_write_from_durable_backup() {
        let root = std::env::temp_dir().join(format!(
            "beam-loose-recovery-{}-{}", std::process::id(), 801
        ));
        let _ = std::fs::remove_dir_all(&root);
        std::fs::create_dir_all(root.join("data")).unwrap();
        let path = root.join("data/existing.txt");
        std::fs::write(&path, b"original").unwrap();
        let txn = root.join(".beam-patch-txn-fixture");
        std::fs::create_dir(&txn).unwrap();
        recovery_marker(&txn, "PREPARING").unwrap();
        let backup = txn.join("backup-0");
        std::fs::copy(&path, &backup).unwrap();
        std::fs::write(&path, b"incomplete-update").unwrap();
        let changes = [ClientChange {
            destination: path.clone(), staged: None, backup: Some(backup),
        }];
        store_recovery_journal(&txn, &changes, &root).unwrap();
        recovery_marker(&txn, "COMMITTING").unwrap();

        recover_interrupted_client_transactions(&root).unwrap();
        assert_eq!(std::fs::read(&path).unwrap(), b"original");
        assert!(!txn.exists());
        std::fs::remove_dir_all(root).unwrap();
    }

    #[test]
    fn cleans_preparing_transaction_without_client_changes() {
        let root = std::env::temp_dir().join(format!(
            "beam-loose-preparing-{}-{}", std::process::id(), 802
        ));
        let _ = std::fs::remove_dir_all(&root);
        std::fs::create_dir_all(&root).unwrap();
        let txn = root.join(".beam-patch-txn-fixture");
        std::fs::create_dir(&txn).unwrap();
        recovery_marker(&txn, "PREPARING").unwrap();
        recover_interrupted_client_transactions(&root).unwrap();
        assert!(!txn.exists());
        std::fs::remove_dir_all(root).unwrap();
    }

    #[test]
    fn committed_transaction_cleans_up_without_reverting_files() {
        let root = std::env::temp_dir().join(format!(
            "beam-loose-committed-{}-{}", std::process::id(), 803
        ));
        let _ = std::fs::remove_dir_all(&root);
        std::fs::create_dir_all(&root).unwrap();
        let original = root.join("names.txt");
        std::fs::write(&original, b"updated").unwrap();
        let txn = root.join(".beam-patch-txn-fixture");
        std::fs::create_dir(&txn).unwrap();
        recovery_marker(&txn, "PREPARING").unwrap();
        recovery_marker(&txn, "COMMITTED").unwrap();
        recover_interrupted_client_transactions(&root).unwrap();
        assert_eq!(std::fs::read(&original).unwrap(), b"updated");
        assert!(!txn.exists());
        std::fs::remove_dir_all(root).unwrap();
    }

    #[test]
    fn missing_backup_blocks_recovery_without_overwriting_client() {
        let root = std::env::temp_dir().join(format!(
            "beam-loose-missing-{}-{}", std::process::id(), 804
        ));
        let _ = std::fs::remove_dir_all(&root);
        std::fs::create_dir_all(&root).unwrap();
        let target = root.join("original.txt");
        std::fs::write(&target, b"partially-updated").unwrap();
        let txn = root.join(".beam-patch-txn-fixture");
        std::fs::create_dir(&txn).unwrap();
        recovery_marker(&txn, "PREPARING").unwrap();
        let changes = [ClientChange {
            destination: target.clone(),
            staged: None,
            backup: Some(txn.join("backup-0")),
        }];
        store_recovery_journal(&txn, &changes, &root).unwrap();
        recovery_marker(&txn, "COMMITTING").unwrap();

        assert!(recover_interrupted_client_transactions(&root).is_err());
        assert_eq!(std::fs::read(&target).unwrap(), b"partially-updated");
        assert!(txn.exists(), "preserve journal for manual recovery");
        std::fs::remove_dir_all(root).unwrap();
    }

    #[test]
    fn refuses_patcher_internal_directory_names_in_thor() {
        let root = std::env::temp_dir().join(format!(
            "beam-loose-protected-{}-{}", std::process::id(), 805
        ));
        let _ = std::fs::remove_dir_all(&root);
        std::fs::create_dir_all(&root).unwrap();
        assert!(checked_client_destination(&root, ".patch_cache/applied_patches.txt").is_err());
        assert!(checked_client_destination(&root, ".beam-patch-txn-forged/journal.json").is_err());
        let mut patch = Thor::new();
        patch.add_file(".patch_cache/applied_patches.txt", b"fake-state");
        assert!(apply_loose_thors(&root, &[patch]).is_err());
        std::fs::remove_dir_all(root).unwrap();
    }

    #[test]
    fn applies_loose_client_thor_without_creating_grf() {
        let root = std::env::temp_dir().join(format!(
            "beam-loose-test-{}-{}", std::process::id(), 703
        ));
        let _ = std::fs::remove_dir_all(&root);
        std::fs::create_dir_all(root.join("data")).unwrap();
        std::fs::write(root.join("data/removed.txt"), b"remove-me").unwrap();

        let mut patch = Thor::new();
        patch.add_file("SystemEN/LuaFiles514/itemInfo.lua", b"translated");
        patch.add_file("data/new.txt", b"new-data");
        patch.remove_file("data/removed.txt");
        apply_loose_thors(&root, &[patch]).unwrap();
        assert_eq!(
            std::fs::read(root.join("SystemEN/LuaFiles514/itemInfo.lua")).unwrap(),
            b"translated"
        );
        assert_eq!(std::fs::read(root.join("data/new.txt")).unwrap(), b"new-data");
        assert!(!root.join("data/removed.txt").exists());
        assert!(!root.join("ragnardata.grf").exists());
        std::fs::remove_dir_all(root).unwrap();
    }

    #[test]
    fn refuses_unsafe_path_before_modifying_client() {
        let root = std::env::temp_dir().join(format!(
            "beam-loose-unsafe-{}-{}", std::process::id(), 704
        ));
        let _ = std::fs::remove_dir_all(&root);
        std::fs::create_dir_all(&root).unwrap();
        std::fs::write(root.join("keep.txt"), b"original").unwrap();
        let mut patch = Thor::new();
        patch.add_file("keep.txt", b"changed");
        patch.add_file("../escape.txt", b"unexpected");
        assert!(apply_loose_thors(&root, &[patch]).is_err());
        assert_eq!(std::fs::read(root.join("keep.txt")).unwrap(), b"original");
        std::fs::remove_dir_all(root).unwrap();
    }

    #[test]
    fn later_loose_thor_wins_in_correct_patch_order() {
        let root = std::env::temp_dir().join(format!(
            "beam-loose-order-{}-{}", std::process::id(), 705
        ));
        let _ = std::fs::remove_dir_all(&root);
        std::fs::create_dir_all(&root).unwrap();
        let mut first = Thor::new();
        first.add_file("SystemEN/names.txt", b"2015");
        let mut second = Thor::new();
        second.add_file("SystemEN/names.txt", b"2022");
        apply_loose_thors(&root, &[first, second]).unwrap();
        assert_eq!(std::fs::read(root.join("SystemEN/names.txt")).unwrap(), b"2022");
        std::fs::remove_dir_all(root).unwrap();
    }

    #[cfg(unix)]
    #[test]
    fn refuses_symlinked_client_ancestor() {
        use std::os::unix::fs::symlink;
        let root = std::env::temp_dir().join(format!(
            "beam-loose-link-{}-{}", std::process::id(), 706
        ));
        let external = std::env::temp_dir().join(format!(
            "beam-loose-outside-{}-{}", std::process::id(), 706
        ));
        let _ = std::fs::remove_dir_all(&root);
        let _ = std::fs::remove_dir_all(&external);
        std::fs::create_dir_all(&root).unwrap();
        std::fs::create_dir_all(&external).unwrap();
        symlink(&external, root.join("SystemEN")).unwrap();
        let mut archive = Thor::new();
        archive.add_file("SystemEN/evil.lua", b"surprise");
        assert!(apply_loose_thors(&root, &[archive]).is_err());
        assert!(!external.join("evil.lua").exists());
        std::fs::remove_dir_all(root).unwrap();
        std::fs::remove_dir_all(external).unwrap();
    }


    #[test]
    fn rejects_loose_client_thor_before_grf_write() {
        let mut archive = Thor::new();
        archive.add_file("SystemEN/LuaFiles514/itemInfo.lua", b"translation");
        assert!(!archive.use_grf_merging);
        assert!(validate_thor_destination(&archive, "ragnardata.grf").is_err());
    }

    #[test]
    fn validates_header_target_against_selected_grf() {
        let mut archive = Thor::new();
        archive.use_grf_merging = true;
        archive.target_grf_name = Some("ragnardata.grf".to_string());
        assert!(validate_thor_destination(&archive, "ragnardata.grf").is_ok());
        assert!(validate_thor_destination(&archive, "data.grf").is_err());
    }
}
