# Changelog

Everything that changed, newest first. This is a living document: any change to
what the program does is recorded here.

Dates are the day the change was made.

---

## 1.11.0 - 2026-08-17

### Added

- **The Updates window now shows what is new.** It used to offer a version number
  and nothing else, so the only way to find out what you were about to install was
  to go and read the project page. What changed, what was fixed and what was added
  now appear in the window, under the version being offered, taken from the release
  itself. It is shown only when there is an update to take, because a list of what
  you already have is not news.

  The notes are text from the internet, and the window that displays them can
  convert and delete your files, so they are never treated as anything but text.
  Only headings, lists, bold, code and ordinary links are understood, links only
  when they point at a real web address, and everything else appears as itself.

---

## 1.10.0 - 2026-08-17

### Added

- **Pause a batch.** Sixty files is twenty minutes of your computer being busy,
  and sometimes that has to wait. **Pause** appears next to Stop while a batch is
  running, and **Carry on** starts it again. The file already being worked on is
  allowed to finish rather than being cut off, which would leave a half written
  file behind, so pausing takes effect from the next one. The estimate of time
  remaining does not count the pause against you.
- **The summary now separates the two kinds of success.** Sixty files of which
  forty came out larger is a very different outcome from sixty that all shrank,
  and reporting both as "done" hid which had happened. It now says how many came
  out smaller and how many came out larger, and suggests what to do about the
  latter. On the command line too.

---

## 1.9.0 - 2026-08-17

### Added

- **Contact sheets.** One image showing small versions of every photograph in a
  folder, with the file names under them. A shoot is sixty pictures that all look
  identical in a file listing, and a sheet is still the fastest way to pick the
  four worth keeping.

  **Make a contact sheet** appears under the buttons whenever the files you have
  added include pictures, with the number it will use. It reports progress while
  it works, because sixty camera RAW files means sixty developments and takes a
  couple of minutes, can be stopped part way, and shows the finished sheet in the
  window when it is done. How many across and how big are under Advanced image
  settings.

  From a terminal:

  ```
  vidsqueeze --contact-sheet ~/Photos
  vidsqueeze --contact-sheet --sheet-out ~/shoot.png --sheet-columns 6 *.CR2
  ```

  Camera RAW works exactly as it does elsewhere, developed with the same look, so
  a sheet of RAW files needs nothing extra. Anything that cannot be read is left
  off and named, rather than quietly shrinking the sheet.

### Notes

- HEIC cannot be written. It was on the list, and ffmpeg has no HEIF muxer at all,
  so there is nothing to build on. HEIC is still read.

---

## 1.8.0 - 2026-08-17

### Added

- **It now says beforehand when a file will come out bigger.** Converting a
  photograph to PNG or TIFF almost always makes it larger, because those formats
  throw nothing away. VidSqueeze used to mention this afterwards, as "the result
  is not smaller", which is true, unavoidable, and reads like a fault rather than
  a property of the format you picked. The warning now appears in the settings as
  soon as you choose such a format, while you can still choose another, and it
  names a smaller one to use instead. It stays quiet where the file will shrink,
  because a warning on every conversion is a warning nobody reads.

---

## 1.7.0 - 2026-08-17

### Fixed

- **Converted photographs looked flat and grey next to the original.** A RAW file
  is what the sensor recorded, not a finished photograph, and something has to
  decide how bright it is and how strong its colour should be. VidSqueeze was
  leaving that to the decoder, which chooses "barely at all", because it is being
  faithful to the sensor rather than to the scene. Measured against the same two
  photographs rendered by the computer's own RAW handling, conversions were about
  18 per cent too dark and 40 per cent short on colour. They now come out close
  to it, within 8 per cent on both counts.

  There is a new setting for this. **Like the photograph** is the default and is
  what almost everybody wants. **Flat, for editing** gives the old faithful
  rendering, which is the better starting point if you are going to edit the
  picture yourself.
- **PNG and TIFF could not be asked for full colour depth from the window.** The
  quality dial decides how much depth is kept for these formats, 16 bits per
  colour at 90 and above, but the dial was hidden for them because they are
  lossless and it looked as though it had nothing to do. So the interface could
  only ever produce 8 bit PNGs. The dial is now shown, and says what it does.
- **Choosing a lossless format still shrank the picture to 2560 pixels.** Asking
  for PNG is asking for fidelity, so the size limit now clears itself when you
  pick a lossless format. Set it again if you did want a smaller one.
- **Sideways photographs stored as PNG or WebP were still resized wrongly.** The
  fix in 1.6.0 read the orientation note out of JPEG and TIFF files but not out
  of PNG or WebP, which keep it somewhere else again.
- **`--dry-run` printed a video command for a photograph**, including for camera
  RAW, which was not a preview of anything that would happen. It now shows the
  develop step and the picture command.

---

## 1.6.0 - 2026-08-17

### Fixed

- **Update checking reported the wrong version, and said you were up to date
  when you were not.** The version number was written down in two places, and
  they drifted apart: the command line announced the new version while the
  window and the update check still reported the old one. There is now one
  place it is written, and the program refuses to build if a second appears.
