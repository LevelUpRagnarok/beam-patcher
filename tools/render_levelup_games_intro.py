#!/usr/bin/env python3
# Dosya Yolu: tools/render_levelup_games_intro.py
# Amac: LevelUp Games markali QA giris videosunu Beam medya klasorunde uretmek
# Modul - Python / FFmpeg Media Tool
# Version: 0.1.1
# Aciklama: Indirilecek video gerekmeden kaynak kodundan MP4 uretir, mevcut dosyayi korur
# Bagimli Oldugu Katman: Beam UI | ffmpeg drawtext/libx264/aac

"""Generate optional LevelUp Games QA MP4 locally, without touching any game EXE/GRF."""

import argparse
from pathlib import Path
import shutil
import subprocess
import sys
import hashlib
import json

WIDTH, HEIGHT, FPS, SECONDS = 1280, 720, 24, 6


def locate_font():
    candidates = (
        Path("C:/Windows/Fonts/arialbd.ttf"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
        Path("/usr/share/fonts/truetype/lato/Lato-Heavy.ttf"),
    )
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    raise RuntimeError("No local Arial/DejaVu/Lato bold font found")


def require(condition, error):
    if not condition:
        raise RuntimeError(error)


def render(output: Path):
    require(shutil.which("ffmpeg") is not None, "FFMPEG_NOT_INSTALLED")
    output = Path(output).absolute()
    require(output.suffix.lower() == ".mp4" and
            output.name == "levelup-games-intro.mp4", "INVALID_OUTPUT_FILENAME")
    require(output.parent.is_dir() and not output.parent.is_symlink(), "OUTPUT_PARENT_MISSING")
    require(not output.exists() and not output.is_symlink(), "INTRO_OUTPUT_ALREADY_EXISTS")
    font = locate_font().as_posix()
    # FFmpeg drawtext treats ':' as an option separator; escape the Windows drive colon.
    font = font.replace(":", r"\:")
    vf = ",".join((
        "drawbox=x=0:y=0:w=iw:h=ih:color=0x071526:t=fill",
        "drawbox=x=95:y=88:w=1090:h=3:color=0x3bd5e8@0.75:t=fill",
        "drawbox=x=95:y=633:w=1090:h=2:color=0xe3b871@0.60:t=fill",
        "drawbox=x=420:y=225:w=440:h=3:color=0x33cce3@0.65:t=fill",
        f"drawtext=fontfile='{font}':text='LEVELUP':fontcolor=0xf5faff:"
        "fontsize=138:x=(w-text_w)/2:y=282",
        f"drawtext=fontfile='{font}':text='G A M E S':fontcolor=0xe9c27d:"
        "fontsize=58:x=(w-text_w)/2:y=470",
        f"drawtext=fontfile='{font}':text='A NEW WORLD BEGINS':fontcolor=0x99c9d7:"
        "fontsize=23:x=(w-text_w)/2:y=595",
        "fade=t=in:st=0:d=0.75",
        "fade=t=out:st=5.25:d=0.75",
    ))
    command = [
        shutil.which("ffmpeg"), "-hide_banner", "-loglevel", "error",
        "-nostdin", "-n",
        "-f", "lavfi", "-i",
        f"color=c=0x071526:s={WIDTH}x{HEIGHT}:r={FPS}:d={SECONDS}",
        "-f", "lavfi", "-i",
        f"sine=frequency=392:sample_rate=44100:duration={SECONDS}",
        "-vf", vf,
        "-af", "volume=0.08,afade=t=in:st=0:d=1,afade=t=out:st=5:d=1",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "19",
        "-pix_fmt", "yuv420p", "-r", str(FPS),
        "-c:a", "aac", "-b:a", "96k", "-movflags", "+faststart",
        str(output),
    ]
    try:
        subprocess.run(command, check=True, timeout=180)
        require(output.is_file() and 0 < output.stat().st_size <= 20 * 1024 * 1024,
                "INTRO_INVALID_SIZE")
        data_hash = hashlib.sha256(output.read_bytes()).hexdigest()
        return {
            "schema": "levelupgt.beam-intro-qa.v1",
            "path": str(output),
            "sha256": data_hash,
            "bytes": output.stat().st_size,
            "title": "LEVELUP GAMES",
            "seconds": SECONDS,
            "width": WIDTH,
            "height": HEIGHT,
            "game_exe_modified": False,
            "published": False,
            "note": "Generated Beam UI candidate, NOT the canonical fixed-SHA client intro MP4.",
        }
    except BaseException:
        # Keep any failed/partial candidate for explicit inspection; no deletion of
        # an output another process may have created after the initial check.
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path,
                        default=Path(__file__).resolve().parents[1] /
                        "beam-ui/public/assets/levelup-games-intro.mp4")
    args = parser.parse_args()
    try:
        print(json.dumps(render(args.output), ensure_ascii=False, sort_keys=True))
        return 0
    except (RuntimeError, OSError, subprocess.CalledProcessError,
            subprocess.TimeoutExpired) as error:
        print("BEAM_INTRO_RENDER_BLOCKED: " + str(error), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
