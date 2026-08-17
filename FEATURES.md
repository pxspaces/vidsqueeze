# What VidSqueeze can do

A complete inventory. This is a living document: anything added to the program
is added here in the same change.

Last updated for version 1.4.0.

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

Images are never enlarged. This includes photographs taken with the camera
turned sideways, which are stored as a landscape picture plus a note saying
which way up they go. VidSqueeze reads the note, so a portrait photograph is
measured on the side you actually see.

### The camera, the lens and the date are kept

Converting a photograph keeps the details recorded with it: the camera and lens,
the exposure, the aperture, the ISO, and the date and time it was taken. The date
taken also becomes the date on the file, so a shoot stays in the right order in
any folder sorted by time.

| Target                         | What is kept                        |
| ------------------------------ | ----------------------------------- |
| JPEG                           | Everything above                    |
| PNG, WebP, AVIF, TIFF, BMP     | The date it was taken               |

This matters most for camera RAW, where previously none of it survived and every
converted photograph was stamped with the day it was converted.

**Strip dates and camera information** removes all of it, for photographs you
intend to share.

### It says when a file will get bigger

Some conversions cannot make a file smaller. A photograph turned into PNG or TIFF
is normally larger than the camera file, because those formats throw nothing away,
and a JPEG turned into any lossless format is larger for the same reason.

VidSqueeze says so in the settings as soon as you choose such a format, before the
work starts, and names a smaller format to use instead. It stays quiet when the
file will shrink: a warning that appears every time is a warning nobody reads.

The same wording appears on the command line, before the batch begins, because it
is worked out in one place rather than twice.

### What quality actually changes

Quality is not only how hard the picture is squeezed. At **90 and above**,
VidSqueeze stops economising on colour:

| Quality  | Colour detail                  | Photographs from a camera |
| -------- | ------------------------------ | ------------------------- |
| below 90 | colour stored at half width    | 8 bits per colour         |
| 90 or up | colour stored in full          | 16 bits per colour        |

Below 90 the saving is large and the difference is hard to see. At 90 and above
nothing is economised, which matters for photographs you intend to edit later,
and makes the files considerably bigger. A 26 megapixel photograph saved as PNG
is about 36 MB below 90, and about 120 MB above it.

PNG, TIFF and BMP are lossless whatever quality you choose. The setting only
decides how much colour depth is carried into them.

**Lossless WebP and lossless JPEG XL reproduce the original exactly**, pixel for
pixel. If you compare the two files with a measuring tool, they are identical.

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

Whichever decoder is used, VidSqueeze asks it for the camera's own white
balance, for 16 bits of colour per channel, and for the standard tone curve that
every image viewer expects. Left to their own defaults these tools use a
different curve, which nothing records in the file, so every viewer reads the
result as too dark. That is why a converted photograph used to look flatter and
greyer than the same shot straight out of the camera.

### How a RAW should look

A RAW file is not a photograph. It is what the sensor measured, and something has
to decide how bright the picture is and how strong its colour should be. A decoder
left to itself decides "barely at all", because its job is faithfulness to the
sensor, not to the scene. The result is correct and looks flat and grey beside the
same shot out of the camera.

| Choice                  | What you get                                             |
| ----------------------- | -------------------------------------------------------- |
| **Like the photograph** | The default. Close to how the camera would render it.    |
| **Flat, for editing**   | Faithful to the sensor. Duller alone, better to edit.    |

The natural setting was measured rather than chosen: two photographs in very
different light were rendered by the operating system's own RAW handling and used
as the target, and the values are the ones that come closest without clipping any
highlight, within about 8 per cent on both brightness and colour. Values that
matched one photograph exactly overshot the other by 15 per cent.

Either way, VidSqueeze does not imitate a particular camera's picture style, which
would be guessing.

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

It also filters what you are shown. In Photos, the file browser lists only
pictures and camera RAW, and choosing a whole folder brings in only those. The
browser tells you how many files of other kinds it has hidden. Anything applies
no filter at all.

