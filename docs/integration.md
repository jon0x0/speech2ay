# Calling and loading audio

Read the output's `manifest.json`; addresses are not interchangeable between
`module.bin` and `player.bin`. Assemble again to relocate. Public API offsets
from `audio_api` are fixed: init +0, AY4/5k +3, AY4/6k +6, DPCM3/6k +9,
AY start +12, AY tick +15, stop +18. Generated absolute labels are also exported.

## Memory and hardware

CPU: 3,528,000 Hz. AY: 1,764,750 Hz. Display interrupts: approximately
60.1145 Hz; Fuse frame arithmetic uses 58,688 T states. Select register using
`$FFF5`, write using `$FFF6`. This player owns sound registers R0–R13 and
does not write joystick registers R14/15. One/two-channel conversion mutes
unused channels; it is not a concurrent AY channel mixer.

Small cartridge demo: HSR `$30` selects **only** contiguous DOCK4/5 ROM. `$FF=0`
selects HOME/DOCK rather than EXROM and primary display. Screen files occupy
HOME `$4000–$5AFF` and `$6000–$7AFF`; second display is demo animation only.
Native RAM `$C000–$C100` is the 257-byte IM2 table, with JP stub at `$C1C1`
outside it. State is `$C210–$C21F`. Stack starts at `$FF00`. Never select DOCK6
or DOCK7 for writable state. DCK descriptors 1/3 are not a substitute for
physical RAM on PicoROM-28.

### Expanded comparison cartridge

`aydemo` DCK output uses contiguous ROM chunks 0–7 (64K total). Resident code
is in chunk 4, `$8000–$9FFF`; baseline HSR is `$10`. The other seven chunks
provide 56K of audio and compressed UI storage. All DCK chunk descriptors are
ROM-only (`2`), and `picorom.bin` maps bytes directly to physical addresses.

Native HOME RAM holds wave frames at `$A000–$A7FF`, the IM2 table at
`$C000–$C100`, the vector stub at `$C1C1`, audio state at `$C210`, wave pointer
at `$C220` and UI state from `$C230`. SP starts at `$C2FF`. Audio records are
copied to `$D000–$FDFF` before playback (maximum 11,776 bytes per record).
The normal bounce buffer is `$7C00`; source chunk 3 instead uses `$5B00`.

Version 3 uses optional lossless LZ storage for audio records. A compressed
record is first loaded at `$D000`, copied to native `$A800–$BFFF` (maximum 6144
bytes), then expanded back into `$D000–$FDFF`. All banks are restored before
decompression. The original playback stream is preserved exactly. Records
that do not shrink or do not fit the compression scratch buffer remain raw.
The record-compression table and `ui+16` hold the flag; source code documents
literal/backreference tokens. Menu RLE records remain unchanged. Manifest
`stored_bytes` is physical audio storage; `bytes` is the expanded stream size.

The loader disables interrupts, selects a source chunk alongside resident
chunk 4, copies at most 256 bytes to the bounce buffer, then restores HSR10.
Only after restoring HOME does it access the stack or copy into the destination
staging buffer. This matters especially when chunk 6 hides the native stack
and state. The banked interval uses straight-line OUT/LDIR/OUT, without CALL,
PUSH, POP or interrupt access. Each record may cross physical chunk boundaries.

The AY/idle ISR copies a 128-byte sine frame per display interrupt. DAC loops
copy eight bytes at a time within balanced 340 T slots, only during the known
early blanking window. Keep the supplied ISR synchronization and timing checks
when changing this demonstration. These are prepared sine frames, not decoded
audio visualizations. The standalone callable runtime has no such dependency.

With `--spectra`, `ui+17` holds the S-key view selector. Each audio entry has
an additional 64-byte record: 32 original and 32 modeled FFT bar heights 0..31.
A shared RLE lower-screen template follows those records. The selected codec
glyph row is copied to the spectrum header; two-pixel bars are drawn in native
screen RAM while interrupts are disabled during redraw. This occurs only on
selection/view changes. Spectrum state and loading add no per-sample or ISR
work. `spectrum_ui.py` documents the display addresses; `spectrum.py` performs
all FFT/modeling work on the host. Spectrum screens still need the declined
Fuse check; assembly and offline numerical validation are separate evidence.

