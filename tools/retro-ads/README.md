# Retro-ad art tools (not part of the add-on zip)

Everything the retro ads ship with is made by these scripts; no outside art,
photos or samples. Run from the repository root.

| Script | Makes | Needs |
|---|---|---|
| `make_bg.py OUTDIR` | The blank card backgrounds (`bg_*.png`) and previews with sample text | `rsvg-convert`, Pillow |
| `make_jingle.py OUTDIR [preset...]` | The jingles as OGG Vorbis, about -16 LUFS | numpy, ffmpeg with libvorbis |
| `make_glyphs.py [FONTDIR]` | The letter pictures in `resources/skins/Default/media/retroads` (DejaVu fonts) | Pillow |
| `make_station_layers.py [OUT_DIR]` | The station ID card's layers in `resources/skins/Default/media/station` (`sid_base.jpg`, `sid_rays.png`, `sid_top.png`, `sid_glint.png`): `make_bg.py`'s section 9 split so the rays can turn and a glint can cross the band | `rsvg-convert`, Pillow |
| `make_upnext_layers.py [OUT_DIR]` | The Up next card's layers in `resources/skins/Default/media/upnext` (`un_base.jpg`, `un_stripes.png`, `un_top.png`, `un_glint.png`, `un_mask.png`): `make_bg.py`'s section 10 split so the stripes can drift and a glint can cross the tab | `rsvg-convert`, Pillow |
| `make_squeeze_layers.py [OUT_DIR]` | The squeezed-credits layers in `resources/skins/Default/media/squeeze` (`sq_base.jpg` behind the video window, `sq_panel.png` that slides in): `make_bg.py`'s section 11 | `rsvg-convert`, Pillow |
| `make_skin.py` | The retro-ad group (letter slots, station ID and Up next layers, the countdown's slots) in `script-cablebox42-tv.xml` | - |
| `to_wav.py OGG_DIR [OUT_DIR]` | The shipped mono WAV jingles from the stereo OGGs, loudness matched | ffmpeg |
| `check_ads.py [ads.json]` | Checks the ad data: phone numbers 555-0100..0199, known fields, kids' rules, every text in strings.po | - |

**Shipping:** backgrounds go to `resources/media/ads/` as 1920x1080 JPG. Jingles go
to `resources/media/jingles/` as **mono WAV**, 22.05 kHz 16-bit (the Kodi repository
checker refuses `.ogg`; mono halves the size), at the stereo version's loudness:

    python3 tools/retro-ads/to_wav.py OUTDIR_OF_make_jingle

`to_wav.py` downmixes (0.5 L + 0.5 R), adds back the loudness the downmix lost (about
3 dB, EBU R128 integrated, measured on the WAV; about -16 LUFS each), and puts a peak
limiter (ceiling -1.5 dB) only on a jingle whose peaks would otherwise pass -1 dBTP
(the kids' jingle, by 0.2 dB). It prints each jingle's loudness and peak.

**Jingle rules:** every jingle ends in its own 0.4 s fade. The add-on never cuts one
short and never touches Kodi's volume: a card lasts its jingle plus 0.45 s
(`ads.START`, for Kodi to start the sound), rounded up to whole seconds, so a new or
longer jingle makes its cards longer by itself. A slot too short for a card gets a
promo or the station ID; tuned in part-way through a card, it stays up silent.
`.claude/tools/retro_check.py` checks every planned card is long enough.

**Station ID card:** `bg_9_station_id.jpg` itself is not shipped. The card is drawn
from the four layers of `make_station_layers.py` (at rest they match bg_9): the rays
(48, every other one filled, so the pattern repeats every 15 degrees) turn 15 degrees
in 40 s and start again, and the glint slides along the band once every 8 s, fading
in and out so its restart never shows. Rebuild the layers whenever section 9 of
`make_bg.py` changes.

The previews and `contact.png` are not shipped.
