<img src="halveit/web/icon.svg" width="52" alt="HalveIt logo">

# HalveIt

**Compress and convert video and audio on your own computer.**
Free and open source, for Windows, macOS and Linux. Nothing is uploaded anywhere,
there are no file size limits, and you need to know nothing about codecs.

**It needs the internet once, and then never again.** On first run it fetches
ffmpeg into its own folder. After that you can turn the network off and HalveIt
keeps working, on a plane, on a train, or on a machine that has never been online.

That is the real difference from a converter on the web. Those want the file
uploaded first, which puts your holiday videos or your
recordings on somebody else's server, under their size limits, their queue, their
privacy policy and their decision about how long to keep a copy. Nothing you
convert here leaves the computer, because there is nowhere for it to go.

Double-click one file. HalveIt opens in your browser. Choose your files, pick
what you want, press Compress. If a tool it needs is missing, it offers to fetch
that tool and keeps it inside its own folder.

People who prefer a terminal get every feature as command line flags.

| Kind           | Reads                                                        | Writes                                       |
| -------------- | ------------------------------------------------------------ | -------------------------------------------- |
| **Video**      | MP4, MOV, MKV, AVI, WebM, MPEG, WMV, FLV and more            | MP4, MKV, WebM, MOV in H.265, H.264, AV1, VP9 |
| **Audio**      | MP3, M4A, AAC, WAV, FLAC, OGG, Opus, WMA, AIFF               | Opus, AAC, MP3, FLAC                          |


<!-- SOON:START -->
### Pictures are coming later

Stills and camera RAW are being worked on and are not in this version. They were
close, but not close enough to hand somebody a wedding shoot and tell them it was
fine, so they wait. When they arrive it will be as a release of its own, with
measurements published alongside it rather than a promise.

Video and audio are finished work, and are what this version does.
<!-- SOON:END -->

**Documentation:** [User guide](USER-GUIDE.md) &middot;
[Everything it can do](FEATURES.md) &middot; [What changed](CHANGELOG.md) &middot;
[Audio](docs/GUIDE-AUDIO.md)

---

## Where to put it

**Put the HalveIt folder somewhere permanent before you use it:**

| System  | Suggested location                     |
| ------- | -------------------------------------- |
| Windows | `C:\Users\<you>\Documents\HalveIt`   |
| macOS   | `~/Documents/HalveIt`               |
| Linux   | `~/Documents/HalveIt`               |

1. **Keep the folder together.** The launcher only works from inside it, so move
   the whole folder rather than dragging the launcher out. Make a shortcut if you
   want it on your desktop.
2. **Avoid Downloads and temporary folders.** HalveIt stores the tools it
   downloads, and by default your converted files, inside its own folder.

No administrator rights are needed, and nothing is installed anywhere else.
Deleting the folder removes HalveIt completely.

---

## Getting it

```
cd ~/Documents
git clone https://github.com/pxspaces/halveit.git HalveIt
```

Or download the ZIP from the repository page and unpack it into the location
above.

## Starting it

| System      | What to do                                                                |
| ----------- | ------------------------------------------------------------------------- |
| **Windows** | Double-click **`Start HalveIt.bat`**                                    |
| **macOS**   | Double-click **`Start HalveIt.command`**                                  |
| **Linux**   | Double-click **`start-halveit.sh`**, or run `./start-halveit.sh`      |

**If macOS refuses to open it**, that is because a browser downloaded it. macOS
marks anything a browser fetches and asks before running it once. It does not
happen if you cloned this repository or downloaded it from a terminal, only if
you used a browser. Try to open it first, so the refusal is recorded, then:

- **macOS 15 Sequoia and later:** open **System Settings**, go to
  **Privacy & Security**, scroll to the bottom, and press **Open Anyway** beside
  the message about HalveIt. Confirm, and it never asks again.
- **macOS 14 and earlier:** right-click the file, choose **Open**, then press
  **Open** in the warning.

