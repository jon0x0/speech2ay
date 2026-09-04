# Development

Use Python3.10 or newer:

```sh
python -m pip install -e .
python -m unittest discover -s tests -p "test_*.py"
python speech2ay.py --help
python audio2aydac.py --help
python ayfit.py --help
python aydemo.py --help
```

Pasmo is required for exported executable artifacts. Ayumi source and GCC are
required for optimization and modeled spectra. Upstream Audio2AY is optional.
See docs/command-line-guide.md for configuration and complete commands.

Tests named verify_* require the tools listed by their --help. Fuse recording
tests require Windows and an explicit Fuse executable. Unit tests use synthetic
signals; do not add copyrighted recordings or ROMs. Historical emulator test
results and the unresolved intermittent-volume report are in docs/validation.md.

The generated reference assembler source is asm/audio_runtime.asm. After changing
tsaudio/assembly.py, regenerate it with `python examples/export_runtime.py`.
Preserve measured TS2068 playback timing when changing the runtime.
