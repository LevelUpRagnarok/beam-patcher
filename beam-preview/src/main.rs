// Dosya Yolu: REPO_ROOT/beam-preview/src/main.rs
// Amac: BEAM Windows GUI onizleme controller komutlari ve guvenli branch sorgulari
// Modul - Rust
// Version: 0.6.0
// Aciklama: Deneysel laboratuvar planini yalnizca Service uzerinden olusturur; kurulum kapali
// Bagimli Oldugu Katman: Controller | Service | Tool | View | Language
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

mod config {
    pub mod branch_visibility;
    pub mod client_profiles;
    pub mod experiment_lab;
    pub mod trusted_signers;
}
mod services {
    pub mod branch_filter;
    pub mod experiment_lab;
    pub mod manifest_preflight;
    pub mod signed_manifest;
    pub mod package_integrity;
}
mod tools {
    pub mod manifest_reader;
    pub mod package_reader;
}

use serde::Serialize;
use std::path::Path;
use std::collections::HashSet;

const MAX_BRANCH_RESPONSE_BYTES: usize = 256 * 1024;
const GITHUB_BRANCH_QUERY_TIMEOUT_SECS: u64 = 12;

#[derive(Serialize)]
struct PreviewStatus {
    name: &'static str,
    mode: &'static str,
    game_mutations_enabled: bool,
    launcher_enabled: bool,
}

#[derive(Serialize)]
struct ThorPreviewReport {
    installed_files: usize,
    removed_files: usize,
    no_grf_written: bool,
}

#[tauri::command]
fn preview_status() -> PreviewStatus {
    PreviewStatus {
        name: "LevelUpRagnarok BEAM Patcher",
        mode: "Preview - Safe Mode",
        game_mutations_enabled: false,
        launcher_enabled: false,
    }
}

#[tauri::command]
async fn preview_verify_thor(path: String) -> Result<ThorPreviewReport, String> {
    tauri::async_runtime::spawn_blocking(move || {
        let candidate = Path::new(&path);
        if !candidate.is_file() ||
            candidate.extension().and_then(|e| e.to_str())
                .map(|e| !e.eq_ignore_ascii_case("thor")).unwrap_or(true)
        {
            return Err("Yalnizca yerel .thor dosyalari secilebilir.".to_string());
        }
        let len = std::fs::metadata(candidate)
            .map_err(|e| format!("THOR dosyasi okunamadi: {e}"))?.len();
        if len == 0 || len > 512 * 1024 * 1024 {
            return Err("THOR dosyasi boyut siniri asildi.".to_string());
        }
        let result = beam_core::patcher::smoke_test_loose_thor(candidate)
            .map_err(|e| format!("THOR test edilemedi: {e}"))?;
        Ok(ThorPreviewReport {
            installed_files: result.verified_files,
            removed_files: result.deleted_files,
            no_grf_written: result.no_grf_written,
        })
    }).await.map_err(|e| format!("THOR test islemi sonlandi: {e}"))?
}


/// Branch browsing is read-only; only public, hardcoded GitHub repositories
/// are accessible. It does not change installed game files or patch channels.
#[derive(serde::Serialize)]
struct BranchSummary {
    name: String,
    short_sha: String,
    sha: String,
    protected: bool,
}

#[derive(serde::Deserialize)]
struct GithubBranch {
    name: String,
    commit: GithubCommit,
    #[serde(default)]
    protected: bool,
}

#[derive(serde::Deserialize)]
struct GithubCommit {
    sha: String,
}

fn public_branch_source(project: &str) -> Result<&'static str, &'static str> {
    config::branch_visibility::public_branch_source(project)
}

fn parse_github_branches(bytes: &[u8]) -> Result<Vec<BranchSummary>, String> {
    if bytes.len() > MAX_BRANCH_RESPONSE_BYTES {
        return Err("GitHub yaniti beklenenden buyuk.".to_string());
    }
    let branches: Vec<GithubBranch> = serde_json::from_slice(bytes)
        .map_err(|e| format!("GitHub branch yaniti okunamadi: {e}"))?;
    let mut items = Vec::with_capacity(branches.len());
    let mut names = HashSet::with_capacity(branches.len());
    for branch in branches {
        let valid_name = !branch.name.is_empty()
            && branch.name.len() <= 255
            && !branch.name.chars().any(char::is_control);
        if !valid_name || branch.commit.sha.len() != 40
            || !branch.commit.sha.bytes().all(|b| b.is_ascii_hexdigit())
        {
            return Err("GitHub branch ismi veya SHA gecersiz.".to_string());
        }
        if !names.insert(branch.name.clone()) {
            return Err("GitHub yanitinda tekrarlanan branch adi var.".to_string());
        }
        items.push(BranchSummary {
            name: branch.name,
            short_sha: branch.commit.sha[..12].to_string(),
            sha: branch.commit.sha,
            protected: branch.protected,
        });
    }
    Ok(items)
}

