# Working with video

---

## Which preset?

| You want to                         | Use                        |
| ----------------------------------- | -------------------------- |
| Make files smaller, keep them good  | **Balanced**               |
| Keep footage you will edit later    | **High quality**           |
| Store master copies for years       | **Archive**                |
| Free up as much space as possible   | **Shrink to 1080p**        |
| Send it on WhatsApp                 | **WhatsApp (16 MB)**       |
| Attach it to an email               | **Email (25 MB)**          |
| Post it to Reels, Shorts or TikTok  | **Short-form video**       |
| Upload it to YouTube                | **YouTube upload**         |
| Put it on a website                 | **Website**                |
| Fix something that will not play    | **Plays anywhere**         |

**Balanced** is the right answer for most people, most of the time.

---

## Understanding the trade

Three things pull against each other: quality, file size and time. You choose
two.

- **H.265** makes much smaller files than H.264 and takes about three times as
  long. It plays on everything modern, but some older televisions and editing
  programs refuse it.
- **H.264** is faster and plays absolutely everywhere, at roughly twice the size.
- **AV1** is smaller still and slower again. Good for storage, not for sharing.

**Encoding speed** changes how hard the encoder works to find savings. Slower
settings produce smaller files at the same quality. Going from veryfast to
medium costs about 40 percent more time for maybe 10 percent smaller files.

---

## The single biggest saving

**Reducing the resolution.** A 4K video scaled to 1080p is typically a quarter
of the size before any other setting is touched. If nobody is going to watch it
on a 4K screen, this is free money.

Videos are never enlarged, so choosing 1080p leaves a 720p clip alone.

---

## Fitting a size limit

Choose **Fit a file size** and give a number, or use a preset that already has
one. HalveIt works out the bitrate needed and uses two passes, so the result
lands close to, and under, the limit.

It is a ceiling, not a quota. A video that already fits is not inflated to fill
the budget.

If the target is impossible, for instance ten minutes into 10 MB, HalveIt
says so rather than producing something unwatchable.

---

## HDR footage

Modern phones and cameras record HDR. Converting it naively gives washed-out
grey video, because HDR and standard video are different colour systems.

**Convert HDR to standard range** is on by default and handles it properly.
Leave it on unless you know you want to keep HDR.

---

## Trimming

Select the video, open **Preview**, drag the Start and End handles under the
filmstrip, press **Use these trim points**, then **Compress**.

Trim applies to the whole batch, so trim one file at a time unless every file
needs the same cut.

---

## Graphics card acceleration

Under **Speed**. Only offered if HalveIt proved your hardware works by
actually running a short encode, because plenty of hardware claims encoders it
cannot use.

It is roughly twice as fast and produces noticeably larger files at the same
setting. Worth it for a long batch you need finished today, not for archiving.

---

## Batches

Add a whole folder and every video inside is queued. **Encode two files at
once**, under Speed, helps when the files are short, by recovering the time each
one spends starting and finishing.
