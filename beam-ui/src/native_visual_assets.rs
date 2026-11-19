// Dosya Yolu: REPO_ROOT/beam-ui/src/native_visual_assets.rs
// Amac: Native Tauri WebView2 icinde yerel tema CSS/SVG erisimini garanti etmek
// Modul - Rust / Native UI asset adapter
// Version: 0.1.0-candidate
// Aciklama: Sadece repo-ici dekoratif kaynaklar; oyun, patch, konfigurasyon degismez
// Bagimli Oldugu Katman: beam-ui/src/lib.rs | beam-ui/public/assets

use serde_json::json;
use tauri::Window;

/// WebView2 can display the embedded index while relative CSS/image URLs are
/// unavailable in portable QA. Inject the *same checked-in assets* into the
/// native DOM as a safe fallback; no network or game operations are involved.
/// All theme selectors remain opt-in and controlled by existing UI config.
pub(crate) fn install(window: &Window) {
    let sources = json!({
        "styles": [
            include_str!("../public/assets/ragnar-legacy.css"),
            include_str!("../public/assets/ragnar-classic.css"),
            include_str!("../public/assets/levelup-modern.css"),
            include_str!("../public/assets/turkuaz-premium.css"),
            include_str!("../public/assets/turkuaz-reference-restore.css")
        ],
        "images": {
            "turkuaz-castle.svg": include_str!("../public/assets/turkuaz-castle.svg"),
            "turkuaz-dungeon.svg": include_str!("../public/assets/turkuaz-dungeon.svg"),
            "turkuaz-poring.svg": include_str!("../public/assets/turkuaz-poring.svg"),
            "turkuaz-skycity.svg": include_str!("../public/assets/turkuaz-skycity.svg"),
            "turkuaz-user-adventurers.svg": include_str!("../public/assets/turkuaz-user-adventurers.svg"),
            "turkuaz-user-classic-castle.svg": include_str!("../public/assets/turkuaz-user-classic-castle.svg"),
            "turkuaz-user-classic-header.svg": include_str!("../public/assets/turkuaz-user-classic-header.svg"),
            "turkuaz-user-modern-hero.svg": include_str!("../public/assets/turkuaz-user-modern-hero.svg"),
            "turkuaz-user-poring.svg": include_str!("../public/assets/turkuaz-user-poring.svg")
        }
    });

    // JSON serialization provides JS string escaping. The files are build-time
    // assets, never remote URLs or user-controlled scripts.
    let script = format!(
        r#"(function () {{
            'use strict';
            if (document.getElementById('beam-native-visual-assets')) return;
            const assets = {sources};
            const imageUrls = Object.create(null);
            for (const [name, svg] of Object.entries(assets.images)) {{
                imageUrls[name] = 'data:image/svg+xml;charset=utf-8,' +
                    encodeURIComponent(svg);
            }}
            let css = assets.styles.join('\n');
            for (const [name, dataUrl] of Object.entries(imageUrls)) {{
                css = css.replaceAll("url('" + name + "')", "url('" + dataUrl + "')");
                css = css.replaceAll('url("' + name + '")', 'url("' + dataUrl + '")');
            }}
            const style = document.createElement('style');
            style.id = 'beam-native-visual-assets';
            style.textContent = css;
            document.head.appendChild(style);

            // Apply embedded local images only when the normal native image
            // source fails. Never replace successful network/server artwork.
            document.addEventListener('error', function (event) {{
                const img = event.target;
                if (!(img instanceof HTMLImageElement) ||
                    img.dataset.beamEmbeddedFallback === '1') return;
                const src = img.getAttribute('src') || '';
                const name = src.split(/[\\/]/).pop()?.split(/[?#]/)[0];
                if (!name || !imageUrls[name]) return;
                img.dataset.beamEmbeddedFallback = '1';
                img.src = imageUrls[name];
            }}, true);
        }})();"#,
        sources = sources
    );
    if let Err(error) = window.eval(&script) {
        tracing::warn!("Could not install native visual fallback: {error}");
    }
}