#[tauri::command]
async fn preview_list_branches(project: String, include_all: bool) -> Result<Vec<BranchSummary>, String> {
    let repo = public_branch_source(&project).map_err(|message| message.to_string())?;
    // No credentials, user-entered URLs or redirect to a game-patch server.
    // The GitHub API response is used for display only.
    let url = format!("https://api.github.com/repos/{repo}/branches?per_page=100");
    let client = reqwest::Client::builder()
        .timeout(std::time::Duration::from_secs(GITHUB_BRANCH_QUERY_TIMEOUT_SECS))
        .redirect(reqwest::redirect::Policy::none())
        .build()
        .map_err(|e| format!("HTTPS istemcisi hazirlanamadi: {e}"))?;
    let mut response = client
        .get(&url)
        .header(reqwest::header::ACCEPT, "application/vnd.github+json")
        .header(reqwest::header::USER_AGENT, "LevelUpRagnarok-BEAM-GUI-Preview/0.2")
        .send()
        .await
        .map_err(|e| format!("GitHub ulasilamadi: {e}"))?
        .error_for_status()
        .map_err(|e| format!("GitHub branch sorgusu reddedildi: {e}"))?;
    if response.content_length().is_some_and(|size| size > MAX_BRANCH_RESPONSE_BYTES as u64) {
        return Err("GitHub yaniti beklenenden buyuk.".to_string());
    }
    let mut bytes = Vec::new();
    while let Some(chunk) = response.chunk().await
        .map_err(|e| format!("GitHub yaniti okunamadi: {e}"))?
    {
        if chunk.len() > MAX_BRANCH_RESPONSE_BYTES.saturating_sub(bytes.len()) {
            return Err("GitHub yaniti beklenenden buyuk.".to_string());
        }
        bytes.extend_from_slice(&chunk);
    }
    Ok(services::branch_filter::apply(
        &project,
        include_all,
        parse_github_branches(&bytes)?,
    ))
}

#[tauri::command]
async fn preview_check_manifest(
    path: String,
    profile: String,
    project: String,
    branch: String,
    sha: String,
) -> Result<services::manifest_preflight::ManifestPreflightReport, String> {
    tauri::async_runtime::spawn_blocking(move || {
        let input = tools::manifest_reader::read_local_json(
            &path, config::client_profiles::MAX_MANIFEST_BYTES,
        )?;
        services::manifest_preflight::check(&input, &profile, &project, &branch, &sha)
    })
    .await
    .map_err(|_| "Manifest kontrol islemi tamamlanamadi.".to_string())?
}

#[tauri::command]
async fn preview_check_signed_manifest(
    path: String,
    profile: String,
    project: String,
    branch: String,
    sha: String,
) -> Result<services::manifest_preflight::ManifestPreflightReport, String> {
    tauri::async_runtime::spawn_blocking(move || {
        let input = tools::manifest_reader::read_local_json(
            &path, config::trusted_signers::MAX_ENVELOPE_BYTES,
        )?;
        services::signed_manifest::check(
            &input, &profile, &project, &branch, &sha,
            config::trusted_signers::PRODUCTION_SIGNERS,
        )
    })
    .await
    .map_err(|_| "Imzali manifest kontrol islemi tamamlanamadi.".to_string())?
}

#[tauri::command]
fn preview_experiment_plan(
    profile: String,
    project: String,
    branch: String,
    sha: String,
) -> Result<services::experiment_lab::ExperimentPlan, String> {
    services::experiment_lab::build(&profile, &project, &branch, &sha)
}

#[tauri::command]
async fn preview_verify_local_package(
    manifest_path: String, package_path: String,
    profile: String, project: String, branch: String, sha: String,
) -> Result<services::manifest_preflight::ManifestPreflightReport, String> {
    tauri::async_runtime::spawn_blocking(move || {
        let bytes = tools::manifest_reader::read_local_json(
            &manifest_path, config::client_profiles::MAX_MANIFEST_BYTES,
        )?;
        services::package_integrity::verify_local_unsigned(
            &bytes, &package_path, &profile, &project, &branch, &sha,
        )
    })
    .await
    .map_err(|_| "Yerel paket incelemesi tamamlanamadi.".to_string())?
}

