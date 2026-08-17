# Working with photos and images

VidSqueeze converts and shrinks still images as well as video. Photographs from
a phone or camera are usually far larger than they need to be for sending,
publishing or storing.

---

## Which format should I choose?

| You want to                        | Use          | Why                                                   |
| ---------------------------------- | ------------ | ----------------------------------------------------- |
| Put photos on a website            | **WebP**     | About a third smaller than JPEG, and every current browser reads it |
| Send photos to someone             | **JPEG**     | Opens on absolutely everything, including old software |
| Get the smallest possible files    | **AVIF**     | Often half the size of JPEG, needs a recent viewer      |
| Keep a logo, screenshot or diagram | **PNG**      | Lossless and keeps transparency                        |
| Keep a photograph perfectly        | **Archive quality** | Lossless WebP, far smaller than PNG or TIFF     |

The presets already choose sensibly. **Photo for the web** is the right answer
if you are unsure.

---

## Step by step

1. Add your photographs. You can add a whole folder.
2. The settings change to image settings automatically. Video codecs disappear,
   because they are meaningless here.
3. Pick a preset, or open **Advanced image settings** to choose the format,
   quality and maximum size yourself.
4. Press **Squeeze**.
5. Click a result to compare it against the original, wiping between the two.

---

## Quality

The quality slider runs 1 to 100 and is translated onto whatever scale the
chosen format actually uses, so 80 means roughly the same thing everywhere.

- **90 and above**: no visible difference, larger files, and full colour
- **75 to 85**: the sensible range for photographs, and the default
- **60 to 75**: acceptable for previews and thumbnails
- **below 60**: visible blotches, especially in skies and skin

**90 is a real threshold, not just a number.** Below it, VidSqueeze stores
colour at half width, which is what almost every photograph on the internet
does and is very hard to see. At 90 and above it stops doing that and keeps
colour in full. If you are going to edit the picture afterwards, or it has fine
coloured detail such as text or a logo on a strong background, use 90 or more.

For photographs from a camera, 90 and above also keeps 16 bits of colour per
channel instead of 8. That is a large difference in file size and no difference
at all to the naked eye, but it is what lets you lift shadows later without the
sky turning into bands.

PNG, TIFF and BMP are always lossless, so there is nothing to lose by squeezing
them. For those the quality setting only decides how much colour depth is kept:
below 90 they are written at 8 bits per channel, which is what screens show and
what every program reads. This is why a photograph converted to PNG is around
36 MB at the default and around 120 MB at 95.

---

## Longest side

The most effective saving available. A 48-megapixel phone photograph is around
8000 pixels wide, and no screen shows more than about 3840. Reducing the longest
side to 2560 typically removes most of the file size without any visible loss.

Images are **never enlarged**, so setting 2560 on a small image leaves it alone.

---

## Transparency

Logos, screenshots and diagrams often have transparent backgrounds.

- **PNG, WebP, JPEG XL and TIFF** keep transparency.
- **JPEG, AVIF and BMP** cannot store it.

When converting to a format that cannot keep it, VidSqueeze places the image on
a background colour of your choosing, white by default, and tells you it did.
Without that, transparent areas would come out black.

If transparency matters, use WebP: it keeps it and is still much smaller than
PNG.

---

## Camera RAW (CR2, NEF, ARW and the rest)

VidSqueeze converts RAW files from Canon, Nikon, Sony, Fujifilm, Olympus,
Panasonic, Pentax, Leica, Hasselblad, Phase One, Sigma and others. Add them like
any other photograph and choose the format you want.

There is one thing worth knowing. ffmpeg, which does everything else in
VidSqueeze, cannot read camera RAW at all. A separate decoder is needed, and
VidSqueeze uses the best one it finds installed: darktable, RawTherapee, LibRaw,
dcraw or ImageMagick, in that order.

**If none is installed**, VidSqueeze falls back to the preview picture your
camera stored inside the RAW file. This always works and needs nothing, but it
is the camera's own rendering and is often much smaller than full resolution.
VidSqueeze tells you when it has done this, so you are never misled about what
you got.

To get full quality, install one decoder. VidSqueeze shows the right command for
your computer, but for reference:

```
winget install ImageMagick.ImageMagick    # Windows
brew install libraw                       # macOS
sudo apt install libraw-bin               # Linux with apt
```

Converted RAW files are named after the original, so `DSC_0431.CR2` becomes
`DSC_0431.jpg`.

A note on expectations: this is a conversion, not a RAW editor. VidSqueeze
develops the file with sensible defaults. Recovering blown highlights or
changing white balance needs a proper RAW editor such as darktable or
RawTherapee, both of which are free.

### Why it does not look identical to the camera's own JPEG

It should look correct, and it should not look dark or muddy. If it does, that
is a fault worth reporting. But it will not be pixel for pixel the same as the
JPEG your camera produces, and that is deliberate.

Your camera applies its own look to the JPEGs it makes: extra contrast, a little
more colour, and its manufacturer's idea of how skin should appear. That look is
a choice, not the photograph. A RAW file is what the sensor actually recorded,
and VidSqueeze develops it plainly, without adding a look of its own.

The practical difference is that a VidSqueeze conversion usually appears very
slightly flatter than the camera's JPEG, and holds more detail in the brightest
and darkest parts. That is the better starting point if you plan to edit it. If
you would rather have the camera's look, use the JPEG your camera already made,
or develop the RAW in darktable or RawTherapee where you can pick a style.

---

## iPhone photos (HEIC)

iPhones save photographs as HEIC. Reading it needs a recent ffmpeg. If yours is
older, VidSqueeze tells you and offers a one-click download of a newer build
into its own folder. Nothing is installed elsewhere on your Mac or PC.

---

## Comparing results

Select a converted photograph in Results. The Compare tab puts the original and
the result behind a divider you drag, so you can see exactly what a quality
setting cost you. The facts table underneath shows dimensions, format and
whether transparency survived.
