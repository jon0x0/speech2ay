# TS2068 Audio Lab on GitHub Pages

[Play the demo](https://jon0x0.github.io/speech2ay/) ·
[Source repository](https://github.com/jon0x0/speech2ay)

The page automatically loads the four-sample Audio Lab cartridge. Click
**Start Audio Lab** to enable sound, then use the keyboard or on-screen controls.

## Live TSRun integration

The local adapter imports emulator modules directly from
https://josef-jelinek.github.io/TSRun/ and fetches its hosted system ROMs and
display shaders. A tiny AudioWorklet entry imports the upstream mixer too.
No emulator implementation or system ROM is copied into this repository.
TSRun serves these resources with cross-origin access enabled.

This is a local emulator view using live upstream components, rather than an
iframe of TSRun's application page. Our adapter inserts the local DCK using
TSRun's insertDock API after fetching the system ROMs, then resets the machine.
It sends a ready/error notification to the page and offers a user-gesture sound
start. The browser frame loop uses the TS2068's 58,688 T-state frame period.

Upstream updates become available after ordinary browser/CDN cache expiry.
Upstream downtime, cross-origin policy changes or incompatible API changes can
affect the demo; startup failures are reported and the DCK download remains
available. Initially checked against TSRun revision
390ecb5d6b0dd26bf0fd1e958b25e4237369dc38; the deployed page follows the live site.

## Local preview and deployment

Run `python -m http.server 8000 --directory web`, then open
http://localhost:8000/. A network connection to TSRun is required. ES modules
and AudioWorklet need HTTP on localhost or HTTPS, not a directly opened file.

The Pages workflow renders documentation and publishes web/ on pushes to main.
To regenerate documentation locally, use Node 22 or later:

```sh
npm install --ignore-scripts
npm run build:web
```

To replace the demo, copy comparison.dck and picorom.bin into web/assets/
using the existing filenames, then update demo.json and preview.png. Preserve
the native-RAM/contiguous-ROM layout described in integration.md and test the
browser as well as Fuse. TS2068 Audio Lab is the demo name; speech2ay is the
toolkit and repository name.
