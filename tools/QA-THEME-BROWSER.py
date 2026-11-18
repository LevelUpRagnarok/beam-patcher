#!/usr/bin/env python3
# Dosya Yolu: tools/QA-THEME-BROWSER.py
# Amac: Dort Beam tema gorunumunu gercek Chromium uzerinde offline smoke ile dogrular
# Modul - Python / Playwright / Visual QA
# Version: 0.3.2-candidate
# Aciklama: Yerel dosyalardan render; Tauri komutlari salt okunur test doubles; oyun/patch yok
# Bagimli Oldugu Katman: beam-ui/public/index.html | assets/*.css | browser QA

"""Offline Chromium UI smoke and screenshot artifacts. Not a Tauri or gameplay test."""

import argparse
from contextlib import contextmanager
import functools
import hashlib
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
import shutil
from pathlib import Path
import sys
from threading import Thread

THEMES = ("default", "ragnar-legacy", "ragnar-classic", "levelup-modern")
PREFERENCE = "beam.launcher.theme.v1"
REPO_ROOT = Path(__file__).resolve().parents[1]
HTML = REPO_ROOT / "beam-ui/public/index.html"

# No real client, patch endpoint, game process, user credentials, or updater.
# Reads local HTML/CSS and injects an entirely inert Tauri command adapter.
MOCK_TAURI = r"""
(() => {
  const calls = [];
  window.__QA_NATIVE_CALLS = calls;
  const config = {
    app: {
      server_name: "TURKUAZ RAGNAROK ONLINE / OFFLINE QA",
      version: "0.1.0-qa",
      bgm_autoplay: false,
      video_background_enabled: false,
      limited_items: [],
      grid_images: ["assets/turkuaz-user-classic-castle.svg", "assets/turkuaz-user-adventurers.svg", "assets/turkuaz-user-poring.svg", "assets/turkuaz-dungeon.svg"],
      social_links: [],
      register_url: null
    },
    ui: {
      theme: "ragnar-legacy",
      status_image_url: null
    }
  };
  window.__TAURI__ = {
    tauri: {
      invoke: async (command, args) => {
        calls.push(command);
        switch (command) {
          case "get_config": return config;
          case "check_initial_setup": return false;
          case "get_news": return [
            { id: 1, title: "Turkuaz Ragnarok Online - offline QA", category: "event", url: "about:blank" },
            { id: 2, title: "Gorunum temalari", category: "event", url: "about:blank" }
          ];
          case "get_server_status":
            return { login_online: false, char_online: false, map_online: false };
          case "check_patches_available":
            throw new Error("OFFLINE_QA_NO_PATCH_ACCESS");
          case "open_setup": return null;
          case "resolve_resource_path":
            if (!["assets/turkuaz-user-classic-castle.svg", "assets/turkuaz-user-adventurers.svg", "assets/turkuaz-user-poring.svg", "assets/turkuaz-dungeon.svg"]
                .includes(args?.path)) {
              throw new Error("OFFLINE_QA_ASSET_DENIED");
            }
            return args.path;
          default: throw new Error("OFFLINE_QA_COMMAND_BLOCKED:" + command);
        }
      },
      convertFileSrc: (path) => new URL(path, window.location.href).href
    },
    window: {appWindow: {minimize: async () => {}, close: async () => {}}},
    event: {listen: async () => () => {}}
  };
})();
"""

QA_WATERMARK = """
body::after {
    content: "OFFLINE BROWSER QA - NOT A GAME CLIENT";
    position: fixed; z-index: 3000; bottom: 1px; left: 50%;
    transform: translateX(-50%);
    padding: 2px 9px; border-radius: 4px;
    color: #ffffff; background: #740d24; font: 600 10px Arial,sans-serif;
    white-space: nowrap; pointer-events: none;
}
"""


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


