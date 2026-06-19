# TV_Series_Ripper

Headless Python TV series DVD ripper using HandBrakeCLI.

This small tool scans a DVD, selects likely episode titles based on runtime/chapters/resolution, and batch-encodes them with HandBrakeCLI into files named like Show_S01E01.mp4. It's intended for unattended or scripted ripping of TV-series DVDs.

## Features

- Scans DVD title information with HandBrakeCLI.
- Automatically selects likely episode titles by runtime and chapter count.
- De-duplicates near-identical titles (playlist obfuscation protection).
- Encodes selected titles to MP4 using HandBrakeCLI/x264 with configurable quality and preset.
- Dry-run mode to verify selection before encoding.
- Attempts to guess show/disc name via `lsdvd` (optional).

## Requirements

- Python 3.7+ (uses dataclasses)
- HandBrakeCLI installed and available on PATH
- Optional: `lsdvd` for better disc title detection
- A DVD device (e.g. /dev/sr0) or path to an ISO

On Debian/Ubuntu you can install prerequisites with:
- sudo apt install handbrake-cli lsdvd
(or use your platform's packages / Homebrew on macOS)

## Installation

Clone the repository (or copy the script) and ensure the script is executable:

git clone https://github.com/PNGuinn-sys/TV_Series_Ripper.git
cd TV_Series_Ripper
chmod +x handbrake_tv_series_ripper.py

## Usage

Basic example (rip season 1 from default DVD device):

python3 handbrake_tv_series_ripper.py --season 1 --device /dev/sr0

Run a scan-only dry run to list chosen titles without encoding:

python3 handbrake_tv_series_ripper.py --season 1 --device /dev/sr0 --dry-run

By default output files are written to `./output_tv` as:
ShowName_S01E01.mp4, ShowName_S01E02.mp4, ...

## Command-line options

- --device: DVD device or input path (default: /dev/sr0)
- --output-dir: Directory to write MP4 files (default: ./output_tv)
- --season: Season number (required)
- --show: Manually specify show/disc name (overrides lsdvd)
- --min-minutes: Minimum runtime to consider an episode (default: 18)
- --max-minutes: Maximum runtime to consider an episode (default: 70)
- --start-episode: Starting episode number for naming (default: 1)
- --quality: HandBrake RF quality (lower => larger/better) (default: 22)
- --preset: HandBrake preset name (default: "Fast 480p30")
- --dry-run: Scan and print selected titles without encoding

## How selection works (summary)

1. Script runs `HandBrakeCLI --scan --json` to gather title metadata.
2. Titles are filtered by runtime (min/max minutes) and a minimum chapter count (>=3).
3. Near-duplicate titles are removed by comparing duration, chapter count, and resolution within a small tolerance.
4. Selected titles are encoded one-by-one with HandBrakeCLI and named Show_SxxExx.mp4.

## Exit codes and basic failure handling

- 1: Missing required binary (HandBrakeCLI)
- 2: HandBrakeCLI scan failed
- 3: No titles found during scan
- 4: No likely episodes found with current filters
- 5: One or more titles failed to encode

The script checks encoded file size (> ~50MB) to determine success.

## Troubleshooting & tips

- If zero candidates are found, try lowering `--min-minutes` or raising `--max-minutes`.
- For discs with poor metadata, use `--show` to set a proper show name.
- If `HandBrakeCLI` logs non-JSON text around scan output, the script extracts the first JSON object; if you see parse errors, run `HandBrakeCLI --scan --json --input /dev/sr0` manually to inspect output.
- Pick presets and quality according to your needs; `--quality` is RF (lower → better). For standard-definition DVDs the default preset works fine.

## Example

Dry-run to verify picks:

python3 handbrake_tv_series_ripper.py --season 2 --device /dev/sr0 --dry-run

Full encode:

python3 handbrake_tv_series_ripper.py --season 2 --device /dev/sr0 --quality 20 --preset "Fast 480p30"

## Contributing

Bug reports, fixes and improvements welcome. Small, focused PRs or issues with sample `HandBrakeCLI` scan output are most helpful.

## License

No license file is included in this repository. Add a LICENSE if you want to make usage terms explicit.
