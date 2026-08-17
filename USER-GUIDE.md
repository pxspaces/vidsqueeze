# VidSqueeze user guide

Step by step, for people who have never touched a video setting. If you can
double-click a file, you can use this.

Living document, last updated for version 1.4.0.

**Jump to:** [Windows](#getting-started-on-windows) &middot;
[macOS](#getting-started-on-macos) &middot; [Linux](#getting-started-on-linux) &middot;
[Your first conversion](#your-first-conversion) &middot;
[Video](docs/GUIDE-VIDEO.md) &middot; [Photos](docs/GUIDE-IMAGES.md) &middot;
[Audio](docs/GUIDE-AUDIO.md) &middot; [Problems](#when-something-goes-wrong)

---

## Before you start: where to put it

Put the VidSqueeze folder somewhere permanent:

| System  | Where                                  |
| ------- | -------------------------------------- |
| Windows | `C:\Users\<you>\Documents\VidSqueeze`   |
| macOS   | `/Users/<you>/Documents/VidSqueeze`     |
| Linux   | `/home/<you>/Documents/VidSqueeze`      |

Two things matter:

1. **Keep the folder together.** The launcher only works from inside it. Move
   the whole folder, and make a shortcut or alias if you want it on your desktop.
2. **Do not leave it in Downloads.** VidSqueeze keeps the tools it downloads,
   and by default your converted files, inside its own folder. If you empty that
   location periodically you will lose both.

Nothing is installed anywhere else, and no administrator password is needed.
Deleting the folder removes VidSqueeze completely.

---

## Getting started on Windows

1. Download the ZIP from the repository page and open it.
2. Drag the **VidSqueeze** folder into your **Documents** folder.
3. Open it and double-click **`Start VidSqueeze.bat`**.
4. A black window appears. Leave it open, it is doing the work.
5. Your browser opens at VidSqueeze.

If Windows says Python is missing, VidSqueeze offers to download a private copy,
about 11 MB, into its own folder. Say yes. It needs no administrator rights.

If Windows SmartScreen warns about an unrecognised app, choose **More info**,
then **Run anyway**. That happens because the file is not code-signed, which
costs money each year.

---

## Getting started on macOS

These are the exact steps, in order.

### 1. Get the folder

Open **Terminal** (press `Command` + `Space`, type `Terminal`, press Return),
then paste this and press Return:

```
cd ~/Documents
git clone https://github.com/pxspaces/vidsqueeze.git VidSqueeze
```

If `git` is not installed, macOS offers to install the developer tools. Accept,
wait, then run the command again.

**No Terminal, no git?** Download the ZIP from the repository page instead,
double-click it in Finder, and drag the unpacked **VidSqueeze** folder into
**Documents**.

### 2. Let macOS run it

macOS blocks programs downloaded from the internet until you say otherwise. Do
this once:

- In Finder, open **Documents** then **VidSqueeze**.
- **Right-click** (or hold `Control` and click) **`Start VidSqueeze.command`**.
- Choose **Open** from the menu.
- A warning appears. Click **Open** again.

You must use right-click then Open the first time. Double-clicking gives you a
warning with no way past it. After this once, double-clicking works forever.

### 3. If double-clicking does nothing at all

The file lost its permission to run, which happens with some ZIP downloads. In
Terminal:

```
cd ~/Documents/VidSqueeze
chmod +x "Start VidSqueeze.command"
```

Then try step 2 again.

### 4. If it says Python is missing

macOS ships without Python until the developer tools are installed. In Terminal:

```
xcode-select --install
```

Accept the installer, wait for it to finish, then start VidSqueeze again.
VidSqueeze offers to do this for you as well.

### 5. First run

A Terminal window opens and your default browser opens at VidSqueeze. If ffmpeg
is not on your Mac, press **Download and continue**, wait about a minute, and
you are ready.

**Leave the Terminal window open** while you work. Closing it stops VidSqueeze.
Press **Quit** in the browser, or `Control` + `C` in Terminal, when finished.

### Making it easier to start

Drag `Start VidSqueeze.command` onto your Dock, or right-click it in Finder and
choose **Make Alias**, then move the alias to your desktop. Do not move the
original out of the folder.

---

## Getting started on Linux

1. Get the folder:
   ```
   cd ~/Documents
   git clone https://github.com/pxspaces/vidsqueeze.git VidSqueeze
   ```
2. Start it:
   ```
   cd VidSqueeze
   ./start-vidsqueeze.sh
   ```
   Or double-click `start-vidsqueeze.sh` in your file manager and choose
   **Run in Terminal**.
3. To add it to your applications menu, once:
   ```
   ./create-desktop-shortcut.sh
   ```

Python is almost always already installed. If not, the launcher names the
command for your distribution.

---

## The first question

The first time it opens, VidSqueeze asks what you work with: **Anything**,
**Video**, **Audio** or **Photos**. This only decides which settings you are
shown, so nothing is hidden permanently. Pick **Anything** if you are not sure.

It remembers your answer and never asks again. The same choice sits in the
header as a row of buttons, so you can change it whenever you like.

Adding files always overrides it. Drop a photograph in while set to Video and
the picture settings appear regardless.

---

## Your first conversion

1. **Add something.** Press **Choose files or a folder** in the Sources pane.
   Navigate to your videos or photos and choose them:

   - tick them one at a time, or
   - click one, then **shift-click** another to take everything between the two,
     which works in either direction, or
   - tick **Select all**, or
   - press **Use this folder** to take the whole folder.

   If you set your media type to Photos, only pictures are listed, so you are
   not picking your way past videos. The same goes for Video and Audio. Choose
   **Anything** in the header to see everything.

2. **Pick what you want.** In the middle, under Settings, choose a preset. If
   you are unsure, **Balanced** for video and **Photo for the web** for
   photographs are the right answers.

   The choices change depending on what you added. Photographs do not offer
   video codecs.

3. **Try it first, optionally.** Press **Test a short sample** to convert about
   eight seconds and see what the whole file would come to. Or **Try several
   settings** to compare two or three at once and pick the winner. This is worth
   doing before a long batch.

4. **Press Squeeze.** Progress shows on each file. Finished files appear in
   Results on the right.

5. **Check the result.** Click a finished file in Results. The Compare tab shows
   the original and the result behind a divider you can drag, with exact sizes.
   If you want to watch them properly, switch to Play, or press **Open result**
   to open it in your usual player.

6. **Find your files.** They are in the `output` folder inside VidSqueeze. Press
   **Folder** at the top of the Results pane to open it.

---

## Trimming a video

1. Click a video in Sources. The **Preview** tab opens.
2. Under Trim, a strip of thumbnails shows the video across its length.
3. Drag **Start** and **End**. The readout shows what you are keeping.
4. Press **Use these trim points**.
5. Press **Squeeze**.

Trim points apply to every file in the batch, so trim one at a time unless they
all need the same cut.

---

## Watching a folder

Useful for a folder your camera or phone dumps files into.

1. Open the **Watch** tab.
2. Press **Choose** and pick the folder.
3. Press **Start watching**.

New files appear in Sources as they arrive. VidSqueeze waits until a file has
finished copying before adding it.

**It never converts anything on its own.** You always press Squeeze yourself.

---

## Deleting originals safely

There is a setting to delete each original after converting. It is off, and it
should stay off unless you are certain.

When it is on, an original is deleted only after the new file has been checked:
it must open, contain the right streams, be the expected length, and be smaller.
If any check fails the original is kept and you are told why.

This cannot be undone. There is no recycle bin.

---

## When something goes wrong

**A file failed.** Open the `logs` folder inside VidSqueeze. Every failure
records the exact command and what went wrong.

**A photo will not open.** iPhone photos are HEIC, which needs a recent ffmpeg.
VidSqueeze offers to download a newer one into its own folder. Press the button.

**My camera RAW files convert but look low resolution.** No RAW decoder is
installed, so VidSqueeze used the preview picture your camera stored inside the
file. It tells you when this happens, and names the command to fix it. Install
that and convert again for full quality.

**My photographs look flatter and greyer than the original.** Fixed in 1.7.0. A
RAW file is what the sensor recorded, not a finished photograph, and VidSqueeze
was leaving the decision about brightness and colour to the decoder, which errs
heavily towards faithful rather than attractive. Update, and they will come out
close to how your camera renders them.

If you preferred the old flat rendering, because you edit your photographs
afterwards, set **Camera RAW should look** to **Flat, for editing** under Advanced
image settings.

**My PNG is not as good as I expected.** Two settings to check, both fixed in
1.7.0 but worth knowing. The quality dial decides colour depth for PNG, so set it
to 90 or more for all 16 bits; it used to be hidden for PNG entirely. And the
longest side used to stay at 2560, so a big photograph came out at under half its
size; choosing PNG now clears that for you.

**My converted picture looks dark or muddy.** It should not. This was a genuine
fault in versions before 1.5.0, where photographs were developed with the wrong
tone curve and came out darker than they should have been. Update, and convert
again.

**I need my computer back part way through a big batch.** Press **Pause**, next to
Stop. The file being worked on finishes, then it waits. Press **Carry on** when you
are ready. Nothing is lost and the time estimate does not punish you for the break.

**It says some files came out larger.** That is the honest report rather than a
fault. It happens when the output format does not compress, which usually means
PNG or TIFF was chosen for photographs. Convert those to JPEG, WebP or AVIF
instead. From 1.8.0 VidSqueeze warns about this before the batch starts.

**My portrait photographs came out the wrong size, or bigger.** Fixed in 1.6.0.
Phones and cameras store a portrait photograph as a landscape picture plus a note
saying which way up it goes, and VidSqueeze was reading the shape and not the
note, so it shrank the wrong side. Update and convert again.

**The date on my converted photographs is today, not when I took them.** Fixed in
1.6.0. The date the photograph was taken is now kept, and becomes the date on the
file, so a shoot stays in order. Camera and lens details are kept too, in JPEG.
If you would rather they were not, tick **Strip dates and camera information**.

**Updates says I am up to date but I know there is a newer version.** Press
**Check again** in the Updates window, which ignores the saved answer from the
last few hours. Versions before 1.6.0 could also report the wrong version number
for themselves, so if you are on 1.5.0 or earlier and the button will not offer
anything, update by pulling with git, or download the newest copy from the
project page.

**The PNG came out bigger than the original.** From 1.8.0 VidSqueeze warns about
this in the settings before you start, rather than mentioning it afterwards.
PNG never throws anything away,
so it is often larger than a camera file, which does. If you want a smaller
file, choose WebP or AVIF. If you want PNG but not an enormous one, keep the
quality below 90: above that VidSqueeze keeps 16 bits of colour per channel,
which roughly triples the size.

**How do I update?** Press **Updates** in the header, then **Update now**. That
is all: no terminal, no git, no downloading a ZIP again. Your converted files,
settings and history are left alone, and the previous version is kept in case
you want it back. Restart VidSqueeze afterwards.

The same button updates ffmpeg separately, if a newer one exists. Nothing is
checked unless you press Updates.

**Colours look washed out and grey.** The source is HDR. Make sure **Convert
HDR to standard range** is ticked in Advanced settings.

**The result is bigger than the original.** It was already efficiently
compressed. Try a lower quality level or a smaller size.

**It is taking a long time.** Video encoding is slow. Use a faster Encoding
speed, reduce the resolution, or turn on graphics card acceleration under Speed
if your machine offers it. H.265 is about three times slower than H.264.

**The browser did not open.** The address is printed in the window VidSqueeze
opened. Copy it into your browser. It only listens on your own computer, and the
address contains a key that changes every time.

**It opened in the wrong browser.** Start it with the one you want, once:
```
python3 -m vidsqueeze --browser firefox
```

**Nothing works and I want to start again.** Delete the `bin`, `runtime` and
`.cache` folders inside VidSqueeze and start it again. Your converted files in
`output` are not touched.

---

## Per-media guides

- [Working with video](docs/GUIDE-VIDEO.md)
- [Working with photos and images](docs/GUIDE-IMAGES.md)
- [Working with audio](docs/GUIDE-AUDIO.md)
