#!/usr/bin/env python3
"""
Batch rip likely TV episodes from a DVD using HandBrakeCLI.

Workflow:
1. Scan all DVD titles with HandBrakeCLI --scan --json.
2. Select likely episode titles using runtime and duplicate filtering.
3. Encode selected titles to MP4 as Show_SxxExx.mp4.

Example:
  python3 handbrake_tv_series_ripper.py --season 1 --device /dev/sr0
"""

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple


@dataclass
class TitleInfo:
    index: int
    duration_seconds: int
    chapters: int
    width: int
    height: int


def require_binary(binary: str) -> None:
    if shutil.which(binary) is None:
        print(f"[!] Required binary not found: {binary}")
        print("    Install it and retry. On Ubuntu/Debian this is usually: sudo apt install handbrake-cli")
        sys.exit(1)


def sanitize_name(name: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", name.strip())
    cleaned = re.sub(r"_+", "_", cleaned).strip("_")
    return cleaned or "TV_Show"


def guess_show_name(device: str) -> str:
    # Prefer lsdvd disc title when available.
    if shutil.which("lsdvd"):
        try:
            result = subprocess.run(["lsdvd", device], capture_output=True, text=True, check=False)
            m = re.search(r"Disc Title:\s*(.+)", result.stdout)
            if m:
                return sanitize_name(m.group(1))
        except Exception:
            pass

    return "TV_Show"


def _extract_json_from_scan(output: str) -> Dict:
    # HandBrakeCLI includes logs around JSON; isolate the first object block.
    start = output.find("{")
    end = output.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("No JSON payload found in HandBrakeCLI scan output")
    return json.loads(output[start : end + 1])


def parse_duration_seconds(duration: Dict) -> int:
    return int(duration.get("Hours", 0)) * 3600 + int(duration.get("Minutes", 0)) * 60 + int(duration.get("Seconds", 0))


def scan_titles(device: str) -> List[TitleInfo]:
    cmd = ["HandBrakeCLI", "--input", device, "--title", "0", "--scan", "--json"]
    result = subprocess.run(cmd, capture_output=True, text=True, check=False)

    if result.returncode != 0:
        print("[!] HandBrakeCLI scan failed.")
        stderr = (result.stderr or "").strip()
        stdout = (result.stdout or "").strip()
        if stderr:
            print(stderr)
        elif stdout:
            print(stdout)
        sys.exit(2)

    payload = _extract_json_from_scan((result.stdout or "") + "\n" + (result.stderr or ""))
    titles = payload.get("TitleList", [])

    parsed: List[TitleInfo] = []
    for t in titles:
        duration = parse_duration_seconds(t.get("Duration", {}))
        geom = t.get("Geometry", {})
        parsed.append(
            TitleInfo(
                index=int(t.get("Index", 0)),
                duration_seconds=duration,
                chapters=len(t.get("ChapterList", [])),
                width=int(geom.get("Width", 0)),
                height=int(geom.get("Height", 0)),
            )
        )
    return parsed


def choose_episode_titles(
    titles: List[TitleInfo], min_minutes: int, max_minutes: int, dedupe_tolerance_seconds: int = 2
) -> List[TitleInfo]:
    min_s = min_minutes * 60
    max_s = max_minutes * 60

    # First filter by likely episode runtime.
    candidates = [t for t in titles if min_s <= t.duration_seconds <= max_s and t.chapters >= 3]

    # Remove likely duplicates caused by playlist obfuscation / repeated alt titles.
    # Key on near-identical runtime + chapter count + resolution.
    unique: List[TitleInfo] = []
    seen_keys: List[Tuple[int, int, int, int]] = []
    for t in sorted(candidates, key=lambda x: x.index):
        key = (t.duration_seconds, t.chapters, t.width, t.height)
        duplicate = False
        for sdur, sch, sw, sh in seen_keys:
            if sch == t.chapters and sw == t.width and sh == t.height and abs(sdur - t.duration_seconds) <= dedupe_tolerance_seconds:
                duplicate = True
                break
        if not duplicate:
            unique.append(t)
            seen_keys.append(key)

    return unique


def encode_title(
    device: str,
    title_idx: int,
    output_file: str,
    preset: str,
    quality: int,
    extra_args: Optional[List[str]] = None,
) -> int:
    cmd = [
        "HandBrakeCLI",
        "--input",
        device,
        "--title",
        str(title_idx),
        "--output",
        output_file,
        "--encoder",
        "x264",
        "--quality",
        str(quality),
        "--audio-lang-list",
        "eng",
        "--all-audio",
        "--aencoder",
        "av_aac",
        "--mixdown",
        "stereo",
        "--markers",
        "--decomb",
        "--preset",
        preset,
    ]
    if extra_args:
        cmd.extend(extra_args)

    proc = subprocess.run(cmd, check=False)
    return proc.returncode


def main() -> None:
    parser = argparse.ArgumentParser(description="Auto-rip likely TV episode titles from DVD using HandBrakeCLI")
    parser.add_argument("--device", default="/dev/sr0", help="DVD device path (default: /dev/sr0)")
    parser.add_argument("--output-dir", default="./output_tv", help="Output directory")
    parser.add_argument("--season", type=int, required=True, help="Season number, e.g. 1")
    parser.add_argument("--show", default=None, help="Override show/disc name")
    parser.add_argument("--min-minutes", type=int, default=18, help="Minimum runtime to consider an episode")
    parser.add_argument("--max-minutes", type=int, default=70, help="Maximum runtime to consider an episode")
    parser.add_argument("--start-episode", type=int, default=1, help="Start episode number")
    parser.add_argument("--quality", type=int, default=22, help="HandBrake RF quality (lower is bigger/better)")
    parser.add_argument("--preset", default="Fast 480p30", help="HandBrake preset name")
    parser.add_argument("--dry-run", action="store_true", help="Scan and print selected titles without encoding")
    args = parser.parse_args()

    require_binary("HandBrakeCLI")
    os.makedirs(args.output_dir, exist_ok=True)

    show_name = sanitize_name(args.show) if args.show else guess_show_name(args.device)
    season_str = f"S{args.season:02d}"

    print(f"[+] Scanning {args.device} with HandBrakeCLI...")
    titles = scan_titles(args.device)
    if not titles:
        print("[!] No titles found during scan.")
        sys.exit(3)

    chosen = choose_episode_titles(titles, args.min_minutes, args.max_minutes)

    print(f"[+] Total scanned titles: {len(titles)}")
    print(f"[+] Candidate episode titles: {len(chosen)}")
    if not chosen:
        print("[!] No likely episodes found with current filters.")
        print("    Try widening --min-minutes / --max-minutes.")
        sys.exit(4)

    for i, t in enumerate(chosen, start=args.start_episode):
        mins = t.duration_seconds / 60.0
        print(f"    - Title {t.index:02d} | {mins:.1f} min | {t.chapters} chapters | {t.width}x{t.height} -> E{i:02d}")

    if args.dry_run:
        print("[+] Dry run complete. No files encoded.")
        return

    failures = 0
    for i, t in enumerate(chosen, start=args.start_episode):
        ep = f"E{i:02d}"
        out_name = f"{show_name}_{season_str}{ep}.mp4"
        out_path = os.path.join(args.output_dir, out_name)
        print(f"\n[>] Encoding Title {t.index} -> {out_name}")

        rc = encode_title(
            device=args.device,
            title_idx=t.index,
            output_file=out_path,
            preset=args.preset,
            quality=args.quality,
        )

        if rc == 0 and os.path.exists(out_path) and os.path.getsize(out_path) > 50_000_000:
            print(f"    [+] Complete: {out_path}")
        else:
            failures += 1
            print(f"    [X] Failed title {t.index} (exit {rc})")

    if failures:
        print(f"\n[!] Finished with {failures} failed title(s).")
        sys.exit(5)

    print("\n[+] All selected episodes encoded successfully.")


if __name__ == "__main__":
    main()