#[cfg(test)]
mod branch_profiles_tests {
    use super::*;

    #[test]
    fn restricts_branch_queries_to_public_allowlisted_repos() {
        assert_eq!(public_branch_source("beam").unwrap(), "LevelUpRagnarok/beam-patcher");
        assert_eq!(public_branch_source("translation").unwrap(), "b1glord/ROenglishRE");
        assert!(public_branch_source("client").is_err());
        assert!(public_branch_source("../../user/unsafe").is_err());
        assert!(public_branch_source("https://evil.example").is_err());
    }

    #[test]
    fn keeps_distinct_branch_names_when_commits_match() {
        let sample = br#"[{"name":"master","commit":{"sha":"af2191234a22e180fac62d179489b64f3d17a997"}},{"name":"archive/tr-2025-10-25","commit":{"sha":"af2191234a22e180fac62d179489b64f3d17a997"}}]"#;
        let branches = parse_github_branches(sample).unwrap();
        assert_eq!(branches.len(), 2);
        assert_ne!(branches[0].name, branches[1].name);
        assert_eq!(branches[0].sha, branches[1].sha);
    }

    #[test]
    fn rejects_duplicate_branch_names_and_oversized_payload() {
        let sample = br#"[{"name":"master","commit":{"sha":"af2191234a22e180fac62d179489b64f3d17a997"}},{"name":"master","commit":{"sha":"af2191234a22e180fac62d179489b64f3d17a997"}}]"#;
        assert!(parse_github_branches(sample).is_err());
        assert!(parse_github_branches(&vec![b'x'; MAX_BRANCH_RESPONSE_BYTES + 1]).is_err());
    }

    #[test]
    fn default_branch_filter_hides_legacy_but_advanced_lists_all() {
        let sample = br#"[{"name":"translation/tr","commit":{"sha":"8cfc3211f8ebba2542fe6b6a114a33af0871367e"}},{"name":"master","commit":{"sha":"af2191234a22e180fac62d179489b64f3d17a997"}},{"name":"release/old-test","commit":{"sha":"8367640e3d9139415dca9e03083dc9b8ae60fd33"}},{"name":"upstream/latest","commit":{"sha":"85f216a230bf9180451fa29a37505baeb676c559"}}]"#;
        let parsed = parse_github_branches(sample).unwrap();
        let visible = services::branch_filter::apply(
            config::branch_visibility::PROJECT_TRANSLATION, false,
            parse_github_branches(sample).unwrap(),
        );
        assert_eq!(parsed.len(), 4);
        assert_eq!(visible.len(), 3);
        assert!(visible.iter().all(|b| b.name != "release/old-test"));
        let all = services::branch_filter::apply(
            config::branch_visibility::PROJECT_TRANSLATION, true, parsed,
        );
        assert_eq!(all.len(), 4);
        let beam = services::branch_filter::apply(
            config::branch_visibility::PROJECT_BEAM, false,
            parse_github_branches(sample).unwrap(),
        );
        assert!(beam.is_empty());
    }

    #[test]
    fn validates_branch_sha_without_downloading_any_patches() {
        let sample = br#"[{"name":"translation/tr","commit":{"sha":"8cfc3211f8ebba2542fe6b6a114a33af0871367e"},"protected":false}]"#;
        let branches = parse_github_branches(sample).unwrap();
        assert_eq!(branches.len(), 1);
        assert_eq!(branches[0].name, "translation/tr");
        assert_eq!(branches[0].short_sha, "8cfc3211f8eb");
        assert!(!branches[0].protected);
        let malformed = br#"[{"name":"a","commit":{"sha":"BAD"},"protected":false}]"#;
        assert!(parse_github_branches(malformed).is_err());
    }
}

fn main() {
    tauri::Builder::default()
        .invoke_handler(tauri::generate_handler![
            preview_status,
            preview_verify_thor,
            preview_list_branches,
            preview_check_manifest,
            preview_check_signed_manifest,
            preview_experiment_plan,
            preview_verify_local_package
        ])
        .run(tauri::generate_context!())
        .expect("Unable to open isolated BEAM GUI Preview window");
}