Callable modules do not initialize IM2, change HSR, or initialize SP. They
reserve the 16 state bytes above. `audio_init`/`audio_stop` restore standard
video mode via port `$FF`; applications using ECM should adapt that line or
restore their mode after stopping. Exact DAC timing assumes code, data and
stack in uncontended address ranges (normally `$8000+`, or ROM below `$4000`).
The builder allows code origins `$6000–$BFFF`, but `$6000–$7FFF` is contended
and is not suitable for cycle-exact DAC or the two-screen demo.

## Digitized playback

```asm
        di                      ; do not interrupt a sample loop
        ld hl,CLIP_ADDRESS      ; manifest data_address + entry offset
        ld de,CLIP_GROUPS       ; entry count, NOT bytes or samples
        call DAC6               ; use generated api.inc
        ei                      ; caller decides whether to re-enable
```

The routine initializes the AY DAC, plays, silences it and returns with
interrupts still disabled. It clobbers AF, BC, DE, HL, IX and IY. A zero count
returns without reading data. `audio_init` and the DAC functions preserve no
general caller state beyond their explicitly supplied parameters. No code is
self-modifying and all mutable state lives in HOME RAM.

AY4 low-nibble-first: AY4/5k groups are 10 samples/5 bytes; AY4/6k groups are
2 samples/byte. Both store actual logarithmic AY volume codes, not linear PCM.
DPCM3 groups are eight 3-bit codes packed LSB-first into three bytes. Start
at AY level 11; each code indexes deltas `[-4,-2,-1,0,1,2,4,8]`, then clamp
to 0..15. Reset the accumulator for each clip. Tail groups are padded; the
manifest reports exact source sample count and padded duration.

The standalone reference routines have no animation. The demo's generated
variant waits for one display interrupt and keeps a 58,688 T software phase.
It changes display file only in the first group after frame wrap, within
blanking, and balances both branches to 133 T. Its ISR must complete in under
about 5,000 T before the initial return; the provided demo does. Do not copy
this synchronization into an arbitrary application's long ISR unchanged.
Unrestricted memory/ULA writes inside DAC padding introduce contention.

## Interrupt AY playback

```asm
        di
        call AUDIO_INIT
        ld hl,CLIP_ADDRESS
        ld de,FRAME_COUNT
        call AY_START
        ei

my_isr:
        push af
        push bc
        push de
        push hl
        call AY_TICK             ; once per DISPLAY interrupt, not game tick
        ; Other bounded interrupt work can go here.
        pop hl
        pop de
        pop bc
        pop af
        ei
        reti
```

`ay_start`: HL=data, DE=frame count; publishes state and active flag under DI.
`ay_tick`: clobbers AF/BC/DE/HL; does not enable interrupts or return with RETI.
Each frame contains exactly 14 bytes R0..R13. **R13=255 means skip the write**,
not write 255: a real shape write restarts the shared envelope. It writes
R0..12 every active update. The last frame remains sounding for one full
interrupt period; the following tick silences the chip and clears active
byte `$C215`. Poll that byte, not remaining-frame count, for completion.
`audio_stop` immediately mutes volumes and clears active/count. Serialize
init/start/stop with the ISR. No nesting or thread safety is provided.

## Reloadable libraries

With `--separate-data`, load `module.bin` at `origin` and `data.bin` at the
manifest's `data_address`. Stop playback under DI before overwriting data.
The default data buffer is `$D000`; the builder accepts `$C300–$FDFF` and
checks the entire payload fits. Reload another generated raw data file there,
then call the appropriate entry with the **new** offset/count. No absolute
pointers are stored in the payload, so its contents are location independent.
The module is origin-dependent. Loading tape/files and keeping metadata are
the host program's responsibility; never load over an actively playing buffer.
