# AY Sound Workshop

The general-purpose browser player and parameter editor lives in
`web/ay-editor/`. It was developed for Sinistar's roar and effects, then adapted
for speech2ay with a selected gunshot example, synthetic starter sounds and register-data import. It does not
require the game, its recordings, a cartridge, system ROMs or a running emulator.

Run `python -m http.server 8000 --directory web` from speech2ay, then open
`http://localhost:8000/ay-editor/`. Use HTTP/localhost or HTTPS so module workers
and Web Audio are available. Click Play to activate audio. Node 22+ can run the
renderer/format checks with `npm run test:ay-editor`.

## Load, edit and audition

The default starting sound is the accepted 30-frame (0.499-second) Sinistar
gunshot noise fit, opened on Noise period with looping off. Existing autosave
can restore another session; select the gunshot or use `?preset=real-gunshot-full`
when switching to it. Tone, sweep, noise decay and envelope examples remain
available, or choose **Import registers**. Imports accept a JSON array of register rows, an object with `rows`,
or raw binary frames: exactly fourteen bytes R0 through R13 per frame. The limit
is 1-3,600 frames. There is no header, compression or sample-rate metadata. Use
only decompressed harmonic/register output at the timing below; DAC data,
compressed cartridge streams, WAV input and ZXAYEMUL `.ay` programs are different
formats. This editor modifies parameters; it does not perform the WAV-to-AY fit.

Draw a curve, drag a straight line, set/smooth/restore a selected range, or enter
numeric values. Select a time interval for looped audition; Play once disables
looping. Compare against **Hear starting version**. Undo/redo records edit gestures;
Reset restores the starting sound. Editing during playback rerenders in a worker
and crossfades the replacement at the current playback position. Stale worker
responses cannot replace newer edits. Automatic audition can be disabled.

Controls include relative tone pitch (50-150%), individual A/B/C tone frequencies,
fixed volumes 0-15 or envelope volume 16, shared noise period, per-channel tone/noise
routing, and shared envelope period/shape. Pitch changes tone dividers only.
Disabling both tone and noise produces a constant level, not a mute; use volume 0.
R13=255 (shown as shape -1) means skip the envelope write; shapes 0-15 restart it
on every frame where they are written. Preserve that distinction when drawing.

## Save and export

Save project writes versioned JSON with current/base rows, pitch curves, selection
and selected track. Load project accepts this schema, including Sinistar v1 project
files. Browser autosave is convenience storage for the last session; download JSON
for a durable editable copy. Opening a new starter/import replaces that session.

Export WAV writes the whole edited sample as mono 44.1 kHz, 16-bit PCM, using a
fixed output scale. Monitor gain affects listening only, without per-edit WAV
normalization. Export AY registers writes `ay-sound-edited.registers.bin`: raw
14-byte compiled frames with pitch edits applied and the R13 skip sentinel intact.
Loop selection does not trim exports. Cartridge packing and player compatibility
must be checked separately; a reduced channel/noise format cannot automatically
represent arbitrary routing or envelopes. Exports do not modify any cartridge.

## Timing, model and implementation

The inherited TS2068 preset uses CPU 3,528,000 T/s and 58,688 T per update
(about 60.1145 Hz). The local TSRun AY core models a 1.764 MHz AY clock, integrated
44.1 kHz sampling and an amplifier RC filter; the mixed output adds a 20 Hz DC
blocker. It preserves oscillator/noise/envelope state between parameter frames.
This differs from the toolkit's 1.764750 MHz Ayumi optimizer model: browser output
is an audition model, not byte-exact Ayumi audio or measured physical sound.
Timing/clock selection is fixed in this version, not inferred from imported data.

`editor.mjs` owns interaction, undo and playback; `formats.mjs` validates imports
and projects; `synth.mjs` compiles pitch, renders and exports WAV; `worker.mjs`
isolates rendering; `ay-core.mjs` is an unchanged TSRun `ay.js` snapshot. Its SHA-256
is in `provenance.json`. See `web/THIRD-PARTY.md` for attribution. The default gunshot retains the accepted Sinistar register rows; the other
starter parameters are synthetic examples. The fit adapts RemingtonGunshot.wav
by fastson ([source](https://freesound.org/people/fastson/sounds/50618/),
[CC BY 3.0](https://creativecommons.org/licenses/by/3.0/)), cropped and level
adjusted before noise/volume fitting. No source PCM is bundled.

Checks cover exact unedited exports, raw/JSON/project roundtrips, invalid inputs,
one-frame duration, finite samples, WAV structure, pitch, level, silence, noise,
envelope progression and R13 skip behavior. Browser interaction and subjective
listening are separate checks; modeled tests do not establish hardware fidelity.
