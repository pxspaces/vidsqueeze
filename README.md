<img src="vidsqueeze/web/icon.svg" width="52" alt="VidSqueeze logo">

# VidSqueeze

**Compress and convert video, audio, photos and camera RAW on your own computer.**
Free and open source, for Windows, macOS and Linux. Nothing is uploaded anywhere,
there are no file size limits, and you need to know nothing about codecs.

**It needs the internet once, and then never again.** On first run it fetches
ffmpeg into its own folder. After that you can turn the network off and VidSqueeze
keeps working, on a plane, on a train, or on a machine that has never been online.

That is the real difference from a converter on the web. Those want the file
uploaded first, which puts your holiday videos, your client photographs or your
recordings on somebody else's server, under their size limits, their queue, their
privacy policy and their decision about how long to keep a copy. Nothing you
convert here leaves the computer, because there is nowhere for it to go.

Double-click one file. VidSqueeze opens in your browser. Choose your files, pick
what you want, press Squeeze. If a tool it needs is missing, it offers to fetch
that tool and keeps it inside its own folder.

People who prefer a terminal get every feature as command line flags.

| Kind           | Reads                                                        | Writes                                       |
| -------------- | ------------------------------------------------------------ | -------------------------------------------- |
| **Video**      | MP4, MOV, MKV, AVI, WebM, MPEG, WMV, FLV and more            | MP4, MKV, WebM, MOV in H.265, H.264, AV1, VP9 |
| **Audio**      | MP3, M4A, AAC, WAV, FLAC, OGG, Opus, WMA, AIFF               | Opus, AAC, MP3, FLAC                          |
| **Photos**     | JPEG, PNG, WebP, AVIF, HEIC, TIFF, BMP, GIF, JPEG XL         | JPEG, PNG, WebP, AVIF, JPEG XL, TIFF, BMP     |
| **Camera RAW** | CR2, CR3, NEF, ARW, RAF, ORF, RW2, PEF, DNG and twenty more  | any photo format above                        |

Camera RAW is handled properly rather than as an afterthought: developed at 16 bits
per colour with the camera's own white balance, keeping the camera, lens, exposure
and the date the photograph was taken. There are contact sheets too, for picking
which of sixty frames are worth keeping.

**Documentation:** [User guide](USER-GUIDE.md) &middot;
[Everything it can do](FEATURES.md) &middot; [What changed](CHANGELOG.md) &middot;
[Video](docs/GUIDE-VIDEO.md) &middot; [Photos](docs/GUIDE-IMAGES.md) &middot;
[Audio](docs/GUIDE-AUDIO.md)

---

## Where to put it

**Put the VidSqueeze folder somewhere permanent before you use it:**

| System  | Suggested location                     |
| ------- | -------------------------------------- |
| Windows | `C:\Users\<you>\Documents\VidSqueeze`   |
| macOS   | `~/Documents/VidSqueeze`               |
| Linux   | `~/Documents/VidSqueeze`               |

1. **Keep the folder together.** The launcher only works from inside it, so move
   the whole folder rather than dragging the launcher out. Make a shortcut if you
   want it on your desktop.
2. **Avoid Downloads and temporary folders.** VidSqueeze stores the tools it
   downloads, and by default your converted files, inside its own folder.

No administrator rights are needed, and nothing is installed anywhere else.
Deleting the folder removes VidSqueeze completely.

---

## Getting it

```
cd ~/Documents
git clone https://github.com/pxspaces/vidsqueeze.git VidSqueeze
```

Or download the ZIP from the repository page and unpack it into the location
above.

## Starting it

| System      | What to do                                                                |
| ----------- | ------------------------------------------------------------------------- |
| **Windows** | Double-click **`Start VidSqueeze.bat`**                                    |
| **macOS**   | **Right-click** **`Start VidSqueeze.command`**, choose **Open**, confirm    |
| **Linux**   | Double-click **`start-vidsqueeze.sh`**, or run `./start-vidsqueeze.sh`      |

macOS needs the right-click the first time only, because the file came from the
internet. After that, double-clicking works.

Missing Python? On Windows VidSqueeze downloads a private copy, about 11 MB,
into its own folder. On macOS and Linux it names the one command that installs
it.

The [user guide](USER-GUIDE.md) has these steps in full, with what to do when
each one misbehaves.

---

## First run

VidSqueeze needs **ffmpeg**, which does the actual conversion. If it is not
already on your computer, press **Download and continue**, roughly 60 to 75 MB,
saved in the `bin` folder next to this file.

Prefer to install it yourself? Any of these work, and VidSqueeze will find it:

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

**Photos and graphics** into JPEG, PNG, WebP, AVIF, JPEG XL, TIFF or BMP, with a
quality dial, a size limit and proper handling of transparency.

**Camera RAW** from Canon, Nikon, Sony, Fujifilm, Olympus, Panasonic, Pentax,
Leica and others. ffmpeg cannot read RAW, so VidSqueeze uses the best decoder
installed and falls back to the camera's embedded preview when there is none,
telling you which it used.

Presets cover the things people actually want: WhatsApp and email size limits,
short-form video, YouTube, websites, web-ready photographs and thumbnails. The
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
- **Updates are checked when you ask**, never on startup, and VidSqueeze can
  update itself in place. No terminal, no git, nothing to re-download.

---

## Using it from a terminal

```
vidsqueeze                          open the interface
vidsqueeze holiday.mp4              convert one file with the default settings
vidsqueeze ~/Videos                 convert everything in a folder
vidsqueeze -p whatsapp clip.mov     fit WhatsApp's size limit
vidsqueeze -p photo_web *.png       convert photographs for the web
vidsqueeze --terminal               step-by-step questions instead of flags
vidsqueeze --list-presets           show every preset
vidsqueeze --info video.mp4         describe a file without changing it
vidsqueeze --dry-run video.mp4      show the command without running it

vidsqueeze --image-format png photo.cr2               develop a camera RAW
vidsqueeze --image-format webp --lossless picture.png an exact, smaller copy
vidsqueeze --image-format jpeg --image-quality 95 *.tif
```

Run it as `python3 -m vidsqueeze` from inside the folder, or use the launcher.
`--help` lists every option.

VidSqueeze opens your computer's default browser. To use a different one, once:

```
vidsqueeze --browser firefox
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

ffmpeg does the encoding. VidSqueeze builds the command, runs it, reads its
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

ffmpeg is a separate program under its own licence. VidSqueeze downloads it at
runtime rather than bundling it, and does not modify it.
