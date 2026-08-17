# Working with audio

VidSqueeze extracts audio from video, and converts audio files.

---

## Getting the sound out of a video

1. Add the video.
2. Choose **Extract audio as MP3** or **Extract audio as M4A**.
3. Press **Squeeze**.

The video is discarded and you are left with an audio file, typically a
fiftieth of the size.

**MP3** plays on everything, including old car stereos and cheap players.
**M4A** sounds better at the same size and plays natively on Apple devices.
Choose MP3 if you are not sure where it is going.

---

## Converting audio files

Add audio files and the same presets apply. VidSqueeze notices there is no video
and does not try to invent one.

---

## Bitrate

| Bitrate      | Suits                                       |
| ------------ | ------------------------------------------- |
| 64 kbps      | Speech, podcasts, voice notes               |
| 96 to 128    | Background music, casual listening          |
| 192 kbps     | Music you actually care about, the default for extraction |
| 256 to 320   | As good as these formats get                |

Above 320 there is nothing to gain: the format itself becomes the limit.

For anything you intend to keep as a master, use **FLAC** in an MKV container
instead, which is lossless.

---

## Removing sound from a video

Set **Audio** to **Remove audio** in Advanced settings. Useful for silent
background clips on websites, where the audio track is wasted bytes.

---

## Keeping audio untouched

Set **Audio** to **Keep as-is**. The sound is copied across without being
re-encoded, so nothing is lost and it takes no time. Sensible when you are only
changing the video and the audio is already fine.

---

## Comparing

Audio results open in the Compare tab with both files as players. If your
browser can play both, **Play both together** starts them in step so you can
hear the difference. If it can only play one, that one still plays and the other
opens in your usual program.