Either way it is once, not every time. A terminal is not affected at all, so
`bash "Start HalveIt.command"` works whatever macOS thinks.

Missing Python? On Windows HalveIt downloads a private copy, about 11 MB,
into its own folder. On macOS and Linux it names the one command that installs
it.

The [user guide](USER-GUIDE.md) has these steps in full, with what to do when
each one misbehaves.

---

## First run

HalveIt needs **ffmpeg**, which does the actual conversion. If it is not
already on your computer, press **Download and continue**, roughly 60 to 75 MB,
saved in the `bin` folder next to this file.

Prefer to install it yourself? Any of these work, and HalveIt will find it:

```
winget install Gyan.FFmpeg      # Windows
brew install ffmpeg             # macOS
sudo apt install ffmpeg         # Linux, or your distribution's equivalent
```

---

## What it does

**Video** into H.265, H.264, AV1 or VP9, with quality levels, exact file size
targets, resizing, framerate capping, trimming, HDR conversion, grain reduction
and deinterlacing.

**Audio** extracted from video or converted between formats.


Presets cover the things people actually want: WhatsApp and email size limits,
short-form video, YouTube and websites. The
presets on offer change to suit whatever you selected.

[The full inventory is in FEATURES.md](FEATURES.md).

### Worth knowing

- **Test before you commit.** Convert a short sample, or several settings at
  once, and see the finished size and time before spending minutes on it.
- **Compare properly.** Wipe between the original and the result frame by frame,
  play both together, or open either in your own player.
- **Size targets are a ceiling, not a quota.** A file that already fits is left
  alone rather than inflated.
- **Graphics card acceleration is proven, not assumed.** It is offered only
  after a real test encode succeeds, and its cost is stated: about twice as fast,
  noticeably larger files.
- **Your originals are never touched by default.** Deleting them is opt-in, and
  happens only after the result passes every check.
- **It asks once what you work with**, then shows you only the settings that
  matter. Change it any time from the header.
- **Updates are checked when you ask**, never on startup, and HalveIt can
  update itself in place. No terminal, no git, nothing to re-download.

---

## Using it from a terminal

```
halveit                          open the interface
halveit holiday.mp4              convert one file with the default settings
halveit ~/Videos                 convert everything in a folder
halveit -p whatsapp clip.mov     fit WhatsApp's size limit
halveit --terminal               step-by-step questions instead of flags
halveit --list-presets           show every preset
halveit --info video.mp4         describe a file without changing it
halveit --dry-run video.mp4      show the command without running it
```

Run it as `python3 -m halveit` from inside the folder, or use the launcher.
`--help` lists every option.

HalveIt opens your computer's default browser. To use a different one, once:

```
halveit --browser firefox
```

---

## Your own presets

Rename `presets.example.json` to `presets.json` and edit it. Custom presets
appear alongside the built-in ones, and reusing a built-in key replaces it.

---

## How it works

Python with no third-party dependencies, so it runs on whatever Python your
system already has. The interface uses one typeface, Inter, bundled into the
folder so it looks the same offline.

The interface is a small server bound to `127.0.0.1` that your browser talks to.
It is not reachable from your network, every request must carry a key generated
fresh at startup, and requests arriving under any other hostname are refused.

ffmpeg does the encoding. HalveIt builds the command, runs it, reads its
progress, and checks the result.

Nothing is uploaded anywhere. The only network access is downloading ffmpeg.

There is a test suite, which also needs nothing installed:

```
python3 -m tests            everything
python3 -m tests --fast     the half that does not need ffmpeg
```

Some of it builds ffmpeg commands and checks them. The rest converts a generated
test picture and measures the result, because a setting that looks right in a
command can still ruin the image, and only measuring catches that.

---

## Licence

MIT. See [LICENSE](LICENSE).

ffmpeg is a separate program under its own licence. HalveIt downloads it at
runtime rather than bundling it, and does not modify it.