- **Photographs taken with the camera turned sideways were made bigger, not
  smaller.** Almost every phone and camera stores a portrait photograph as a
  landscape picture plus a note saying which way up it goes. VidSqueeze was
  reading the stored shape and not the note, so it shrank the wrong side.
  Asking for a longest side of 500 pixels gave back a picture 1000 pixels tall,
  four times the size of the original, and broke the promise that images are
  never enlarged. It now reads the note.
- **Converting a photograph threw away the camera, the lens, the exposure and
  the date it was taken.** The converted file was stamped with the day it was
  converted, so a folder of holiday pictures lost the order it was taken in.
  This was worst for camera RAW, where none of it survived at all. The details
  are now carried across, and the date the photograph was taken becomes the
  date on the file, so a shoot stays in order in any folder sorted by time.
  JPEG keeps the full set of details. Other formats keep the date.

---

## 1.5.0 - 2026-08-17

### Fixed

- **Photographs from a camera came out dark and muddy.** Converting a RAW file
  produced something noticeably flatter and greyer than the same shot rendered
  by the camera. The decoder was being left on its default tone curve, which is
  not the one every viewer assumes, so every shadow was rendered darker than it
  should have been. It is now told explicitly which curve to use, and the
  difference is plain when the two are put side by side.
- **RAW files were developed at 8 bits per channel**, throwing away most of what
  the camera recorded before anything else happened. They are now developed at
  16, and at a quality setting of 90 or more the extra depth is kept all the way
  into the finished file.
- **Lossless was not lossless.** Asking for a lossless WebP produced a file that
  was neither: colour was thrown away before the encoder ever saw the image, and
  because that damage does not compress, the result was also about twice the
  size it should have been. Lossless now reproduces the original exactly.
- **Colour detail was reduced even at the highest quality.** At a quality of 90
  or more, JPEG now keeps full colour resolution instead of quartering it.
- **Converting a RAW file wrote a large temporary file into the folder holding
  your photographs**, and failed outright if that folder was read only, such as
  a memory card. Everything temporary is now kept out of the way and cleaned up.
- **A custom preset giving an exact size in odd numbers** produced an empty file
  for AV1 and AVIF, with no error. Sizes are now always brought to even numbers.

### Added

- **Image settings on the command line.** `--image-format`, `--image-quality`,
  `--lossless`, `--max-dimension` and `--background` were previously only
  reachable in the browser interface, which meant photographs and camera RAW
  could not be converted from a script. Wrong values are refused with a sentence
  rather than a stack trace.
- **A test suite**, in `tests/`. It uses nothing beyond what Python already
  includes. `python3 -m tests` runs it, and `python3 -m tests --fast` runs the
  half that needs no ffmpeg.

---

## 1.4.0 - 2026-08-17

### Fixed

- **Choosing an image size made conversion fail** with a type error. Values
  arriving from the interface were converted using a list of field names kept by
  hand, and that list had never been extended to the image settings, so a chosen
  size arrived as the text "2560" and every later comparison against it threw.
  Conversion now reads each field's declared type from the definition itself, so
  no field can be forgotten. Values outside a sensible range are brought back
  into it, and a choice that is not one of the offered options falls back to the
  default rather than travelling on to fail somewhere less obvious.
- **Test a short sample failed on photographs.** There is no such thing as eight
  seconds of a still, and sending one through the video pipeline produced an
  empty file and a confusing error. Images are now converted whole, which also
  makes the size reported the real one rather than an estimate, and it says so.

### Added

- **Update VidSqueeze from inside VidSqueeze.** The Updates window now has an
  Update now button, so nobody needs git or a terminal or to hunt down the
  download page again. A folder cloned with git is updated with git; anything
  else has the newest release downloaded and unpacked over it. Converted files,
  settings, history and the downloaded ffmpeg are untouched, and the previous
  version is kept so a bad update can be undone.
- `vidsqueeze --update` does the same from a terminal.

---

## 1.3.0 - 2026-08-17

### Fixed

- **The Check again button in Updates sat flush against the last entry.** It now
  has space and a dividing line above it, and says when the last check was made.

- **Only the first 25 files of a selection were listed.** Choosing a folder of
  two hundred photographs showed twenty-five, and the count and total size were
  wrong with them. Every file chosen is now listed. Opening each one to measure
  it is what was slow, so the first sixty are measured in full and the rest are
  listed from their name and size, which is all the list needs. The conversion
  itself always used the whole selection; it was the display that was short.
- **Measuring files was done one at a time.** Sixty files took over five
  seconds before anything appeared. They are now measured together, which brings
  the same folder down to under two.
- **Rubbish with a picture extension was listed as a real image** of no
  dimensions, and only failed later during conversion. It is now marked as
  unreadable in the list.
- Files that cannot be read no longer vanish from the list and the count. They
  are shown, marked.

### Added

- **The media type you chose now filters what you see.** In Photos, the file
  browser lists only pictures and camera RAW, and choosing a whole folder brings
  in only those. Video and Audio behave the same way. Anything applies no filter.
  The browser says how many files of other kinds it is hiding.
- **Shift-click to select a range.** Click one file, then shift-click another,
  and everything between them is taken, in either direction. There is also a
  Select all box, and the add button says how many are chosen.

---

## 1.2.0 - 2026-08-17

### Fixed

- The ignore file named development-only paths that do not exist in a published
  copy. The publishing script now writes a clean one rather than editing the
  development version, and its checks scan every file instead of a list of
  extensions, which is how a dotfile slipped past them.

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
