# speech2ay: command-line guide

Run these commands from the root of the `speech2ay` repository. Input files must be
uncompressed 8-bit or 16-bit PCM WAV. Stereo is averaged to mono. A directory
input includes its WAV files, sorted by name, without recursive searching.
Quote paths containing spaces. Output directories are created automatically.

The included assembly playback code is written for the Z80 processor, and the tools generate example executable programs specifically for the TS2068 computer. The AY conversion algorithms can also be used for other machines with suitable playback code and timing adaptations.

## Setup (PowerShell)

```powershell
python -m pip install -r requirements.txt
$env:PASMO = 'C:\tools\pasmo.exe'
$ayumi = 'C:\tools\audio2ay\ayumi'
$audio2ay = 'C:\tools\audio2ay\bin\audio2ay.exe'
```

Replace these example paths with your installations. An extensionless Linux
Pasmo executable on Windows is run through WSL. Alternatively use a native
Pasmo executable. Every command accepts `--pasmo PATH` instead of `PASMO`.
Optimization and `--spectra` require Ayumi source and GCC (`--gcc PATH` if necessary).
Ayumi emulates the sound chip for offline rendering; see
[how Ayumi is used here](./speaking-with-the-ts2068.md#ayumi-the-software-sound-chip).
Only the Audio2AY comparison requires the upstream Audio2AY executable.

## Digitized audio: audio2aydac

Generate all three digitized formats with callable code at `$9000`:

```powershell
python audio2aydac.py 'voice.wav' 'laser.wav' --codecs ay4-5k ay4-6k dpcm3-6k --format bin --origin 0x9000 --out build/digitized
```

Generate a tape demo and a cartridge demo for one codec:

```powershell
python audio2aydac.py 'voice.wav' --codecs dpcm3-6k --format tap dck --out build/dpcm-demo
```

AY4 stores two 4-bit samples per byte. DPCM3 stores eight 3-bit deltas in
three bytes. The sample rates are fixed by the codec name; there is no
arbitrary rate switch. These players block until playback finishes.

## Harmonic synthesis: speech2ay

Choose one, two or three AY channels:

```powershell
python speech2ay.py 'voice.wav' --channels 1 --format tap --out build/voice-one-channel
python speech2ay.py 'laser.wav' --channels 2 --format dck --out build/laser-two-channel
python speech2ay.py samples --channels 3 --format bin --origin 0x9000 --out build/harmonic-library
```

Separate executable code from replaceable audio data:

```powershell
python speech2ay.py 'voice.wav' 'laser.wav' --channels 3 --format bin --origin 0x9000 --separate-data --data-origin 0xd000 --out build/separate
```

Load `module.bin` at the manifest's code origin and `data.bin` at `$D000`.
Use the entry's offset and count in `manifest.json` to select a clip. Read
`api.inc` for routine addresses. Your application loads replacement files,
stops playback before replacing active data, and calls `ay_tick` once per
display interrupt. Separate-data mode supports binary output only; it does
not create a runtime tape-file loader. See [calling examples](integration.md).

## Parameter optimization: ayfit

See [how the optimizer searches](./speaking-with-the-ts2068.md#how-the-optimizer-searches)
for candidate ranges, scoring, acceptance checks, limitations and future improvements.

```powershell
python ayfit.py 'voice.wav' --channels 3 --ayumi $ayumi --passes 3 --objective joint --format tap dck --out build/voice-fit
python ayfit.py 'laser.wav' --channels 2 --ayumi $ayumi --passes 2 --objective spectrum --low 80 --high 6500 --format bin --separate-data --data-origin 0xd000 --out build/laser-fit
```

`--search-mode auto` (default) uses conservative search with the filtered
profile and free search with the Berzerk effect profile. Conservative mode
preserves voice routing, avoids new envelopes, limits tone-period changes to
±6% of the baseline, and rejects any worsening clip-average score component.
Use `free` explicitly to explore the wider search:

```powershell
python ayfit.py 'Humanoid.wav' --channels 3 --ayumi $ayumi --search-mode conservative --high 6500 --format dck --out build/humanoid-conservative
python ayfit.py 'Humanoid.wav' --channels 3 --ayumi $ayumi --search-mode free --high 6500 --format dck --out build/humanoid-free
```

The same WAV and cutoffs make these a controlled comparison. The mode is
recorded in optimizer metadata and included in the conversion cache key.

`--passes` accepts 1–4, default 3. More passes cost conversion time, without
changing playback CPU cost. `joint` uses waveform and spectral criteria;
`spectrum` emphasizes spectral matching. Acceptance checks can retain the
baseline where a candidate fails the full-clip criteria. Listen to the result;
an optimizer score does not establish better intelligibility.

All tools accept `--low` (default 80 Hz) and `--high` (6500 Hz, or 7000 Hz
for `ayfit`). The optimizer also accepts `--feedback-cutoff` (11702.57 Hz)
and `--feedback-gain` (7.8), which describe the modeled output filter, not
playback volume choices. Start with defaults unless comparing a measured
machine/filter model. Rebuild in a fresh output directory if changing external
Ayumi or Audio2AY installations, to avoid reusing cached conversion results.

## TS2068 Audio Lab: multi-codec demo (aydemo)

### Reproducing the Berzerk effect sound

The default `filtered` profile uses filtered audio for analysis. The
`berzerk` profile reproduces the original game's effect pipeline: unfiltered
input, the original band estimator clock 1774400 Hz, two search passes,
spectrum candidate search and joint full-clip acceptance by default. The
actual AY renderer/playback clock remains 1764750 Hz. It preserves the legacy
estimator constant deliberately for reproducibility, not as a hardware claim.
The source is not prefiltered in this profile; `--low/--high` apply to optimizer
scoring bands. Default scoring range is 80–7000 Hz. Explicit passes/objective
options override their defaults. This profile is not a guarantee for every clip.

```powershell
python speech2ay.py 'Laser.wav' --channels 3 --profile berzerk --format dck --out build/laser-harmonic
python ayfit.py 'Laser.wav' --channels 3 --profile berzerk --ayumi $ayumi --format dck --out build/laser-optimized
python aydemo.py samples --sample-profile Laser=berzerk --optimize 1 2 3 --ayumi $ayumi --audio2ay $audio2ay --out build/lab
```

The last command changes only Laser's AY synthesis profile; its DAC and
Audio2AY modes keep their existing conversion. The name matches the WAV stem.
The restored three-channel optimizer output was checked byte-for-byte against
the game's saved 31.wav stream (602 bytes), rather than judged by score alone.

### Original versus achieved spectra

```powershell
python aydemo.py samples --spectra --sample-profile Laser=berzerk --optimize 1 2 3 --ayumi $ayumi --audio2ay $audio2ay --out build/lab-fft
```

Press **S** to switch between codec list and spectra. O/P selects the sample,
Q/A selects the codec, and Space plays in either view. The upper plot is the
original recording and the lower plot is modeled output. Both show 32 logarithmic
frequency bands from 80 Hz to 7 kHz, using a shared 48 dB display range. Each signal
is DC-removed and independently RMS-normalized: these are spectral-shape
comparisons, not loudness measurements. They average the whole clip, so they
cannot show transient timing or distinguish every audible difference.

Python computes 2048-point FFTs with approximately 46 ms Hann windows and 50%
overlap, then averages power density in each band. Original audio uses its
native sample rate (no invented spectrum above Nyquist). Achieved AY audio is
rendered by Ayumi at 44100 Hz; DAC audio uses the decoded nonlinear AY levels
with sample-and-hold reconstruction. Both include the approximate feedback
shelf described in the article. Neither includes a measured speaker response.
This is modeled achieved output, not microphone feedback from the machine.

Only 64 one-byte heights per sample/codec pair are stored. No FFT runs on the
TS2068, and no additional work is inserted into playback or its interrupt.
Plots redraw on selection/view changes. The full 40-choice display adds about
3.5 KB of payload and less than 1 KB of resident code. `spectrum-N.png/.scr` are
build previews; FFT powers and assumptions are recorded in `manifest.json`.
Read validation.md: numerical FFT checks pass, but the new spectrum screen's
Fuse verification was declined and is not yet established.

To add plots to an existing build without re-encoding audio:

```powershell
python examples/add_spectra.py --base build/comparison-v4 --samples build/wargames-samples --ayumi $ayumi --pasmo $env:PASMO --out build/comparison-v5
```

The helper checks each original WAV hash against the cartridge manifest.
To update just a subset of codecs, generate a replacement comparison with
those same WAV names, then use `examples/update_comparison.py --base OLD
--replacement NEW --out UPDATED --pasmo PATH`. It preserves other entries
byte-for-byte and rejects source WAV mismatches. To change a whole sample,
add `--replace-sample Laser`; the replacement must contain every existing
codec for that sample, all encoded from the same new WAV. Include `--spectra`
when generating the replacement to refresh its spectrum displays too.

Six standard choices per sample (three digitized and three harmonic):

```powershell
python aydemo.py samples --format dck --out build/comparison
```

Ten choices per sample, adding all optimized channel counts and Audio2AY:

```powershell
python aydemo.py samples --optimize 1 2 3 --ayumi $ayumi --audio2ay $audio2ay --format dck --out build/comparison-all
```

Limit the comparison if a collection exceeds capacity:

```powershell
python aydemo.py 'voice.wav' --codecs ay4-6k harmonic3 --optimize 3 --ayumi $ayumi --audio2ay $audio2ay --out build/short-comparison
```

The DCK comparison is one 64K ROM image, with 8K reserved for resident code
and 56K for audio and menu records. Each decoded record must fit the 11,776-byte
native RAM staging area. Oversized collections fail explicitly. The on-screen
`ROM bytes` counts are stored audio payload sizes after lossless compression,
excluding shared code, menus and record descriptors. The manifest distinguishes
`bytes` (playback stream) from `stored_bytes` (cartridge storage). Decompression
happens before playback and does not alter codec quality or sample timing.
O/P selects samples, Q/A selects codecs, and Space plays.
Release the key before the next action. Codec pages change automatically.
The original small font is retained, with 16-pixel row spacing. A moving sine
wave indicates playback activity; it is not an oscilloscope.

Outputs are `comparison.dck` for an emulator and `picorom.bin` for physical
ROM programming. The latter is exactly 65,536 bytes, without a DCK header.
`player.asm`, symbols, manifest and menu preview PNGs accompany the image.
The memory layout is documented in [integration](integration.md).

For a tape collection:

```powershell
python aydemo.py samples --format tap --out build/tape-comparison
```

TAP uses the smaller demo layout and splits large collections into volumes;
Q/A selects a sample/codec combination and Space plays. The expanded sample
selector and scrolling animation belong to the 64K DCK comparison. Individual
converter DCK demos also use the smaller layout. Multiple requested formats
are placed in separate output directories; consult `index.json` for legacy
volumes. The DCK-only comparison uses its `manifest.json` instead.

## Reproduce the four-sample comparison

Prepare Intruder Alert (18.wav, 100 ms silence, 08.wav), Humanoid (15.wav),
player laser (30.wav), and the supplied Wargames clip. Explicit input order makes
Laser sample 3 and Shall we play a game sample 4:

```powershell
python examples/prepare_samples.py --samples 'C:\audio\berzerk-samples' --wargames 'C:\audio\war_games_play_a_game.wav' --out build/wargames-samples
python aydemo.py 'build/wargames-samples/Intruder Alert.wav' 'build/wargames-samples/Humanoid.wav' 'build/wargames-samples/Laser.wav' 'build/wargames-samples/Shall we play a game.wav' --sample-profile Laser=berzerk --spectra --optimize 1 2 3 --ayumi $ayumi --audio2ay $audio2ay --format dck --out build/comparison-v5
```

This produces 40 choices, including all ten codecs for the full Wargames clip.
Read `manifest.json` for the build's actual ROM use. Original recordings are not
bundled with the reusable tools. The helper requires NumPy and the same PCM
WAV input constraints as the converters.

Use `python TOOL.py --help` for the complete argument list. For CPU costs,
compression and listening compromises, read [Speaking with the TS2068](speaking-with-the-ts2068.md).

One- and two-channel harmonic/optimized entries in the comparison demo show
compact-stream byte estimates with an asterisk; unstarred counts are actual
stored payload bytes. The common playback format is unchanged. See the
[storage explanation](./speaking-with-the-ts2068.md#smaller-one--and-two-channel-streams)
for the calculation and actual-versus-estimated counts.
