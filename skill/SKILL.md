---
name: ts2068-audio-development
description: Convert speech and sound effects for TS2068 AY DAC or harmonic playback, build TAP/DCK/PicoROM demos and callable Z80 libraries, and integrate or extend timed audio routines. Use for TS2068 audio development; not generic audio editing or arcade game-logic changes.
---

# TS2068 Audio Lab development

Use the self-contained toolkit in `assets/audio-tools/`. Read its
[README](assets/audio-tools/README.md) for the four commands and dependencies.
Read [integration](assets/audio-tools/docs/integration.md) before changing
assembly, memory placement, stream formats or interrupt scheduling. Read the
[article](assets/audio-tools/docs/speaking-with-the-ts2068.md) for codec choices,
CPU accounting and quality tradeoffs, and [validation](assets/audio-tools/docs/validation.md)
before claiming hardware or timing support.

## Choose the workflow

- `audio2aydac.py`: AY4/5k, AY4/6k or DPCM3/6k from PCM WAV input.
- `speech2ay.py`: one, two or three-channel harmonic synthesis for speech/effects.
- `ayfit.py`: optional stateful Ayumi search; preserve the baseline unless
  full-clip acceptance gates pass. Numerical improvements are not listening approval.
- `aydemo.py`: selectable sample/codec combinations, TAP or DCK/PicoROM,
  optional upstream Audio2AY comparison and optimized 1/2/3-channel results.
  DCK builds one 64K comparison; TAP uses smaller numbered volumes. Read the
  [command-line guide](assets/audio-tools/docs/command-line-guide.md) for examples.

The `berzerk` AY profile reproduces the game's effect pipeline: raw source,
legacy1774400Hz band estimator, calibrated1764750Hz renderer, spectrum search
and joint acceptance, two passes by default. Keep this separate from the
`filtered` profile. `--sample-profile Laser=berzerk` applies it to one sample's
harmonic/optimized entries. Do not silently add filtering or equate candidate
search with final acceptance: those changes caused an audible laser regression.
The saved three-channel31.wav result is a602-byte exact regression reference.

`aydemo --spectra` computes whole-clip FFT comparisons offline and stores64
heights per selection. The S-key view displays original and modeled output,
RMS matched, with shared48dB/80–7000Hz axes. It is not a measured speaker
response or a live FFT. Keep FFT work out of timed playback. Read the validation
record before claiming screen support: the first Fuse screen check was declined.

Set Pasmo explicitly or via PASMO. Ayfit additionally needs GCC and an external
Ayumi directory. Never assume the original Berzerk workspace or WAV collection
exists. The toolkit has no imports from that project. Do not copy ROMs or
recordings into a distributable skill without an appropriate reason/authorization.

## Invariants

- CPU3.528MHz; AY1.764750MHz; display60.1145Hz. A60Hz ISR cannot independently
  supply6k DAC samples while returning most of the frame to unrestricted code.
- DAC playback is blocking. Advertise padding as replaceable **instruction
  budget**, not automatically available foreground CPU time. Validate every
  inter-sample gap, including group and frame boundaries.
- Screen RAM and ULA ports can contend. The expanded demo's scrolling writes
  are gated to the first7168T of its synchronized frame; its340T per-sample
  slot and short synchronization ISR must be preserved and reverified.
- R13=255 skips an envelope write. AY generators retain state across frames;
  shared noise/envelope and output filter state belong in optimizer snapshots.
- Call the AY player once per display interrupt, not twice per game tick.
  Preserve AF/BC/DE/HL in the ISR and serialize start/stop/data replacement.
  Keep the final frame sounding for its full interval.
- Small demo ROM is contiguous at8000–BFFF. The expanded comparison uses all
  eight ROM chunks, resident code at8000–9FFF and baseline HSR10. Bank loads
  stage through native RAM; while DOCK hides the stack, no stack access,
  interrupt or call is allowed. See the integration memory map before editing.
  Native HOME RAM holds state/stack.
  Version3 audio storage may be losslessly compressed: copy the stored record
  to native A800–BFFF before expanding at D000–FDFF, with HSR10 restored.
  Preserve the6144-byte compressed and11776-byte expanded bounds. Onscreen
  ROM bytes differ from playback-stream bytes; keep both in the manifest.
  Never mark ROM-backed PicoROM storage as writable DCK RAM. Physical output
  is64K with bytes at physical address offsets; DCK headers are not ROM bytes.
- The module and demo have different symbols. Use each artifact's own manifest.
  Separate data is relocatable; executable code is rebuilt at its load origin.
- Public routines currently own the AY sound registers and restore standard
  video mode on stop; adapt explicitly for ECM or concurrent channel mixing.

Use `tests/verify_exports.py`, `verify_runtime.py`, `verify_ay.py`, and
`verify_demo_boot.py` for changes touching their contracts. Use
`verify_comparison.py` and `verify_comparison_playback.py` for banked
storage, decompression, menu and full playback changes. Keep debugger
command strings free of a trailing newline. Match the tests to the change;
report emulator versus physical/audio verification honestly. Source assembly
is generated by `tsaudio/assembly.py`; regenerate `asm/audio_runtime.asm`
when changing that generator. Do not hand-patch binaries.

Keep changes to the canonical skill's toolkit and its article together.
This skill does not authorize changing any game's source-of-truth behavior.