@contextmanager
def local_preview_server():
    # Bind only localhost; browser test never serves client files on a LAN.
    handler = functools.partial(SimpleHTTPRequestHandler, directory=str(HTML.parent))
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_address[1]}/index.html"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def run(output_dir, source_sha):
    if not HTML.is_file():
        raise RuntimeError("Beam HTML is missing")
    if output_dir.exists() and any(output_dir.iterdir()):
        raise RuntimeError("QA_OUTPUT_ALREADY_EXISTS: do not overwrite existing evidence")
    output_dir.mkdir(parents=True, exist_ok=True)

    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise RuntimeError("Playwright is not installed; see theme QA docs") from exc

    artifacts = []
    with local_preview_server() as preview_url, sync_playwright() as pw:
        system_browser = next((shutil.which(name) for name in (
            "google-chrome", "chromium", "chromium-browser"
        ) if shutil.which(name)), None)
        if not system_browser:
            raise RuntimeError("SYSTEM_CHROME_REQUIRED: install Chrome/Chromium for browser QA")
        browser = pw.chromium.launch(headless=True, executable_path=system_browser)
        context = browser.new_context(viewport={"width": 900, "height": 620}, device_scale_factor=1)
        context.add_init_script(MOCK_TAURI)
        page = context.new_page()
        blocked = []

        def route(request_route):
            url = request_route.request.url
            # Same-origin localhost fixture is allowed; ALL external URLs are blocked.
            if (url.startswith("http://") or url.startswith("https://")) and not url.startswith(
                preview_url.rsplit("/", 1)[0] + "/"
            ):
                blocked.append(url.split("?", 1)[0])
                request_route.abort()
            else:
                request_route.continue_()

        page_errors = []
        page.on("pageerror", lambda err: page_errors.append(str(err)))
        page.route("**/*", route)
        page.goto(preview_url, wait_until="domcontentloaded", timeout=30000)
        try:
            page.wait_for_function("document.body.classList.contains('theme-ragnar-legacy')",
                                   timeout=8000)
        except Exception as exc:
            state = page.evaluate("""() => ({
                bodyClass: document.body.className,
                isTauri: typeof window.__TAURI__ !== 'undefined',
                calls: window.__QA_NATIVE_CALLS || [],
                selector: document.querySelector('#theme-settings-choice')?.value,
                applyTheme: typeof applyConfiguredTheme,
                news: document.querySelector('#news-cards')?.textContent?.slice(0,100)
            })""")
            raise RuntimeError(
                "INITIAL_THEME_NOT_READY: " + json.dumps(
                    {"state": state, "page_errors": page_errors[:8], "blocked": blocked[:8]},
                    ensure_ascii=True,
                )
            ) from exc
        page.add_style_tag(content=QA_WATERMARK)

        for theme in THEMES:
            # Open the real gear button and click each actual preview card.
            page.locator("#theme-settings-open").click(timeout=8000)
            panel = page.locator("#theme-settings-modal")
            require(panel.is_visible(), "Theme settings modal did not open")
            choice = panel.locator(f'button[data-launcher-theme="{theme}"]')
            choice.click(timeout=8000)
            require(choice.get_attribute("aria-pressed") == "true", f"{theme}: aria-pressed")
            require(
                page.locator("#theme-settings-choice").input_value() == theme,
                f"{theme}: native select not synced",
            )
            require(
                page.evaluate(
                    "(name) => window.localStorage.getItem('beam.launcher.theme.v1') === name",
                    theme,
                ),
                f"{theme}: preference not stored",
            )
            require(
                page.evaluate(
                    "(name) => name === 'default' ?"
                    " !document.body.classList.contains('theme-ragnar-classic') &&"
                    " !document.body.classList.contains('theme-ragnar-legacy') &&"
                    " !document.body.classList.contains('theme-levelup-modern') :"
                    " document.body.classList.contains('theme-' + name)",
                    theme,
                ),
                f"{theme}: wrong active body CSS",
            )
            regions = page.evaluate("""() => {
                const visible = (selector) => {
                    const element = document.querySelector(selector);
                    return element && getComputedStyle(element).display !== 'none';
                };
                return {
                    modernNav: visible('.modern-nav'),
                    modernHero: visible('.modern-hero'),
                    classicRail: visible('.classic-ad-rail')
                };
            }""")
            require(
                regions == {
                    "modernNav": theme == "levelup-modern",
                    "modernHero": theme == "levelup-modern",
                    "classicRail": theme == "ragnar-classic",
                },
                f"{theme}: inactive theme content visible: {regions}",
            )
            require(
                page.evaluate(
                    "() => !document.querySelector('#theme-settings-modal').hidden"
                ),
                f"{theme}: modal unexpectedly hidden",
            )
            panel.locator(".theme-settings-close").click()
            require(panel.is_hidden(), f"{theme}: modal did not close")
            page.locator("#news-cards .news-item").first.wait_for(timeout=8000)
            page.wait_for_function("""() => [...document.querySelectorAll('#image-grid img')]
                .every(img => img.complete && img.naturalWidth > 0 && img.naturalHeight > 0)
            """, timeout=10000)
            require(
                page.evaluate("""() => [...document.querySelectorAll('#image-grid img')]
                    .every(img => img.currentSrc.startsWith(document.baseURI.replace('index.html', 'assets/')))
                """),
                f"{theme}: grid image loaded from outside embedded frontend assets",
            )
            screenshot = output_dir / f"{theme}.png"
            page.screenshot(path=str(screenshot), animations="disabled")
            require(screenshot.stat().st_size > 5000, f"{theme}: suspicious screenshot")
            artifacts.append({"theme": theme, "file": screenshot.name, "sha256": digest(screenshot),
                              "bytes": screenshot.stat().st_size})

            if theme == "ragnar-classic":
                # User screenshot regression: maximized desktop browser must not
                # stretch the original 900x620 launcher/artwork to 1650x900.
                page.set_viewport_size({"width": 1650, "height": 900})
                layout = page.evaluate("""() => {
                    const box = (selector) => {
                        const r = document.querySelector(selector).getBoundingClientRect();
                        return {x:r.x, y:r.y, width:r.width, height:r.height,
                                right:r.right, bottom:r.bottom};
                    };
                    const news = document.querySelector('.news-section-main');
                    const progress = document.querySelector('.progress-bar-container');
                    return {
                        launcher: box('.patcher-container'),
                        banner: box('.turkuaz-reference-banner'),
                        left: box('.classic-ad-rail'),
                        news: box('.news-section-main'),
                        right: box('.image-grid-section'),
                        start: box('#play-button'),
                        bannerScale: getComputedStyle(
                            document.querySelector('.turkuaz-reference-banner')).backgroundSize,
                        sceneScale: getComputedStyle(news).backgroundSize,
                        progressOverflow: getComputedStyle(progress).overflow,
                        secondRail: getComputedStyle(progress, '::before').content
                    };
                }""")
                outer = layout["launcher"]
                require(abs(outer["width"] - 900) <= 2 and
                        abs(outer["height"] - 620) <= 2,
                        "Classic launcher stretched beyond reference size")
                require(abs(outer["x"] - 375) <= 3 and abs(outer["y"] - 140) <= 3,
                        "Classic launcher not centered in maximized browser")
                require(125 <= layout["banner"]["height"] <= 155 and
                        layout["bannerScale"] == "100% auto",
                        "Classic illustrated header aspect ratio/crop regression")
                require("auto 100%" in layout["sceneScale"],
                        "Classic castle is being blown up via cover")
                require(layout["progressOverflow"] == "visible" and
                        layout["secondRail"] not in ("none", "normal"),
                        "Classic second decorative progress rail is hidden")
                require(160 <= layout["left"]["width"] <= 174 and
                        154 <= layout["right"]["width"] <= 164,
                        "Classic promo columns no longer match the reference")
                for panel in ("left", "news", "right", "start"):
                    rect = layout[panel]
                    require(rect["width"] > 35 and rect["height"] > 35 and
                            rect["x"] >= outer["x"] - 3 and
                            rect["right"] <= outer["right"] + 3 and
                            rect["y"] >= outer["y"] - 3 and
                            rect["bottom"] <= outer["bottom"] + 3,
                            "Classic panel clipped outside launcher: " + panel)
                wide = output_dir / "ragnar-classic-maximized-browser.png"
                page.screenshot(path=str(wide), animations="disabled")
                require(wide.stat().st_size > 5000,
                        "Maximized-browser screenshot unexpectedly small")
                classic_wide_artifact = {
                    "file": wide.name, "sha256": digest(wide), "bytes": wide.stat().st_size,
                    "viewport": {"width": 1650, "height": 900}, "layout": layout
                }
                page.set_viewport_size({"width": 900, "height": 620})

        page.reload(wait_until="domcontentloaded")
        page.wait_for_function("document.body.classList.contains('theme-levelup-modern')")
        require(page.locator("#theme-settings-choice").input_value() == "levelup-modern",
                "Theme did not survive reload")
        require(
            page.evaluate("() => !window.__QA_NATIVE_CALLS.some(x => ['launch_game','start_patching','manual_patch','reset_cache'].includes(x))"),
            "Forbidden native command was called during theme QA",
        )
        require(page.locator("#theme-game-setup").is_enabled(),
                "Mocked Tauri setup should remain accessible")
        require(
            page.evaluate("() => window.__QA_NATIVE_CALLS.includes('check_patches_available')"),
            "Tauri-like launch path was not exercised",
        )
        # A separate browser context exercises the real UI's QA-only branch.
        # The mocked native adapter cannot launch game, patch or open a real
        # folder, and does not share theme preferences with the primary run.
        qa_context = browser.new_context(viewport={"width": 900, "height": 620})
        qa_mock = MOCK_TAURI.replace(
            "    ui: {", "    patcher: {qa_only: true}," + chr(10) + "    ui: {", 1
        )
        qa_context.add_init_script(qa_mock)
        qa_page = qa_context.new_page()
        qa_page.route("**/*", route)
        qa_page.goto(preview_url, wait_until="domcontentloaded", timeout=30000)
        qa_page.wait_for_function("document.getElementById('play-button')?.textContent === 'QA / Oyun Kapalı'",
                                  timeout=15000)
        require(qa_page.locator("#play-button").is_disabled(), "QA Play action should be disabled")
        qa_page.locator("#theme-settings-open").click()
        require(qa_page.locator("#qa-workspace-select").is_visible(),
                "QA folder selection must be accessible from Settings")
        require(qa_page.locator("#theme-game-setup").is_disabled(),
                "Unconfigured QA game setup must not launch")
        require(
            "TEST MODU" in qa_page.locator("#progress-label").inner_text(),
            "QA safety message not shown",
        )
        require(
            qa_page.evaluate("() => !window.__QA_NATIVE_CALLS.includes('check_patches_available')"),
            "QA build unexpectedly queried patch feed",
        )
        qa_context.close()

        # Standalone file:// / localhost browsing has no native backend,
        # even when the user omits ?theme=. Keep Play, Patch and Setup inert.
        standalone = browser.new_context(viewport={"width": 900, "height": 620})
        raw_page = standalone.new_page()
        raw_page.route("**/*", route)
        raw_page.goto(preview_url + "?theme=ragnar-classic",
                      wait_until="domcontentloaded", timeout=30000)
        raw_page.wait_for_function("""() => {
            const p = document.querySelector('#play-button');
            return p?.disabled && p.textContent.trim() === 'Preview Only' &&
                document.body.classList.contains('theme-ragnar-classic') &&
                document.body.classList.contains('theme-preview-only');
        }""", timeout=10000)
        require(raw_page.locator("#theme-settings-open").is_enabled(),
                "Standalone theme selector was disabled")
        require(raw_page.locator("#theme-game-setup").is_disabled(),
                "Standalone browser exposed real game settings")
        require(raw_page.locator(".btn-action-small[title='Manual Patch']").is_disabled(),
                "Standalone browser exposed patch command")
        icons = raw_page.evaluate("""() => Array.from(
            document.querySelectorAll('.btn-action-small')
        ).map(el => getComputedStyle(el, '::after').content)""")
        require(len(icons) == 3 and all(icon not in ("none", "normal", '""') for icon in icons),
                "Classic offline button glyphs are missing")
        for viewport in ({"width": 900, "height": 620},
                         {"width": 700, "height": 620}):
            raw_page.set_viewport_size(viewport)
            buttons = raw_page.evaluate("""() => {
                const rect = el => {
                    const b = el.getBoundingClientRect();
                    return {left: b.left, right: b.right, top: b.top,
                            bottom: b.bottom, width: b.width, height: b.height};
                };
                const row = document.querySelector('.button-row');
                const tools = [
                    document.querySelector('#theme-settings-open'),
                    document.querySelector('.btn-action-small[title="Manual Patch"]'),
                    document.querySelector('.btn-action-small[title="Reset Cache"]')
                ];
                return {
                    layout: getComputedStyle(row).display,
                    row: rect(row),
                    play: rect(document.querySelector('#play-button')),
                    tools: tools.map(rect)
                };
            }""")
            require(buttons["layout"] == "grid",
                    "Classic controls are not placed in the same grid")
            require(buttons["row"]["width"] > 0 and
                    buttons["play"]["left"] - max(t["right"] for t in buttons["tools"]) >= (5 if viewport["width"] <= 760 else 7),
                    f"Classic action tools overlap/touch play at {viewport}: {buttons}")
            require(all(buttons["tools"][i]["bottom"] + 1 <=
                        buttons["tools"][i + 1]["top"] for i in (0, 1)),
                    "Classic action tools overlap vertically")
            require(buttons["play"]["right"] <= buttons["row"]["right"] + 1 and
                    buttons["play"]["left"] >= buttons["row"]["left"] - 1,
                    "Classic play button overflows action grid")
        raw_page.set_viewport_size({"width": 900, "height": 620})
        direct_preview = output_dir / "ragnar-classic-browser-preview.png"
        raw_page.screenshot(path=str(direct_preview), animations="disabled")
        require(direct_preview.stat().st_size > 5000,
                "Standalone screenshot unexpectedly small")
        browser_preview_artifact = {
            "file": direct_preview.name, "sha256": digest(direct_preview),
            "bytes": direct_preview.stat().st_size
        }
        raw_page.goto(preview_url, wait_until="domcontentloaded", timeout=30000)
        raw_page.wait_for_function("""() => {
            const p = document.querySelector('#play-button');
            return p?.disabled && p.textContent.trim() === 'Preview Only' &&
                document.body.classList.contains('theme-preview-only');
        }""", timeout=10000)
        standalone.close()
        browser.close()

    summary = {
        "schema": "levelupgt.beam-theme-browser-qa.v1",
        "source_sha": source_sha,
        "browser": "Playwright Chromium (offline mocked Tauri; NOT WebView2)",
        "viewport": {"width": 900, "height": 620},
        "themes": list(THEMES),
        "preference_survived_reload": True,
        "embedded_grid_images_loaded": True,
        "game_or_patch_commands": 0,
        "qa_ui_blocks_play_and_patch_feed": True,
        "external_requests_blocked": len(blocked),
        "screenshots": artifacts,
        "classic_maximized_browser": classic_wide_artifact,
        "classic_standalone_browser": browser_preview_artifact,
        "standalone_browser_without_query_blocks_game": True,
        "desktop_webview2": "NOT RUN",
        "actual_gameplay": "NOT RUN",
        "published": False,
    }
    (output_dir / "qa-report.json").write_text(
        json.dumps(summary, ensure_ascii=True, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=True))
    return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=REPO_ROOT / "build/theme-visual-qa")
    parser.add_argument("--source-sha", default="unknown")
    args = parser.parse_args()
    try:
        return run(args.output_dir.resolve(), args.source_sha)
    except Exception as exc:
        print("THEME_BROWSER_QA_FAILED: " + str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
