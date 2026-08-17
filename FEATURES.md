# What VidSqueeze can do

A complete inventory. This is a living document: anything added to the program
is added here in the same change.

Last updated for version 1.2.0.

---

## Media it handles

| Kind       | Reads                                                            | Writes                                        |
| ---------- | ---------------------------------------------------------------- | --------------------------------------------- |
| **Video**  | MP4, MOV, MKV, AVI, WebM, M4V, MPG, WMV, FLV, TS, M2TS, MTS, 3GP, OGV, VOB, MXF and more | MP4, MKV, WebM, MOV        |
| **Audio**  | MP3, M4A, AAC, WAV, FLAC, OGG, Opus, WMA, AIFF                    | MP3, M4A, and the audio inside any video file |
| **Images** | JPEG, PNG, WebP, AVIF, HEIC, TIFF, BMP, GIF, JPEG XL, QOI, PPM, TGA | JPEG, PNG, WebP, AVIF, JPEG XL, TIFF, BMP   |
| **Camera RAW** | CR2, CR3, CRW, NEF, NRW, ARW, SRF, SR2, RAF, ORF, RW2, PEF, SRW, DNG, 3FR, DCR, KDC, MRW, MOS, IIQ, X3F, ERF, RWL, GPR | converted to any image format above |

HEIC, the format iPhones use for photos, needs a recent ffmpeg. If the one on
your computer cannot open a file, VidSqueeze says so and offers to download a
newer build into its own folder.

