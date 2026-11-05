// Dosya Yolu: REPO_ROOT/beam-preview/src/config/branch_visibility.rs
// Amac: BEAM branch goruntuleyicisinin depo ve varsayilan dal kurallarini merkezi tanimlar
// Modul - Config Rust
// Version: 0.1.0
// Aciklama: Test ve arsiv dallarini varsayilan listeden ayirir, gelismis gorunumu korur
// Bagimli Oldugu Katman: Service | Tool

pub const PROJECT_BEAM: &str = "beam";
pub const PROJECT_TRANSLATION: &str = "translation";
pub const PROJECT_CLIENT: &str = "client";

pub const REPOSITORY_BEAM: &str = "LevelUpRagnarok/beam-patcher";
pub const REPOSITORY_TRANSLATION: &str = "b1glord/ROenglishRE";

const BEAM_DEFAULT_BRANCHES: &[&str] = &[
    "main",
    "feat/thor-transactional-loose-client",
    "feat/windows-gui-preview",
];

const TRANSLATION_DEFAULT_BRANCHES: &[&str] = &[
    "master",
    "translation/tr",
    "upstream/latest",
];

pub fn public_branch_source(project: &str) -> Result<&'static str, &'static str> {
    match project {
        PROJECT_BEAM => Ok(REPOSITORY_BEAM),
        PROJECT_TRANSLATION => Ok(REPOSITORY_TRANSLATION),
        PROJECT_CLIENT => Err("RagnarokClient ozel bir repo. Token kullanmadan branch listesi alinamaz."),
        _ => Err("Desteklenmeyen GitHub projesi."),
    }
}

pub fn default_branches(project: &str) -> &'static [&'static str] {
    match project {
        PROJECT_BEAM => BEAM_DEFAULT_BRANCHES,
        PROJECT_TRANSLATION => TRANSLATION_DEFAULT_BRANCHES,
        _ => &[],
    }
}
