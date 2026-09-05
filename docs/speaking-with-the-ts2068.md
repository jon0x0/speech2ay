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
may help consonants. This means **6,000 4-bit volume samples per second**,
packed two per byte, for **3,000 bytes per second**. At 3 kHz, the equivalent
packed rate would be 1,500 bytes per second. Neither retains the
full bandwidth of the original recording. DPCM3 stores changes in AY level,
using 2,250 bytes per second at 6 kHz. It saves another quarter over AY4/6k,
but rapid changes can exceed its small downward steps, causing slope overload
and extra distortion. It is a different compromise, not a free quality win.

A T-state (T) is one CPU clock cycle; this article uses T-states to measure playback work and the time available between audio updates on the 3.528 MHz TS2068.

| Mode | Payload bytes/s | Nominal sample spacing | Decode/output work* | Available instruction budget* |
|---|---:|---|---:|---:|
| AY4 5 kHz | 2,500 | 705.6 T average | 9.16% | 90.84% |
| AY4 6 kHz | 3,000 | 588 T | 13.44% | 86.56% |
| DPCM3 6 kHz | 2,250 | 588 T | 24.53% | 75.47% |

*These percentages describe instruction slots where calibrated padding could
be replaced with useful work. The supplied blocking DAC routines still occupy
the CPU for the entire clip, with interrupts disabled, and return only when
playback finishes. You can replace padding with
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
| Intruder Alert | optimized1 | 363 | 193* |
| Intruder Alert | harmonic2 | 432 | 333* |
| Intruder Alert | optimized2 | 432 | 333* |
| Humanoid | harmonic1 | 255 | 158* |
| Humanoid | optimized1 | 262 | 166* |
| Humanoid | harmonic2 | 294 | 256* |
| Humanoid | optimized2 | 303 | 262* |
| Laser | harmonic1 | 494 | 281* |
| Laser | optimized1 | 511 | 337* |
| Laser | harmonic2 | 574 | 462* |
| Laser | optimized2 | 648 | 543* |
| Shall we play a game | harmonic1 | 897 | 568* |
| Shall we play a game | optimized1 | 915 | 587* |
| Shall we play a game | harmonic2 | 1094 | 988* |
| Shall we play a game | optimized2 | 1098 | 994* |

## Searching for a better fit

<a id="ayumi-the-software-sound-chip"></a>

### Ayumi: the software sound chip

