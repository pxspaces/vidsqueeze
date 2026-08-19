# HalveIt user guide

Step by step, for people who have never touched a video setting. If you can
double-click a file, you can use this.

Living document, last updated for version 1.13.0.

**Jump to:** [Windows](#getting-started-on-windows) &middot;
[macOS](#getting-started-on-macos) &middot; [Linux](#getting-started-on-linux) &middot;
[Your first conversion](#your-first-conversion) &middot;
[Audio](docs/GUIDE-AUDIO.md) &middot; [Problems](#when-something-goes-wrong)

---

## Before you start: where to put it

Put the HalveIt folder somewhere permanent:

| System  | Where                                  |
| ------- | -------------------------------------- |
| Windows | `C:\Users\<you>\Documents\HalveIt`   |
| macOS   | `/Users/<you>/Documents/HalveIt`     |
| Linux   | `/home/<you>/Documents/HalveIt`      |

Two things matter:

1. **Keep the folder together.** The launcher only works from inside it. Move
   the whole folder, and make a shortcut or alias if you want it on your desktop.
2. **Do not leave it in Downloads.** HalveIt keeps the tools it downloads,
   and by default your converted files, inside its own folder. If you empty that
   location periodically you will lose both.

Nothing is installed anywhere else, and no administrator password is needed.
Deleting the folder removes HalveIt completely.

---

## Getting started on Windows

1. Download the ZIP from the repository page and open it.
2. Drag the **HalveIt** folder into your **Documents** folder.
3. Open it and double-click **`Start HalveIt.bat`**.
4. A black window appears. Leave it open, it is doing the work.
5. Your browser opens at HalveIt.

If Windows says Python is missing, HalveIt offers to download a private copy,
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
git clone https://github.com/pxspaces/halveit.git HalveIt
```

If `git` is not installed, macOS offers to install the developer tools. Accept,
wait, then run the command again.

**No Terminal, no git?** Download the ZIP from the repository page instead,
double-click it in Finder, and drag the unpacked **HalveIt** folder into
**Documents**.

### 2. Let macOS run it

macOS blocks programs downloaded from the internet until you say otherwise. Do
this once:

- In Finder, open **Documents** then **HalveIt**.
- **Right-click** (or hold `Control` and click) **`Start HalveIt.command`**.
- Choose **Open** from the menu.
- A warning appears. Click **Open** again.

You must use right-click then Open the first time. Double-clicking gives you a
warning with no way past it. After this once, double-clicking works forever.

### 3. If double-clicking does nothing at all

The file lost its permission to run, which happens with some ZIP downloads. In
Terminal:

```
cd ~/Documents/HalveIt
chmod +x "Start HalveIt.command"
```

Then try step 2 again.

### 4. If it says Python is missing

macOS ships without Python until the developer tools are installed. In Terminal:

```
xcode-select --install
```

Accept the installer, wait for it to finish, then start HalveIt again.
HalveIt offers to do this for you as well.

### 5. First run

A Terminal window opens and your default browser opens at HalveIt. If ffmpeg
is not on your Mac, press **Download and continue**, wait about a minute, and
you are ready.

**Leave the Terminal window open** while you work. Closing it stops HalveIt.
Press **Quit** in the browser, or `Control` + `C` in Terminal, when finished.

### Making it easier to start

Drag `Start HalveIt.command` onto your Dock, or right-click it in Finder and
choose **Make Alias**, then move the alias to your desktop. Do not move the
original out of the folder.

---

## Getting started on Linux

1. Get the folder:
   ```
   cd ~/Documents
   git clone https://github.com/pxspaces/halveit.git HalveIt
   ```
2. Start it:
   ```
   cd HalveIt
   ./start-halveit.sh
   ```
   Or double-click `start-halveit.sh` in your file manager and choose
   **Run in Terminal**.
3. To add it to your applications menu, once:
   ```
   ./create-desktop-shortcut.sh
   ```

Python is almost always already installed. If not, the launcher names the
command for your distribution.

---

## The first question

The first time it opens, HalveIt asks what you work with: **Anything**,
**Video**, **Audio** or **Photos**. This only decides which settings you are
shown, so nothing is hidden permanently. Pick **Anything** if you are not sure.

It remembers your answer and never asks again. The same choice sits in the
header as a row of buttons, so you can change it whenever you like.


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
   you are unsure, **Balanced** is the right answer.

   The choices change depending on what you added.

3. **Try it first, optionally.** Press **Test a short sample** to convert about
   eight seconds and see what the whole file would come to. Or **Try several
   settings** to compare two or three at once and pick the winner. This is worth
   doing before a long batch.

4. **Press Compress.** Progress shows on each file. Finished files appear in
   Results on the right.

5. **Check the result.** Click a finished file in Results. The Compare tab shows
   the original and the result behind a divider you can drag, with exact sizes.
   If you want to watch them properly, switch to Play, or press **Open result**
   to open it in your usual player.

6. **Find your files.** They are in the `output` folder inside HalveIt. Press
   **Folder** at the top of the Results pane to open it.

---

## Trimming a video

1. Click a video in Sources. The **Preview** tab opens.
2. Under Trim, a strip of thumbnails shows the video across its length.
3. Drag **Start** and **End**. The readout shows what you are keeping.
4. Press **Use these trim points**.
5. Press **Compress**.

Trim points apply to every file in the batch, so trim one at a time unless they
all need the same cut.

---

## Watching a folder

Useful for a folder your camera or phone dumps files into.

1. Open the **Watch** tab.
2. Press **Choose** and pick the folder.
3. Press **Start watching**.

New files appear in Sources as they arrive. HalveIt waits until a file has
finished copying before adding it.

**It never converts anything on its own.** You always press Compress yourself.

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

**A file failed.** Open the `logs` folder inside HalveIt. Every failure
records the exact command and what went wrong.


**I need my computer back part way through a big batch.** Press **Pause**, next to
Stop. The file being worked on finishes, then it waits. Press **Carry on** when you
are ready. Nothing is lost and the time estimate does not punish you for the break.

**It says some files came out larger.** That is the honest report rather than a
fault. It happens when the output format does not compress, which usually means
the chosen output format does not compress.


**Updates says I am up to date but I know there is a newer version.** Press
**Check again** in the Updates window, which ignores the saved answer from the
last few hours. Versions before 1.6.0 could also report the wrong version number
for themselves, so if you are on 1.5.0 or earlier and the button will not offer
anything, update by pulling with git, or download the newest copy from the
project page.


**What is in the new version?** Press **Updates** in the header. When there is one
to take, the window lists what was fixed and what was added, so you can decide
before installing rather than afterwards.

**How do I update?** Press **Updates** in the header, then **Update now**. From
1.13.0 HalveIt restarts itself and opens in a new tab when it is done, so there
is nothing to do by hand. The tab you pressed the button in stops working at that
point and can be closed. That
is all: no terminal, no git, no downloading a ZIP again. Your converted files,
settings and history are left alone, and the previous version is kept in case
you want it back. Restart HalveIt afterwards.

The same button updates ffmpeg separately, if a newer one exists. Nothing is
checked unless you press Updates.

**Colours look washed out and grey.** The source is HDR. Make sure **Convert
HDR to standard range** is ticked in Advanced settings.

**The result is bigger than the original.** It was already efficiently
compressed. Try a lower quality level or a smaller size.

**It is taking a long time.** Video encoding is slow. Use a faster Encoding
speed, reduce the resolution, or turn on graphics card acceleration under Speed
if your machine offers it. H.265 is about three times slower than H.264.

**The browser did not open.** The address is printed in the window HalveIt
opened. Copy it into your browser. It only listens on your own computer, and the
address contains a key that changes every time.

**It opened in the wrong browser.** Start it with the one you want, once:
```
python3 -m halveit --browser firefox
```

**Nothing works and I want to start again.** Delete the `bin`, `runtime` and
`.cache` folders inside HalveIt and start it again. Your converted files in
`output` are not touched.

---

## Per-media guides

- [Working with video](docs/GUIDE-VIDEO.md)
- [Working with photos and images](docs/GUIDE-IMAGES.md)
- [Working with audio](docs/GUIDE-AUDIO.md)
