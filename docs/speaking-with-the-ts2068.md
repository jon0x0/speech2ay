# Speaking with the TS2068

The TS2068 can reproduce recorded speech through its 1-bit beeper output or
through its AY chip. With the AY, we can drive a volume register thousands of
times a second to approximate the original waveform, or describe an evolving
combination of tones and noise and let the chip generate it. Digitized playback
usually preserves more of the recording's identity. AY synthesis leaves far
more time for a game and can substantially reduce storage requirements.

## The 1-bit beeper: speech without an AY

Digitized speech does not require a multi-level DAC or an AY chip. A program can
switch the beeper between its two output levels with carefully controlled
timing. This is the approach used by Tad Painter's speech software and other
beeper speech players. Painter's TS2068 package plays prerecorded vocabulary
under program control; it is not a general text-to-speech engine. See the
preserved [Speech Synthesizer package](https://timexsinclair.com/computer_media/speech-synthesizer/index.html)
and [Tad Painter's documentation](https://www.timexsinclair.com/document/speech-synthesizers-for-timex-computers/index.html).

The same general technique works on the ZX Spectrum, including the 16K/48K
machines without an AY. That does not make a TS2068 executable directly
portable: CPU clock, display contention, memory layout and output-port handling
must match the target machine. On an AY-equipped machine, beeper playback also
leaves the AY channels available, although the CPU still has to service the
beeper on time.

One-bit output has only two instantaneous levels. A simple sign-quantized
recording loses amplitude detail; pulse-width or pulse-density methods can
represent intermediate average levels through the timing of those transitions.
These are different encoding choices, with different bandwidth, noise and
storage tradeoffs—not a claim about Painter's exact stored format. Recognizable
speech is possible, but harshness, hiss and loss of quiet detail can be more
pronounced than with well-encoded AY4 audio. Encoding and the output circuit
matter as much as the nominal bit depth.

Unlike AY tone synthesis, a beeper has no autonomous generator to continue the
recording between coarse updates. Playback needs a tightly timed CPU routine;
a blocking implementation occupies the CPU for the clip, and concurrent work
must fit its timing budget. There is no single CPU percentage for all beeper
players. The same scheduling restriction applies to our blocking AY DAC loops,
although AY4 offers 16 nonlinear output levels instead of two.

For a fixed-rate packed bitstream, storage is sample rate divided by eight:
6,000 bits per second takes 750 bytes per second before metadata. That is four
times smaller than AY4 at the same update rate, but it does not offer equivalent
quality; higher-rate pulse modulation may erase that saving. Transition-time
and compressed formats have different costs. The tools in this repository
currently generate AY DAC and AY synthesis data, not a beeper stream or player.

## AY digitized audio: faithful shape, demanding schedule

`audio2aydac` removes DC, filters, resamples and quantizes against the AY's
nonlinear 16-level output table. A volume code is not a linear four-bit sample.
Nearest-level quantization avoids the rasp heard in earlier error-feedback
experiments. Quiet input remains quiet; clips are not automatically trimmed.

AY4 at 5 kHz keeps about 2.1 kHz of useful filtered bandwidth and costs
2,500 bytes per second. At 6 kHz the cutoff can reach about 2.58 kHz, which
may help consonants but costs 3,000 bytes per second. Neither retains the
full bandwidth of the original recording. DPCM3 stores changes in AY level,
using 2,250 bytes per second at 6 kHz. It saves another quarter over AY4/6k,
but rapid changes can exceed its small downward steps, causing slope overload
and extra distortion. It is a different compromise, not a free quality win.

A T-state (T) is one CPU clock cycle; this article uses T-states to measure playback work and the time available between audio updates on the 3.528 MHz TS2068.

| Mode | Payload bytes/s | Nominal sample spacing | Decode/output work* | Available instruction budget* |
|---|---:|---|---:|---:|
| AY4 5 kHz | 2,500 | 705, 706, 705, 706, 706 T | 9.16% | 90.84% |
| AY4 6 kHz | 3,000 | 588 T | 13.44% | 86.56% |
| DPCM3 6 kHz | 2,250 | 588 T | 24.53% | 75.47% |

*These percentages describe replaceable instruction budget, **not free time
automatically returned to your program**. The supplied blocking DAC routines
use all elapsed CPU time: useful work plus calibrated padding, with interrupts
disabled. They return only at the end of a clip. You can replace padding with
equal-cycle bounded work; you cannot call an arbitrary game loop there.
Setup, final stop, contention and animation are excluded from the percentages.

The arithmetic uses the actual 3.528 MHz TS2068 CPU: 3,528,000/5,000=705.6 T
and 3,528,000/6,000=588 T. AY4/5k needs an average 64.6 T for decode, data OUT
and group bookkeeping; AY4/6k needs 79 T; DPCM3 needs 144.25 T. The remaining
time is deterministic padding that can be replaced with carefully timed work.

The demos demonstrate that useful processing time remains during audio
playback: all the supplied implementations animate the screen while speaking.
With digitized audio, that opportunity comes with a strict schedule. Every
sample must reach the output at its prescribed time; jitter and overruns can
cause choppiness, distortion and other audible artifacts. A carefully crafted
cooperative system could divide animation, input handling and game mechanics
into small, bounded pieces that fit between sample writes. Every execution path
must respect the deadline, including memory contention and task-switching work.
The demonstrations implement scheduled animation; they do not yet provide a
general cooperative game scheduler.

The smaller TAP/individual-converter demo spends 133 T per group on phase tracking and a blanking-period screen
flip: about 1.88%, 11.31% and 2.83% of the total CPU respectively for these
three group sizes. It animates a prepared wave without stretching sample
intervals. It illustrates how useful work can share the digitized playback
schedule. Direct screen and ULA-port writes outside blanking caused measurable
timing errors in testing and were replaced.

The expanded 64K comparison instead scrolls a prepared sine wave in two-pixel
phase steps. Its DAC implementation reserves 340 T **per sample** for a balanced
phase-tracking and eight-byte screen-copy slot: 48.19% of the 5 kHz sample interval
or 57.82% of the 6 kHz interval. This is scheduled work inside the blocking loop,
not CPU returned to the caller. Copies are restricted to the first 7168 T of
the synchronized frame to avoid display contention. Preparation and remaining
padding still consume the rest of the loop. The AY version copies 128 screen
bytes per interrupt; the eight LDIR copies alone add 2648 T (4.51% of a frame),
plus address/control overhead, to the audio-only budget below. Thus the
roughly 97% available figure describes the reference player without animation.

## Harmonic synthesis: the AY performs the ongoing work

`speech2ay` estimates pitch and fits square-wave harmonic templates to the
recording's spectrum. A band/noise model handles less periodic portions. One
channel has very little ability to separate pitch from speech formants; two
or three give more freedom. Sound effects can also work well when their
important features resemble tones, harmonics or noise. Complex transients
and natural voices can become buzzy, robotic or less intelligible. Listening
to the actual samples matters more than assuming a codec ranking.

The player receives one register frame per 60.1145 Hz display interrupt.
Between updates the AY runs by itself. The current straightforward reference
writer takes approximately 1,575 T per frame with no R13 write, or 1,641 T
with a shape event. Including IM2 entry, register saves/restores and the CALL
is about 1,713–1,779 T: **2.92–3.03% of a 58,688 T frame**, leaving about
97% for other work. This excludes the demo's animation and any application
interrupt overhead. It is a static instruction count; actual contention and
missed interrupts depend on the application. The final stop has its own cost.

This approximately 60 Hz interrupt-driven player can interrupt foreground game
mechanics or animation, update speech or sound effects, then resume the
interrupted work. Foreground processing need not be divided into sample-sized
slots. Audio quality is maintained provided the register updates arrive on time:
keep interrupt-disabled sections short, and leave enough time for every other
task sharing the display interrupt to finish before the next deadline. Servicing
audio first gives it a predictable place in the interrupt routine. The AY keeps
generating sound between updates, so the timing requirement is much less
demanding than the 5–6 kHz schedule of digitized playback, though missed or late
updates can still affect the result.

This package keeps the same 14-byte frame format for one, two and three
channels, so reducing channels does not reduce raw stream size or register-write
overhead. Unused channels are explicitly muted. An application can implement
a smaller stream/writer if that tradeoff is useful. AY noise and envelope
generators are shared; treating them as three independent synthesizers is wrong.

## Another possibility: hardware-timed interrupts

A custom cartridge or another hardware expansion could provide a periodic
timer connected to the Z80's `/INT` input. A sample-rate interrupt handler could
then output digitized audio while foreground tasks run between interrupts,
rather than requiring a cooperative sample loop. This is a possible future
design, not a feature of the current cartridges or players.

A periodic interrupt request does not by itself guarantee jitter-free output.
The Z80 must finish the current instruction before accepting an enabled
maskable interrupt, and `DI` delays servicing it. Interrupt entry, register
preservation and return also consume part of every sample interval. The design
would need bounded response latency, a short audio handler, and coordination
with the existing display interrupt, including safe electrical sharing and
identification/acknowledgement of each interrupt source. See the
[Zilog Z80 CPU User Manual](https://www.zilog.com/docs/z80/um0080.pdf) for the
interrupt behavior. A hardware sample latch or FIFO driven directly by a timer
could further separate exact output timing from the CPU's response time.

## How much compression?

At 14 bytes/frame, the AY stream is about **841.6 bytes/second** (6.73 kbit/s).
This is lossy synthesis rather than lossless sample compression. Ratios need
an explicit reference format:

| Reference, mono | Reference bytes/s | Ratio to current AY stream |
|---|---:|---:|
| 16-bit PCM, 44.1 kHz | 88,200 | 104.80:1 |
| 16-bit PCM, 6 kHz | 12,000 | 14.26:1 |
| 16-bit PCM, 5 kHz | 10,000 | 11.88:1 |
| Packed AY4, 6 kHz | 3,000 | 3.56:1 |
| Packed AY4, 5 kHz | 2,500 | 2.97:1 |
| Packed DPCM3, 6 kHz | 2,250 | 2.67:1 |

AY4 itself compresses 16-bit PCM at the same rate 4:1; DPCM3 gives 5.33:1.
These steady-state ratios exclude player code, clip metadata, frame rounding,
group padding, screenshots and ROM padding. For short clips those fixed costs
can dominate. Reducing the source sampling rate is not lossless compression.

The version 3 comparison cartridge additionally compresses audio streams
losslessly using literals and LZ backreferences. It expands them into native
RAM before playback, so the sample values, register frames and playback CPU
costs are unchanged. Actual savings depend on the clip and codec; muted AY
registers and repeating frames often compress well. Unstarred onscreen `ROM bytes` reports
this stored size; starred counts estimate a compact channel-specific format
(see below). The manifest also reports the expanded stream size.
The rates and ratios above describe the expanded codec format. This extra
storage layer applies to the comparison cartridge, not standalone BIN/TAP
exports. It adds preparation time when selecting playback, not per-frame work.


<a id="smaller-one--and-two-channel-streams"></a>

### Smaller one- and two-channel streams

In TS2068 Audio Lab, an asterisk after a byte count marks a **compact-stream
estimate**, rather than the bytes occupied by that clip in this cartridge.
The reference player uses 14-byte frames for every channel count. A dedicated
format could omit unused channels: two tone-period bytes and one volume byte
per active channel, plus five shared noise, mixer and envelope bytes. That is
**8 bytes/frame for one channel** or **11 for two**, versus 14 for three:
42.9% and 21.4% less raw data respectively, with identical audible settings.

The starred figures are calculated from the actual clips by removing those
unused registers and applying the same lossless LZ storage rules as the demo.
Compression savings vary with the data; already-muted registers compress well,
so the stored reduction need not match the raw reduction. These estimates
require an adapted loader that restores omitted channels to muted defaults,
or a player that reads the compact format. They exclude shared code and
metadata, just like the actual payload counts. Current BIN/TAP exports and
the cartridge still use the common format. The manifest retains actual
`stored_bytes` separately from `compact_estimate`.

| Sample | Codec | Actual cartridge bytes | Compact estimate* |
|---|---|---:|---:|
| Intruder Alert | harmonic1 | 363 | 193* |
| Intruder Alert | optimized1 | 380 | 219* |
| Intruder Alert | harmonic2 | 432 | 333* |
| Intruder Alert | optimized2 | 461 | 369* |
| Humanoid | harmonic1 | 255 | 158* |
| Humanoid | optimized1 | 283 | 172* |
| Humanoid | harmonic2 | 294 | 256* |
| Humanoid | optimized2 | 438 | 379* |
| Laser | harmonic1 | 494 | 281* |
| Laser | optimized1 | 511 | 337* |
| Laser | harmonic2 | 574 | 462* |
| Laser | optimized2 | 648 | 543* |
| Shall we play a game | harmonic1 | 897 | 568* |
| Shall we play a game | optimized1 | 940 | 614* |
| Shall we play a game | harmonic2 | 1094 | 988* |
| Shall we play a game | optimized2 | 1115 | 1001* |

## Searching for a better fit

`ayfit` starts with the harmonic result, then searches tone periods, volume,
noise, mixer and envelope settings. Every candidate starts from the same
saved AY/filter state; the chosen state continues into the next frame.
After local search, full-clip rescoring accepts whole-clip, four-frame and
single-frame proposals only when the objective improves. Joint mode also
requires neither average waveform nor average spectrum score to worsen.

The joint objective includes spectral/RMS error, bounded phase-aligned
waveform correlation (about ±5 ms), periodicity and roughness. It does not
promise absolute sample-phase identity. `--passes` controls search effort;
`--low` and `--high` control source filtering and objective bands. Defaults
use 80 Hz as the lower cutoff. The baseline harmonic pipeline uses 6.5 kHz
as its upper analysis limit. These are analysis limits, not promised audio
bandwidth. There is no intelligibility model or guarantee of a global optimum.

The output circuit approximation uses a feedback shelf near 11,702.57 Hz
and a DC/high-frequency gain ratio of 7.8. Those come from the previous
R14=680kΩ, C23=20 pF, R15=100kΩ interpretation. `--feedback-cutoff` and
`--feedback-gain` expose those assumptions. It is not a measured complete
speaker/amplifier response and does not model diode or speaker nonlinearities.

## Comparing Audio2AY

The optional `aydemo --audio2ay PATH` mode runs the installed upstream tool
on the same WAV and adds a menu choice. Its peak-picking approach can suit
effects and music; this harmonic fitter explicitly models square-wave odd
harmonics and source pitch. Neither approach is uniformly better. The adapter
disables arpeggio, requests the TS2068 AY clock, and preserves duration when
rescheduling 50 Hz output onto the 60.1145 Hz display interrupt.

Upstream's three-channel packed format is approximately 300 bytes/second
before its header; this adapter expands it into the common 14-byte stream,
so its expanded playback stream takes the same 841.6 bytes/second as harmonic
playback. A direct packed Audio2AY player could retain the smaller storage,
but that is not the player shipped here. Compare equal-volume listening
results, consonant clarity, noise and effects character—not just file size.

## Running TS2068 Audio Lab

The cartridge images let you try the playback methods on a real TS2068 or in
an emulator. Hardware options include an EPROM programmed with an EPROM
programmer and fitted to a compatible TS2068 cartridge board, or a USB-programmable PicoROM-28
fitted to such a board. Other options include a TSPico with cartridge emulation
and the upcoming PicoCartridge2068.

For emulation, use [Fuse](https://fuse-emulator.sourceforge.net/), the
browser-based [TSRun](https://josef-jelinek.github.io/TSRun/), or another emulator
with suitable TS2068 cartridge, memory-paging and AY support. Select the TS2068
machine configuration where applicable; a standard Spectrum configuration is
not sufficient for these cartridge demos.

Use the `.dck` cartridge image with software that accepts that format. For
EPROM programming or USB-programmable PicoROM-28, use the flat `picorom.bin` image and the
appropriate cartridge-board mapping; the DCK header is not part of the ROM
contents. Follow the device's loading instructions for cartridge emulation.
See the [integration guide](./integration.md) for the generated memory layouts.

The current automated tests establish byte values, timing and loadability in
Fuse; listing other platforms here does not mean this build has been tested on
each one. Listening on a real TS2068 remains important when judging audio
quality, because the speaker and output circuitry affect what you hear.
