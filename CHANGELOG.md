# Changelog

Everything that changed, newest first. This is a living document: any change to
what the program does is recorded here.

Dates are the day the change was made.

---

## 1.2.0 - 2026-08-17

### Added

- **Camera RAW.** Converts CR2, CR3, NEF, ARW, RAF, ORF, RW2, DNG and twenty
  more, covering eighteen camera makers. ffmpeg cannot read RAW at all, so
  VidSqueeze looks for a decoder, in descending order of quality: darktable,
  RawTherapee, LibRaw, dcraw, then ImageMagick. The developed image then goes
  through the ordinary picture pipeline, so every setting behaves as it does for
  a JPEG.
- **A fallback when no decoder is installed.** The preview image the camera
  stored inside the RAW is used instead. It always works and needs nothing
  installed, and is reported honestly as the camera's own rendering rather than
  passed off as a full conversion. Where a decoder would be better, VidSqueeze
  names the one command to install it, chosen for the machine it is running on.
- **Update checking.** A button that reports whether a newer VidSqueeze or a
  newer ffmpeg exists, and updates ffmpeg in place. Nothing is checked unless
  you ask.
- **A media type question, asked once.** On first run VidSqueeze asks whether
  you work with video, audio, photos or anything. The answer decides which
  settings are shown, is remembered, and can be changed at any time from the
  selector in the header.

### Changed

- Settings now follow the chosen media type when nothing is selected, instead of
  showing everything at once. What is actually selected still takes precedence.

---

## 1.1.0 - 2026-08-17

### Added

- **Still images.** VidSqueeze now converts photographs and graphics as well as
  video and audio. Reads JPEG, PNG, WebP, AVIF, HEIC, TIFF, BMP, GIF, JPEG XL
  and more; writes JPEG, PNG, WebP, AVIF, JPEG XL, TIFF and BMP. Seven image
  presets, a quality dial translated onto each format's own scale, and a longest
  side limit that never enlarges anything.
- **Transparency handling.** Preserved where the target format supports it.
  Where it does not, the image is composited onto a background colour you choose
  rather than turning black, and VidSqueeze says it did so.
- **Three-pane interface.** Sources on the left, workspace in the middle,
  Results on the right. Both side panes collapse, and the whole thing stacks on
  narrow screens.
- **Preview tab.** Plays video and audio, displays images, and shows a still
  frame for formats the browser cannot play.
- **Visual trim.** A filmstrip of thumbnails with start and end handles, instead
  of typing numbers.
- **Try several settings.** Converts a short sample at two or three settings at
  once and reports what each would mean for the whole file, so you can choose
  before committing.
- **Watch a folder.** Adds new files to Sources as they appear, waiting until
  each has finished copying. It never starts converting on its own.
- **ffmpeg capability upgrade.** When a file cannot be opened by the installed
  ffmpeg, typically an iPhone HEIC photograph, VidSqueeze offers a one-click
  download of a newer build into its own folder.
- **Logo and browser tab icon.**
- **Living documents.** `FEATURES.md`, `CHANGELOG.md`, `USER-GUIDE.md` and
  per-media guides in `docs/`.

### Changed

- **Presets are filtered to what you selected.** Choosing photographs no longer
  offers video codecs, and the settings panel changes to match.
- **Compare handles audio and partial playability.** Both files play side by
  side with **Play both together** when the browser manages both. When it can
  play only one, that one still plays instead of both being refused. Open
  original and Open result are always available.
- **The interface opens in the computer's own default browser.** Python's
  browser module keeps its own idea of the default, which disagreed with the
  system's; the operating system opener is now used instead.

### Fixed

- **AVIF produced empty files.** Two causes: `-still-picture` belongs to a
  different encoder than the one used, and scaling with `-1` produced an odd
  height, which formats with subsampled colour reject silently. Scaling now
  always rounds to an even number.

---

## 1.0.1 - 2026-08-16

### Fixed

- **The interface was unusable.** Several elements set an explicit `display`
  value in the stylesheet, which takes precedence over the `hidden` attribute,
  so hiding them from script had no effect. The file browser covered the whole
  page from the moment it loaded, ignored its close button and blocked every
  control underneath. The quality mode fields were affected in the same way. One
  rule for the `hidden` attribute fixes every case.
- The wipe divider in Compare used width arithmetic that could misalign the two
  frames on first paint. It now uses `clip-path`, and can be moved with the
  arrow keys.

---

## 1.0.0 - 2026-08-16

First version.

### Added

- Video and audio conversion with H.265, H.264, AV1 and VP9, in MP4, MKV, WebM
  and MOV.
- Quality levels, an exact quality number, fitting a file size, or an exact
  bitrate. Size targets use two passes.
- Resizing, framerate capping, trimming, HDR to standard range conversion, grain
  reduction, deinterlacing, subtitles and metadata control.
- Eighteen presets covering everyday use, sharing limits for WhatsApp, Discord
  and email, short-form video, YouTube and websites.
- Runs three ways: a browser interface, a command line, and a step-by-step
  terminal wizard.
- Downloads ffmpeg itself when missing, into its own folder, with no
  administrator rights. The Windows launcher does the same for Python.
- Graphics card encoders offered only after a real test encode proves they work.
- Compare view with a frame wipe, sizes to scale and a facts table.
- Sample testing, to estimate size and time before converting a whole file.
- History of what was converted and how much space was reclaimed.
- Originals never touched by default. Opt-in deletion only after the result is
  verified readable, complete, the right length and smaller.
- Local server bound to loopback, with a per-run key and hostname checking.

### Notes

- File size targets are a ceiling, not a quota: files that already fit are not
  inflated.