Camera RAW needs a decoder that ffmpeg does not include. See
[Camera RAW](#camera-raw) below.

---

## Ways to run it

| Way                    | Command or action                    | Who it suits                    |
| ---------------------- | ------------------------------------ | ------------------------------- |
| Browser interface      | Double-click the launcher            | Everyone. This is the default.  |
| Terminal, with flags   | `vidsqueeze holiday.mp4`             | Scripting and batch work        |
| Terminal, step by step | `vidsqueeze --terminal`              | Terminal users who want prompts |

The interface opens in **the computer's own default browser**. To use a
different one: `vidsqueeze --browser firefox`, which is then remembered.

---

## The interface

Three panes, each of the side ones collapsible by the arrow in its header or by
clicking its collapsed edge.

- **Sources** on the left: everything you have added, with size, resolution and
  length, and live progress while converting.
- **Workspace** in the middle: Settings, Preview, Compare, Watch and History.
- **Results** on the right: finished files. Selecting one opens Compare.

On narrow screens the three panes stack vertically.

---

## Presets

Presets are filtered to whatever you have selected, so choosing photographs does
not offer you video codecs.

**Everyday (video)** Balanced, High quality, Archive, Small, Shrink to 1080p,
Shrink to 720p.

**Share and upload (video)** WhatsApp (16 MB), Discord free (10 MB),
Email (25 MB), Short-form video for Reels, Shorts and TikTok, YouTube upload,
Website.

**Convert (video)** Plays anywhere (H.264), AV1, WebM, Change container only.

**Audio** Extract as MP3, Extract as M4A.

**Images** Photo for the web, WebP, AVIF, PNG, Photo for messaging, Thumbnail,
Archive quality (lossless WebP).

You can add your own: rename `presets.example.json` to `presets.json` and edit
it. Custom presets appear alongside the built-in ones, and reusing a built-in
key replaces it.

---

## Video and audio settings

| Setting            | Choices                                                     |
| ------------------ | ----------------------------------------------------------- |
| Video format       | H.265, H.264, AV1, VP9, or copy without re-encoding          |
| File type          | MP4, MKV, WebM, MOV, M4A, MP3                                |
| Quality mode       | Quality level, fit a file size, or an exact bitrate          |
| Quality level      | Maximum, High, Balanced, Small, Tiny, or an exact CRF number |
| Encoding speed     | ultrafast through veryslow                                   |
| Resize             | 4K, 1440p, 1080p, 720p, 480p, 360p, or keep original         |
| Framerate          | Cap at 60, 30, 25 or 24, or keep original                    |
| Trim               | Start and end, by number or by dragging on the filmstrip     |
| Audio              | Opus, AAC, MP3, FLAC, copy, or remove                        |
| Audio bitrate      | 64 to 320 kbps                                               |
| 10-bit colour      | Better gradients, slightly larger files                      |
| HDR to standard    | Stops the washed-out grey look, on by default                 |
| Reduce grain       | Helps noisy low-light footage compress                       |
| Fix interlacing    | For old camcorder and broadcast footage                      |
| Web playback       | Moves the index to the front so playback starts sooner       |
| Subtitles          | Carry them across                                            |
| Metadata           | Keep or strip dates and camera information                   |

**Fitting a file size** is treated as a ceiling, not a quota: a video that
already fits is left alone rather than inflated. It uses two-pass encoding so
the result lands close to, and under, the limit.

---

## Image settings

| Setting        | Choices                                                       |
| -------------- | ------------------------------------------------------------- |
| Convert to     | JPEG, PNG, WebP, AVIF, JPEG XL, TIFF, BMP                      |
| Quality        | 1 to 100, mapped correctly onto each format's own scale        |
| Lossless       | WebP and JPEG XL                                               |
| Longest side   | 4096, 2560, 1920, 1600, 1080, 512, or keep original            |
| Background     | White, black or grey, when flattening transparency             |

Transparency is preserved wherever the target format supports it. Where it does
not, such as JPEG, the image is composited onto your chosen background rather
than turning transparent areas black, and VidSqueeze tells you it did so.

Images are never enlarged.

---

## Camera RAW

ffmpeg cannot read camera RAW. Its "raw" decoders are for Cintel, DPX and
OpenEXR, none of which is what comes off a Canon or a Nikon. VidSqueeze
therefore looks for a proper decoder and uses the best one installed:

| Decoder      | Result                                              |
| ------------ | --------------------------------------------------- |
| darktable    | Full resolution, the camera's own colour handling    |
| RawTherapee  | Full resolution, high quality development            |
| LibRaw       | Full resolution                                      |
| dcraw        | Full resolution                                      |
| ImageMagick  | Good quality, often at half resolution               |

Once developed, the image goes through the ordinary picture pipeline, so every
setting works exactly as it does for a JPEG.

**If none of them is installed**, VidSqueeze uses the preview image the camera
stored inside the RAW file. That needs nothing installed and always produces
something, but it is the camera's own rendering and is often well below full
resolution, so it is labelled as such rather than presented as a real
conversion. VidSqueeze also names the single command that would fix it, chosen
for the system you are on:

```
winget install ImageMagick.ImageMagick    # Windows
brew install libraw                       # macOS
sudo apt install libraw-bin               # Linux, or the dnf/pacman/zypper equivalent
```

---

## What do you work with?

On first run VidSqueeze asks whether you work with video, audio, photos, or
anything. This only decides which settings you are shown: nothing is locked
away. The answer is remembered, and the selector stays in the header so you can
change it whenever you like.

Selecting files always wins over the setting. Add a photograph while in Video
mode and the picture settings appear anyway.

---

## Updates

The **Updates** button reports two separate things: whether a newer VidSqueeze
exists, and whether a newer ffmpeg exists. ffmpeg can be updated in place, which
downloads a current build into the VidSqueeze folder and uses it from then on,
leaving whatever the system has alone.

Nothing is checked unless you press the button. VidSqueeze does not contact
anything on startup.

---

## Speed

Encoding is genuinely slow work. Measured on an eight-core laptop, for thirty
seconds of 1080p:

| Setting                    | Time | Result |
| -------------------------- | ---- | ------ |
| H.264, medium              | 13 s | 29 MB  |
| H.264, veryfast            |  9 s | 26 MB  |
| H.264 on the graphics card |  5 s | 50 MB  |
| H.265, veryfast            | 30 s | 17 MB  |

H.265 is roughly three times slower than H.264, which is the price of its much
smaller files.

**Graphics card acceleration** is offered only after VidSqueeze has proven it
works, by running a short real encode once and caching the answer. Plenty of
hardware advertises encoders it cannot actually use. It is presented as an
explicit choice, with its cost stated: about twice as fast, noticeably larger
files.

**Encode two files at once** helps batches of shorter clips by recovering the
time each file spends starting and finishing. It is capped by processor count.

---

## Test before you commit

**Test a short sample** converts about eight seconds with your current settings
and reports what the whole file would come to, in both size and time.

**Try several settings** does the same at two or three settings at once, so you
can choose before spending minutes on the wrong one. Press "Use this" on the
winner.

On uniform footage the estimate lands within a percent or two. Material that
mixes still and busy scenes varies more, because a sample cannot know what the
rest of the file looks like.

---

## Compare

Select a finished file in Results.

- **Frames or Images**: the same moment from the original and the result, behind
  a divider you drag, or move with the arrow keys. This always works, whatever
  the format.
- **Play or Listen**: both files side by side, with **Play both together** when
  the browser can manage both. If it can only play one, that one still plays and
  the other is one button away in your own program. If it can play neither, both
  buttons remain.
- Exact sizes drawn to scale, the compression ratio, and a table of dimensions,
  format, audio, bitrate, length and transparency.
- **Open original** and **Open result** always open the real files in whatever
  program your computer normally uses.

---

## Preview and trim

Selecting a source shows it: video and audio play if the browser supports the
format, images display, and anything unplayable still shows a still frame.

Videos get a **filmstrip** of thumbnails with start and end handles. Set the
points, press "Use these trim points", and they apply to the batch.

---

## Watch a folder

VidSqueeze can watch a folder and add anything new to Sources. It waits until a
file has stopped growing, so a video still copying off a memory card is not
converted half-written.

**It never starts converting by itself.** New files wait in Sources until you
press Squeeze.

---

## Where files go, and safety

Results are written to the **`output` folder inside VidSqueeze**, so they never
mix with your originals or land somewhere unexpected. You can point elsewhere.

**Originals are never touched by default.** There is an opt-in setting to delete
each one after converting. When it is on, an original is deleted only after the
new file passes every check:

- it exists and is not empty
- it can be opened and read back
- it contains the streams it should
- its length matches what was expected
- it is genuinely smaller than the original

If any check fails the original is kept and the reason is shown.

---

## History

What has been converted and how much space has been reclaimed, from the terminal
as well as the interface. Kept in `history.json` inside the folder, holding only
names, sizes and dates. Clear it whenever you like.

---

## Command line

```
vidsqueeze                          open the interface
vidsqueeze holiday.mp4              convert one file with the default settings
vidsqueeze ~/Videos                 convert everything in a folder
vidsqueeze -p whatsapp clip.mov     fit WhatsApp's size limit
vidsqueeze -p photo_web *.png       convert photographs for the web
vidsqueeze --terminal               step-by-step questions
vidsqueeze --list-presets           every preset
vidsqueeze --info video.mp4         describe a file, change nothing
vidsqueeze --dry-run video.mp4      show the command without running it
vidsqueeze --setup                  download ffmpeg and exit
```

Flags: `--codec --container --quality --crf --size --bitrate --speed --scale
--fps --trim-start --trim-end --audio --audio-bitrate --hardware --replace
--10bit --denoise --deinterlace --no-tonemap --keep-subtitles --no-metadata
--browser --port --no-browser --no-download -o -p`

---

## Privacy and security

Nothing is uploaded anywhere. The only network access is downloading ffmpeg, and
only when you ask for it.

The interface is a server on `127.0.0.1` that your own browser talks to. It is
not reachable from your network. Every request must carry a key generated fresh
each time it starts, and requests arriving under any other hostname are refused,
so no other page or program can drive it.