Selecting files always wins over the setting for the purposes of which settings
appear: add a photograph while in Video mode and the picture settings show up
anyway.

---

## Updates

The **Updates** button reports two separate things: whether a newer VidSqueeze
exists, and whether a newer ffmpeg exists. Both can be updated from there.

**Updating VidSqueeze** needs no terminal and no git knowledge. Press **Update
now**. A folder cloned with git is updated with git, because that is what
someone who cloned it will expect; anything else has the newest release
downloaded and unpacked over it. Either way:

- your converted files, settings, history and downloaded ffmpeg are untouched
- the previous version is kept in `.cache/previous-version`, so a bad update can
  be undone
- a copy with local changes is refused rather than overwritten
- restart VidSqueeze afterwards to run the new version

`vidsqueeze --update` does the same from a terminal.

**Updating ffmpeg** downloads a current build into the VidSqueeze folder and
uses it from then on, leaving whatever the system has alone.

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

## Choosing files

The file browser lists everything of the kind you are working with, however many
that is. Select them individually, use **Select all**, or click one file and
**shift-click** another to take everything in between, in either direction, the
way a file manager behaves. **Use this folder** takes the whole folder.

Large selections are listed in full. The first sixty files are opened and
measured for resolution and length; the rest are listed from their name and
size, so a folder of hundreds appears in a second or two rather than making you
wait. Every file in the selection is converted regardless.

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

## Long batches

Sixty files is twenty minutes of the machine being busy, so a batch can be put
down and picked up again.

**Pause** sits next to Stop while a batch runs, and becomes **Carry on**. The file
already being worked on finishes rather than being cut off, which would leave a
half written file behind, so pausing takes effect from the next one. The estimate
of time remaining does not count the pause against you.

The summary at the end separates the two kinds of success:

```
Finished. 41 came out smaller, 2.3 GB saved.
23 came out larger, and would have been better left alone or sent to a format
that squeezes.
```

Both numbers matter. A run where most files grew usually means the wrong output
format was chosen, and one count of "done" hides that completely. The command line
prints the same breakdown.

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

Contact sheets, one image of everything in a folder with the names underneath.
**Make a contact sheet** appears under the buttons whenever pictures have been
added, counts its way through, can be stopped, and shows the result. From a
terminal:

```
vidsqueeze --contact-sheet ~/Photos                        named after the folder
vidsqueeze --contact-sheet --sheet-out ~/shoot.png *.CR2   choose the name
vidsqueeze --contact-sheet --sheet-columns 6 *.CR2         six across
vidsqueeze --contact-sheet --no-sheet-labels *.jpg         no names
```

Camera RAW is developed the same way it is everywhere else, so a sheet of RAW
files needs nothing extra. Anything unreadable is left off and named rather than
quietly shrinking the sheet. Names are drawn with whatever font the computer has;
if there is none, the sheet is made without them and says so.

Photographs and camera RAW, from a script as well as the interface:

```
vidsqueeze --image-format png photo.cr2           develop a RAW to PNG
vidsqueeze --image-format webp --lossless *.png   lossless WebP, exact copies
vidsqueeze --image-format jpeg --image-quality 95 *.tif
vidsqueeze --image-format avif --max-dimension 2048 ~/Pictures
```

Flags: `--codec --container --quality --crf --size --bitrate --speed --scale
--fps --trim-start --trim-end --audio --audio-bitrate --hardware --replace
--10bit --denoise --deinterlace --no-tonemap --keep-subtitles --no-metadata
--image-format --image-quality --lossless --max-dimension --background
--browser --port --no-browser --no-download -o -p`

---

## Privacy and security

Nothing is uploaded anywhere. The only network access is downloading ffmpeg, and
only when you ask for it.

The interface is a server on `127.0.0.1` that your own browser talks to. It is
not reachable from your network. Every request must carry a key generated fresh
each time it starts, and requests arriving under any other hostname are refused,
so no other page or program can drive it.