[Ayumi](https://github.com/true-grue/ayumi) is an open-source C library that
emulates the AY-3-8910 and YM2149 sound chips. Given tone periods, volumes,
noise, mixer and envelope settings, it generates the audio samples those
settings would produce. Here it acts as a software sound chip on the computer
running the conversion tools.

`ayfit` uses Ayumi to hear each proposed set of AY register values. Our small
C helper renders the candidates in AY mode at 44,100 samples/second, using the
configured chip clock and a mono mix. Python then compares the rendered
waveform and spectrum with the source recording. Candidates start from the
same saved chip and output-filter state, and the selected candidate's state
continues into the next frame. This preserves tone phase, noise and envelope
history instead of restarting the chip at every comparison. Ayumi supplies
the sound model; the parameter search and scoring are implemented in `ayfit`.

The optional `aydemo --spectra` feature also uses Ayumi to render the harmonic,
optimized and Audio2AY register streams before calculating their displayed
spectra. The digitized AY4/DPCM3 spectra instead use decoded nonlinear AY
volume levels held for each sample interval. All these calculations happen
offline; the cartridge stores the resulting spectrum bars. Our renderer adds
the approximate TS2068 output-circuit filter described below, so the plots
represent modeled output rather than a recording from a real speaker.

Ayumi is needed for optimization and modeled spectrum generation, but ordinary
`speech2ay` harmonic conversion and `audio2aydac` conversion do not require it.
Pass `--ayumi` the directory containing `ayumi.c` and `ayumi.h`; GCC compiles
the helper with those sources. Ayumi adds no Z80 playback cost or cartridge
storage: the generated program writes the AY registers directly on the TS2068,
and an emulator supplies its own sound-chip emulation when running the demo.

<a id="how-the-optimizer-searches"></a>

### How the optimizer searches

`ayfit` starts with the harmonic converter's register stream as its baseline.
It renders that stream through Ayumi, resamples the source to 44,100 Hz, and
matches the source's overall AC level to the rendered baseline. This makes
the comparison focus on reproduction rather than an arbitrary recording level.
The normal `filtered` profile applies the source filters; the `berzerk` effect
profile uses the unfiltered source.

The search proceeds one 60.1145 Hz frame at a time (about 16.6 ms). For each
frame it starts from the harmonic settings and tries a batch of alternatives,
including, in free mode, the preceding frame's selected settings. Most alternatives change
one setting at a time; envelope trials change several related settings
together. Every alternative is rendered from the same saved chip/filter
state. The lowest-scoring candidate becomes the starting point for the next
pass. After the last pass, its state is committed before moving forward.

`--passes` accepts **1–4** passes per frame, default **3**, or **2** with the
`berzerk` profile. Frames whose baseline volume registers are all zero skip
candidate search. Extra passes increase conversion time, but leave the player
and its update rate unchanged. This is a deterministic local search, not an
exhaustive search or a guarantee of the best possible encoding.

### Choosing the search mode

`--search-mode auto` is the default. It selects **conservative** search for
the normal filtered profile and **free** search for the Berzerk effect profile.
Either mode can also be selected explicitly in `ayfit` or `aydemo`.

Conservative search addresses an audible regression in the Humanoid sample:
the old optimizer introduced envelopes and large tone changes that improved
its scores but sounded worse than the harmonic baseline. The new mode keeps
the baseline's tone/noise routing and envelope settings, never enables a
baseline-muted voice, and searches fixed volumes 0–15 on active voices.
Tone periods stay within **±6% of that frame's original harmonic period**,
bounded to 1–4095. Each pass tries the original period, nearby integer steps
(±1 and ±2), and baseline-relative factors 0.94, 0.98, 1.02 and 1.06.
Anchoring to the original frame prevents successive passes drifting farther
away. Noise periods 1–31 remain available where the baseline already uses noise.

Acceptance is stricter too: **none of the four clip-average error components
may worsen**, including roughness and periodicity, even when the objective is
`spectrum`. The chosen objective must still improve strictly. If changes do
not pass, the relevant baseline frames remain. This favors small refinements
to a useful harmonic result; it can miss a better result requiring new voice
assignments or envelope synthesis. Listening remains necessary: these checks
do not measure intelligibility directly or prevent every local regression.

The following wider candidate table describes **free** mode, retained for
experimentation and effects. Free mode keeps its previous acceptance rules.

### What it searches, and the bounds

| Setting | Candidates tried by the current implementation |
|---|---|
| Tone period, per channel | Current period multiplied by 0.94, 0.98, 1.02 and 1.06, plus 18 logarithmically spaced periods across **1–4095**; rounded and clamped. It does not try every period. |
| Volume, per channel | All **16 fixed levels (0–15)**, plus **16** as the register value selecting envelope-controlled volume. |
| Tone/noise mixer | Toggle tone, noise, or both for one channel at a time. |
| Shared noise period | Every value **1–31**. |
| Shared envelope shape | All **16 shape codes**, each tried with the channel's existing mixer setting and with both tone and noise disabled so the envelope alone controls the output level. |
| Initial envelope period | Derived from the estimated source pitch, with a **70 Hz** pitch floor and **96 Hz** fallback when pitch is unavailable; uses a divisor of 512 for shapes 10/14 and 256 otherwise, clamped to **1–65535**. |
| Envelope-period refinement | When the current candidate uses an envelope: period offsets **−2, −1, +1, +2**, plus 20 logarithmically spaced periods across **1–65535**, without restarting its shape. Keeping the shape unchanged is also an explicit option. |

Noise and envelope generators are shared across channels, so changing them
can affect several voices. `--channels` restricts playback to **1, 2 or 3**
channels; unused channels are forced silent in every candidate. Tone, noise
and envelope period zero are not newly proposed by these searches. The
`R13=255` value in the stream means “do not write the envelope shape,” not an
additional hardware shape.

The simulator currently fixes the AY clock at **1,764,750 Hz** and register
updates at **60.1145 Hz**. The optimizer does not search clock rate, frame
duration, channel count, source filters or output-circuit parameters. Those
are fixed settings for each run, with channel count and filters chosen by
the caller.

### How a candidate is scored and accepted

Each local comparison includes the candidate frame and **1,024 preceding
audio samples** (about 23.2 ms), giving roughly a 40 ms window. There is no
future-frame look-ahead. A Hann window and 4,096-point FFT feed **48 logarithmic
frequency bands**. The spectral error compresses magnitudes so weaker speech
bands still matter, and includes an RMS-level penalty with safeguards against
nearly silent windows dominating the score.

`--objective spectrum` uses that spectral/RMS score. The default `joint`
objective adds three terms:

- **Waveform similarity**, weight **0.8**: correlation with one time offset
  limited to **±220 samples (about ±5 ms)**. It does not time-warp the signal or
  require absolute phase alignment. This term is disabled for near silence.
- **Periodicity**, weight **0.5**: compare normalized autocorrelation over
  lags **16–640 samples**, to help preserve repeating tone structure.
- **Roughness**, weight **0.1**: compare the RMS difference between adjacent
  samples, discouraging inappropriate rapid fluctuations.

The resulting proposal is then checked against the original baseline. The
optimizer first tries replacing the whole clip, then successive four-frame
blocks, then individual frames. Each trial is re-rendered from the beginning
and scored across the complete clip, accounting for the state changes it
causes later. A replacement is kept only if the current whole-clip objective
improves. In free `joint` mode, average spectral and waveform errors must also
individually not worsen (apart from a tiny numerical tolerance). Conservative
mode applies that requirement to all four components. These are
clip-average safeguards; an individual frame or a listener's perception can
still get worse. If no proposals pass, the baseline is retained.

The `berzerk` profile deliberately uses spectral scoring to generate local
candidates, then the requested objective for final acceptance—`joint` by
default. The conversion metadata records both objectives, before/after
component scores, candidate evaluations and accepted blocks.

### Frequency limits and model assumptions

`--low` defaults to **80 Hz**. `--high` defaults to **7,000 Hz** for `ayfit`,
or **6,500 Hz** for the normal `aydemo` profile; the `berzerk` profile uses
7,000 Hz. These set the objective's analysis band and, for the filtered
profile, source filtering. The input filter also limits its upper cutoff to
43% of the source sample rate. These are analysis choices, not guaranteed
output bandwidth or bounds on the tone periods the search may propose.

The output-circuit approximation uses a feedback shelf near **11,702.57 Hz**
and a DC/high-frequency gain ratio of **7.8**, based on the previous
R14=680 kΩ, C23=20 pF, R15=100 kΩ interpretation. `--feedback-cutoff` must be
positive and `--feedback-gain` at least 1; they configure the model, not
parameters automatically fitted by the optimizer. This is not a measured
complete amplifier/speaker response and omits diode and speaker nonlinearities.

### Possible future improvements

These are development possibilities, not features of the current tools:

- **Search several frames together.** Retain a small set of promising paths
  and evaluate upcoming frames before choosing one. This could improve
  envelope continuity and fast laser sweeps that a greedy frame decision misses.
- **Refine promising parameter regions.** Try finer period steps, coupled
  channel changes and multiple starting solutions, instead of relying on the
  fixed coarse grids and a single harmonic seed.
- **Improve perceptual scoring.** Combine short windows for transients with
  longer windows for low pitches, and tune speech/effect objectives against
  controlled listening comparisons. A lower numerical error alone does not
  establish better intelligibility or a more convincing effect.
- **Calibrate the output model.** Compare real-machine recordings with the
  renderer, fit the amplifier response, and test sensitivity to initial chip
  phase and hardware variation so improvements transfer more reliably.
- **Include storage and playback cost.** Penalize unnecessary register
  changes or compressed size, and explore compact channel-specific streams.
  The current optimizer minimizes audio error, not ROM bytes or CPU time.
- **Reduce conversion time.** Cache duplicate candidate evaluations and
  reuse intermediate rendering where state permits. Whole-clip acceptance
  checks currently re-render every trial, which becomes expensive for longer
  recordings.

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
