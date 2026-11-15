# CableBox 42 — guide for Claude Code sessions

CableBox 42 (`script.cablebox42`) is a Kodi 21 (Omega) program add-on that turns the
user's own Kodi library into live retro cable TV: real-clock channels, commercial
breaks, bumps, station IDs, a guide channel, a weather channel, a weekly planner,
CRT effects and turn-on/turn-off effects. Everything plays through Kodi's own player.
Inspired by FieldStation42, but a separate Kodi-native implementation.
License MPL-2.0. Maintainer: Seadog McGrog (GitHub `SeadogMcGrog`).

The maintainer's main test box is **CoreELEC 21.3 on an ODROID N2** (HDMI, 7.1 PCM
output `surround71`, passthrough on for AC3/E-AC3/DTS/TrueHD/DTS-HD, refresh rate
"On start/stop"). Always think about CoreELEC and other low-power boxes.

## Where things are

The repository root **is** the add-on folder.

| Path | What |
|---|---|
| `default.py` → `resources/lib/main.py` | Script entry (main menu, `RunScript(script.cablebox42,watch,7)` etc.) |
| `service.py` → `resources/lib/service_main.py` | Background service |
| `resources/lib/tv.py` | The TV window: playback, channel changes, banner, static, turn-on/off, `GuiSounds` |
| `resources/lib/scheduler.py` | Real-time rolling schedules, slot filling, breaks, pinned shows |
| `resources/lib/manager.py` | Channel manager, lineup wizard, menus, Help text, Branding & clips, folder tools |
| `resources/lib/channels.py` | Channel model and `channels.json` persistence, automatic lineup |
| `resources/lib/assign.py` | Home-channel assignment and scoring (`compute(..., explain=True)` for the Finder) |
| `resources/lib/finder.py` | "Shows without a good channel" |
| `resources/lib/stations.py` | Built-in stations, branding by time of day, station folders |
| `resources/lib/captions.py` | Closed captions |
| `resources/lib/library.py` | Kodi library queries (JSON-RPC); music videos for Boombox (library + folder files, background measuring into `musicvideos.json`) |
| `resources/lib/musicvideos.py` | Boombox, no Kodi imports: "Artist - Title (Year)" names, caption lines (library > file tags > name), frame-rate groups, rotation |
| `.claude/make-promo-art.py` | Rebuilds the 90s promo art (`media/promo90s/`: Bebas Neue letter pictures, bands, shapes). Not shipped |
| `resources/lib/ads.py` | Retro ads in house breaks: data (`resources/ads/ads.json`), picking (time of day, season, Ad flavour, 2-hour no-repeat), card layout lettered with DejaVu letter pictures (`media/retroads`) into skin slots 3000-3399 / 3400-3539 (countdown 3600-3615); placed by `scheduler._retro_block`, shown by `tv.start_retro`; `RunScript(script.cablebox42,preview_ad,P01)` shows one. Jingles: mono 22.05 kHz WAV (`tools/retro-ads/to_wav.py`), never cut short: a card lasts its jingle + 0.45 s, late tune-in = silent card. Video-themed ads (`video` cards, ads with `"theme": "video"`): one a break, not in two breaks in a row (`scheduler._prev_break_video`; a back-to-back run is one break), at most 1 in 6 of a General channel's retro ads in 6 h (1 in 3 Movies, 1 in 4 others; `ads.video_ok`). Two retro ads a house break (4 Movies; `ads.per_break`), 3 in a back-to-back run (4 Movies; `ads.per_run`). A local spot's phone number is left off on kids' channels (`ads.card(e, kids=True)`; `check_ads.py`: no other number on a K ad). A programme-end gap over `GAP_SPLIT` (240 s) is a series of ~150 s breaks (`_house_fill`), each ending on a station ID card with `"sep": 1`; the walk-backs (`_retro_block`, `_prev_break_video`) stop there, and each such break gets up to `ads.per_gap_break` (10) in all, at most `GAP_PROMOS` (3) promos, each system ad once in the gap (`_run_so_far`). Gap variety when promos are named (`_resolve_promos` → `_gap_avoid`; on air `tv.promo_subject` → `gap_avoid`): the same target (show title, own or other channel) once in `GAP_PROMO_SPACING` (600 s) and at most `GAP_PROMO_MAX` (3) times a gap; nothing fresh → `_gap_filler`: a retro ad (`_gap_retro`: long gap, `per_gap_break`, 2-hour rule also for the ads it moves; the house break's ID card takes up the length difference) → a system ad the gap hasn't run → station ID (`pt` 0). Before off-air the next show after it (`_signon`) at most `OFFAIR_PROMOS` (2): the first slot that names it and the gap's last promo slot (`_signon_slot`). Every layout fills breaks through `_breaks(ads)` (house breaks where the channel runs them). Blocks carry `"cf"` (`planning_code()`): a refresh keeps the on-air block as an earlier build planned it. Schedule state `retro_stats` counts the planner's retro turns (placed / none / long / repeat) for retro_check. `ads.station_card` is the station ID card (`tv.station_id`, mode `station`, layers in `media/station`; `preview_ad,station:N`). `ads.upnext_card` is the end-of-show Up next card (`tv.up_next`, mode `upnext`, layers in `media/upnext`, countdown relettered each second by `tv.upnext_tick`; `preview_ad,upnext:N[:K]`). Chapter breaks: `probe.chapters` (MKV Chapters, MP4 Nero chpl) read by `library.ChapterReader` in the service's own thread (pace from measured read times: ~1/s to start, up to 5/s idle, backs off at once on a slow read, pauses on /proc/loadavg over 0.9 per CPU; TV on: planned episodes airing in the next 6 h first, at most 1/s, never within 4 s of the TV opening a file (home property `cablebox42.play_at`), the rest never from the playing share; paused while anything else plays or a tool runs; one summary log line a minute; Settings `chapters_status` shows X of Y; Check chapters' *Read now* = `chapters_read_all`; `Chapters.save` merges with the file; the main loop re-plans (`refresh_now`) when planned episodes got chapters, at most every 10 min) into `chapters.json`; `chapters.py` (no Kodi imports) gives act / dense / auto / none and the credits start; `scheduler._chapter_points` uses cached chapters only, `_credits_at` puts `"cr"` (file time) on an episode's last part. `chapter_shows.json`: per-show Always/Never (Check chapters). Squeezed credits: `tv.squeeze_tick` sets the window property `squeeze` when the playing file reaches the last part's `"cr"` (mode stays `video`); the skin draws `media/squeeze/sq_base.jpg` *behind* the video window (id 10), zooms the video window (Conditional zoom 58.33 % about 168,360 → 70,150 1120×630) and slides in the panel (`ads.squeeze_card`, letter slots, countdown in the clock slots); `tv.unsqueeze` on every new item and channel change; captions' full-screen player is left while squeezed (`fs_wanted`). No chapters (or not read yet): `_credits_at` squeezes the final 30 s of a TV episode of 15 min or more that plays to its natural end; `tv.squeeze_tick` never squeezes before an off-air block. `scheduler._skip_short` drops TV episodes under *Skip episodes shorter than* from automatic pools (not short-form series, unknown lengths, singles or pinned slots); skipped files go to `skipped.json` (*Tools → Check skipped episodes*) |
| `tools/retro-ads/` | Scripts that make the retro-ad backgrounds, jingles, letter pictures, station ID, Up next and squeeze layers (`make_station_layers.py`, `make_upnext_layers.py`, `make_squeeze_layers.py`) and skin slots; `check_ads.py` checks the ad data. Not shipped (build_zip/release zip exclude `tools/`) |
| `resources/lib/promos.py` | Schedule promos: artwork/plot/theme/Extras lookup (read-only); slots are placed in `scheduler._fill`, shown by `tv.start_promo` |
| Others | `planner.py`, `weather.py`, `progress.py`, `presets.py`, `seasons.py`, `probe.py`, `logos.py`, `widget.py`, `kodiutil.py` |
| `resources/language/resource.language.en_gb/strings.po` | All UI strings |
| `resources/settings.xml` | Add-on settings |
| `README.md` (reference), `HOWTO.md` (step-by-step guide), `changelog.txt` | User docs |
| `.github/` | Discussions/issue forms. Not shipped. |
| `.claude/` | This guide and the test-rig script. Not shipped. |

The maintainer keeps private notes and task briefs **outside the repo** in
`G:\CableBox42\briefs\` (next to this repo at `G:\CableBox42\script.cablebox42\`).
A task often starts as "implement `briefs\<name>.md`".

## House rules

- Kodi 21 / Python 3 only; `xbmc`, `xbmcgui`, `xbmcaddon`, `xbmcvfs`, JSON-RPC.
- Remote-friendly: Kodi dialogs (`select` with `useDetails`, `yesno`, `textviewer`),
  arrows/OK/Back. No mouse-only UI.
- Keep the live-TV feel: real clock, leftover time becomes breaks, series advance in
  order, no show on two channels at once by default.
- Small, focused changes; keep the existing structure; no new top-level files unless needed.
- Manual assignments and exclusions always win over automatic ones. Never break
  existing `channels.json` or schedules.
- Every user-visible string goes through `_("...")` **and** must exist in `strings.po`
  (exact text). New ids continue after the highest id in the file (ids above 32999
  are fine). Remove entries nothing uses any more.
- Never delete or overwrite the user's own files (station folders, clips, logos).
  Folder renames refuse when the target exists.
- Every screen is one of five kinds, and each kind always works the same way
  (helpers in `manager.py`: `done_select`, `ask`, `confirm`, `confirm_remove`):
  - **Menu** (you come back to it after each change): changes save as you go;
    bottom row **Done** (= Back).
  - **Step-by-step** (several screens that create one thing: Build my lineup,
    Add a channel, Pin a show, Add a time block, Add off-air hours): Back on any
    step cancels the whole thing, nothing saved. Ends with an OK / Cancel screen
    when it replaces something or has more than ~4 steps; otherwise a short
    notification says what was added.
  - **Question**: buttons say what they do ("Rename folder" / "Leave it"), never
    plain Yes/No. Back = Cancel, never an answer that does something; three-way
    questions use `yesnocustom` (Back returns -1) via `ask(..., cancel=...)`.
  - **Remove / replace**: always asks first, buttons *Cancel* / *Remove* (or
    Delete, Replace, Clear) via `confirm_remove`. Lists of choices get a Cancel row.
  - **Info** (textviewer): never a dead end in the middle of a flow; if something
    can be done next, offer it after the viewer closes it.
- Docs: user-facing wording is plain and short; `README.md` = reference,
  `HOWTO.md` = task walkthroughs. Update both when menus or behaviour change.

## Hard-won lessons (do not regress)

- **Never change an audio setting during playback.** In Kodi 21 changing
  `audiooutput.guisoundmode` (and the other settings in `ActiveAESettings.cpp`)
  rebuilds the whole audio output. Toggling it on every channel change made sound
  sputter and wedged CoreELEC HDMI audio ("CAESinkALSA::Initialize - Unable to open
  the requested channel layout", every 0.5 s until Kodi restarts). Since 1.1.1
  `GuiSounds` sets *Always* once at TV start and restores the user's value at TV
  stop (crash recovery: `gui_sounds_orig` in state.json). Kodi's own button clicks are
  therefore audible while the TV is on — documented, accepted.
- **Never change Kodi's volume from the add-on** (it shows the volume bar, changes the
  viewer's own volume, and stays wrong if anything fails). No `Application.SetVolume` /
  `SetMute` and no volume-step fades: promo themes play at the file's own level and are
  cut with the card; the built-in tune has its level and fade baked into the file.
  Kodi already handles the remote's Volume/Mute keys while CableBox's windows are open
  (verified in Kodi 21.3: the window receives the action *and* Kodi changes the volume),
  so passing them on as well made each press count twice and made Mute cancel itself.
- **Kodi 21 script add-ons can't ship fonts.** A `Font.xml` in the add-on's skin folder is
  ignored (labels fall back to the default font); only the active skin's fonts work. The 90s
  promo lettering is therefore pictures of letters (`media/promo90s/glyphs`) placed by
  `promos.apply_card` into fixed image slots in the skin XML (ids 1300-1527).
- **Channel names are never cut off** (no "..."): Kodi labels can't shrink text, so each
  name label has a variant per skin font plus a two-line one, and Python picks one with
  `promos.fit_font(text, width, ladder, two)` (Noto Sans widths, `promos._px`), setting a
  property the variants' `<visible>` test (`promo_kicker_f90` / `_fm`, `ch_name_fsb` /
  `_foa`, the guide's `nfit`, `sid_label_fit`). A new place that shows a channel name
  needs the same. Fonts are Estuary's; other skins' sizes may differ.
- **An image slot emptied with `setImage("")` while its group is hidden keeps showing its old
  picture** when the group shows again (Kodi 21): the squeeze and a break's first card after a
  programme are lettered while their group is hidden. Letter slots are emptied *and*
  `setVisible(False)`, and `setVisible(True)` when used (`ads.Slots.fill`, `promos._fill`).
- **Never open a file just as the static clip ends:** Kodi's end-of-playlist handling for
  the clip then closes the file just opened (0.35 s of playback, `CVideoPlayer::OnExit`, then
  black until the watchdog). The clip is 2.5 s long so the 0.55 s hold always ends well before
  it. A file that stops within `EARLY_STOP` s of opening is reopened at once (`tv.early_stop`),
  a second stop gets the stand-in (not marked unplayable). EDL files' "Error adding mute"
  warnings are harmless (rig: 9 mid-file starts around overlapping cuts and mutes all played).
- **Tuning in mid-programme:** Kodi takes a moment to open and seek (2-3 s in the rig), and starts
  at the keyframe before the asked position when that's more than ~16 s back (the rig's
  25-second-GOP test media; real encodes have keyframes every 0.5-10 s). `tv.play` adds a learned
  start delay (`start_lag`: median of the last 10 tune-ins' open + seek time, 0-3 s; a sample
  more than 1.5 s off is a keyframe landing and is left out unless 3 in a row agree); the
  keyframe part is Kodi's. Only real tune-ins get it: CableBox's own start of a part after a
  break (`PART_START`) starts exactly at the mark.
- **The black cover (`tv.set_cover`) at every start partway in:** a tune-in keeps it until
  the first captions check has run (`Captions.checked_at`) and, with CC off, until Kodi
  reports its remembered subtitles off (1.5 s at most); a part after a break keeps it until
  the picture reaches the mark. Never trust `getTime()` before AV start: Kodi reports the
  position it was asked for (then the old file's). The cover is mirrored to the Home
  property `cablebox42.cover` for `cc_off_check.py`, which fails a round on any subtitle
  sample not under it. Run `cc_off_check.py setup` before every run: each CC-off round makes
  Kodi save "subtitles off" in the film's per-file memory, and a worn fixture turns the
  re-show test into a viewer's choice (CableBox then rightly switches CC on).
- **The CC setting (`state.json` cc_on) changes only through CableBox's own CC controls**
  (`Captions.switch` / `set_track` / `set_off` / `load_file`). What `_watch` sees from
  outside - Kodi re-applying its per-file "subtitles on", a phone remote, Kodi's menu - is
  for that programme only (`allowed` / `muted` sets), never the setting: Kodi's own re-show
  used to switch CC on for good (the Godfather setup). `cc_off_check.py` fails a round when
  the CC setting has changed.
- **guide_check.py switches the TV off with the Stop key first:** in captions mode (Kodi's
  full-screen player under CableBox's overlay dialog) Kodi refuses ActivateWindow(home)
  ("active modal dialogs") and the guide never comes up.
- **House promos never name the show the promo before named:** on a marathon channel the
  only show for hours is also the next one; `_resolve_promos` turns it into another
  channel's promo (`_house_cross_for`) or, failing that, the station ID card (`pt` 0).
- **A part ending mid-file (chapter mark or timed break) ends by the picture, not the clock**
  (`tv.end_at_mark`): the switch to the break is asked for when `getTime()` reaches the mark
  less `SWITCH_LEAD` (Kodi's switch time, measured in the rig), and `early_to` keeps the clock
  from bringing the part back until its slot ends. Without it the picture ran a few tenths
  ahead of the clock and ~0.5 s of the next act showed before the break. Rig check:
  `break_frames.py` films the screen around each break of the colour-act episodes
  (`rig/mkacts.sh`, `lineup-acts.json`): no frame of the wrong act on either side.
- **Image controls added from Python are unreliable**: `addControls` + a visible condition +
  entrance animations drew nothing until something else was added later. Use controls
  declared in the skin XML and fill them from Python (`setImage`, `setPosition`).
  Python's `colorDiffuse` is `0xAARRGGBB` (the XML's `AARRGGBB`).
- **`background="true"` textures load after the control is visible.** The promo card's
  title used to show only while `promo_logo` was empty, so it showed through while a logo
  loaded. Now `promos.card` sets *either* `promo_logo` *or* `promo_title` (logo only when
  `logo_ready`: the file exists and is in Kodi's texture cache), each control keys off its
  own property, and `tv.prefetch_promo` preloads the next logo via the skin's
  `promo_preload` image during the item before the card.
- **`Addons.ExecuteAddon` / `RunScript` split parameters at commas**; pass lists with `|`.
- **Still windows screenshot stale**: Kodi only redraws what changes, so `TakeScreenshot` of
  a window that has stopped moving can return an old frame. The contact sheet turns dirty
  regions off (`<algorithmdirtyregions>0`) in its portable profile.
- **Interface sounds need a playing stream or no stream.** `xbmc.playSFX` stalls while
  a programme is merely paused. The turn-off path pauses (instant silence), stops the
  programme (`release_audio()`), waits ~250 ms, then plays the sound.
- **An empty sound skin, or GUI sound volume 0, silences CableBox's own sounds too**
  (`CGUIAudioManager::Enable`, `PlayPythonSound` uses the GUI volume).
- **Station folders match exactly** (name, call letters, `N`, `Channel N`, `CH N`;
  case/punctuation ignored). Only time-block folders may match by "ends with". The old
  ends-with rule made "Disney Showcase 13" pass for channel 3.
- **Breaks are planned hours ahead**, so new clips appear in breaks planned later;
  a refresh (on closing Settings / the Channel manager / a tool, or *Tools → Refresh
  schedules*) uses them from each channel's next programme. Don't promise "from the
  next break".
- **Never throw a plan away to apply a change: cut it** (`ChannelSchedule.cut`). A
  wipe replans from the half hour, replacing what's on air and skipping every episode
  already planned (bookmarks move when an episode is *planned*). Every bookmark change
  while planning goes in the schedule's undo log; cut() puts them back. A show's
  bookmark is shared (series.json) only on its home channel; channels' hashes include
  their home shows so the old home is cut when a show moves.
- **Library caches live in each Kodi process** (TV, service, menus; 30 min). After a
  library change call `library.new_generation()` (refresh() does) so the others drop
  theirs too, and re-read `assign.json` before treating a channel as changed, or the
  TV and the service undo each other's home channels.
- **Planned black + one file at a time = 1.5-2 s gaps between spots.** `_fill` used to
  spread leftover seconds as black after each spot, and each spot ending on its own made
  Kodi close the player and the audio device and open the next file (~0.5 s in the rig,
  slower with passthrough). Now breaks are filled completely and the next item waits in
  Kodi's video playlist (`tv.queue_next`/`take_queued`): Kodi moves on in ~0.12 s with no
  black frame. Don't `playnext()` an item in its last ~1.5 s: it crosses Kodi's own move
  and leaves the player stopped (12 s of black until the watchdog). Rig: 1.3-1.7 s black
  per switch before, 0-0.12 s after (2026-11-12).
- **A control keeps drawing while its `Visible` animation runs**, even after its condition
  turns false (Kodi 21). The Modern promo background zooms for 16 s; a house break's
  next card (8-15 s later) without a picture still showed the old one. Long `Visible`
  animations need a short `Hidden` animation. Setting the property empty doesn't help.
- **Never hand Kodi a planned file without checking it exists** (`tv.file_missing`):
  for a missing file Kodi shows its own "Playback failed" box, which stays over the TV
  until someone presses OK, and `onPlayBackError` doesn't come for it (12 s of black).
- **Anything that changes what schedules are planned from must end in
  `manager.refresh_if_changed()`** (settings, lineup, station clips; applied.json
  remembers what the last refresh used), holding `TOOL_BUSY` like any tool.
- **Kodi caches an add-on's strings until Kodi restarts.** After editing `strings.po`,
  restart Kodi before testing: `_()` finds the id in the new file but Kodi returns the
  old text for it (a changed `%s` count then raises "not enough arguments").
- **Kodi's yes/no dialog text box shows 4 lines** (Estuary, 720p and 1080p); more
  scrolls the top lines out of sight. Put a long question in the dialog's heading.
  `yesnocustom` buttons read yes / no / custom from left to right, focus on *no*.
- **A library path whose case differs from the file on disk doesn't open through `xbmcvfs.File`** (Windows,
  Kodi 21: size 0, no bytes) although Python's `open()` and ffprobe read it. Happens when a file is renamed
  ('9 to 5' -> '9 To 5') after the library scan. Music videos use the name found on disk (`musicvideo_files`).
- **Vertical `grouplist` + `<align>right</align>` sits its items on the bottom edge** (Boombox caption):
  hidden lines close up and the block keeps one baseline.
- **This add-on's `settings.xml` is the old format, which has no setting levels**: Kodi 21 ignores a
  `level="3"` attribute (the setting shows at Standard). Expert-only settings need the new format.
- **Anything started from a Settings button must set `manager.TOOL_BUSY`** while it runs (tools via
  `run_tool`, Preview promo itself): `open_settings` waits only 2 s for it, then the CableBox menu
  opens again - over whatever is on screen.
- **The guide crawl** (`tv.crawl_loop`): list 50 is a `wraplist` with `<scrolltime tween="linear">3200`,
  moved by `Control.Move(50,1)` from its own thread every step (3.0 / 2.5 / 1.7 s). A linear scroll
  restarts from where it is, so a move arriving mid-scroll keeps the speed at exactly one row a
  step - the scroll time must stay above the slowest step and below twice the fastest (the list
  is 8 rows tall so Kodi's jump correction, `itemsPerPage / 4` rows, never fires). The 5-minute
  refresh changes the rows in place (`getListItem(i).setProperty`); `reset()` would jump.
  Rig: `rec F.mp4 40 "RunScript(script.cablebox42,watch,2)"`, then `.claude/tools/crawl_speed.py F.mp4`
  (in the rig) measures the grid's motion: a constant 35 px/s at 1080p (Normal), no still frames.
- **Skin conditions group with `[ ]`, not `( )`**, and `String.EndsWith(...,2)` also matches
  `font12`: the guide's cells use the value `two` for their two-line variant.
- **A `grouplist` clips its children to its own rectangle** (Kodi 21, verified in the rig): the weather
  map's tiles (`media/wxmap`, slots 4101-4112) sit in a group inside a grouplist and are moved with
  `setPosition` relative to it; a plain `group` would let them spill over the header and ticker.
- **The skin folder is `resources/skins/Default`** (capital D): a path built as `.../default/...` works
  on Windows and fails on Linux/CoreELEC (the weather map's `index.json` did).
- **Weather map and cities** come from Natural Earth (public domain) via `G:/CableBox42/rig/wx_prerender.py`
  (not shipped; the GeoJSON sources are in `G:/CableBox42/rig/naturalearth/`): `resources/weather/places.json`
  (places of 50,000+) and the 32768-px equirectangular world in 1024-px tiles (~1.9 MB, ocean-only
  tiles left out). `.claude/tools/gen_weather_xml.py` writes the two pages into the TV skin.
- `kodi-addon-checker` rejects `<news>` over 1500 characters. Keep the newest release
  notes there and the full history in `changelog.txt`.

## Testing

- `python3 -m pyflakes resources/lib/*.py` and `python3 -m py_compile resources/lib/*.py`.
- Check `strings.po` covers every `_("...")` literal and has no stale entries.
- Real Kodi: the test rig (next section). Audio timing there is not hardware-accurate;
  the N2 has the final word.
- Promo cards: `python .claude/promo-contact-sheet.py --kodi G:/Kodi` renders every
  library show's promo at 1080p and 720p in a portable *copy* of Kodi (own profile; the
  user's library DB and CableBox data are copied in, never written) and writes
  `G:/CableBox42/promo-contact-sheet/index.html`. Windows only; Kodi must be closed
  (one copy at a time). Cards come from `promo_preview.card_for_show`, the same code as
  *Settings → Advanced → Preview promo*.
- Hardware: the maintainer tests on the N2. On CoreELEC, `pastekodi` uploads the log;
  BusyBox tools (`ps`, `sed`) have fewer options than GNU.

## Test rig (Kodi 21, already built: run `ensure`, never rebuild)

- **Where:** a WSL distro of its own, **`CableBoxRig`** (Ubuntu 26.04, Kodi 21.3, Xvfb,
  PulseAudio null sink you can record). Its disk is
  `C:\Users\mrdav\AppData\Local\wsl\CableBoxRig\ext4.vhdx` (SSD: on G:, a USB hard
  disk, a cold Kodi start took 20 s); snapshots go in `G:\CableBox42\rig\snapshots\`.
  Outside the repo; it survives
  sessions, reboots and `wsl --shutdown`. Inside: Kodi profile `/root/.kodi`, test
  library `/root/library/tv` (Seinfeld, Friends, Mr. Bean, Star Trek TNG), outputs
  `/root/test`. The repo is at `/mnt/g/CableBox42/script.cablebox42`.
- **Start of every session:** `bash .claude/kodi21-test-vm.sh ensure` (Git Bash). It
  reuses the rig and starts Kodi in seconds; it builds only if the distro is missing or
  broken (from the newest snapshot if there is one, otherwise ~10 min of debootstrap in
  the `Ubuntu` distro). **Never run `setup` on Windows** and never make a second rig.
- **Install a build:** `bash .claude/kodi21-test-vm.sh install ../test-builds/<zip>`
  (enables it in Kodi's database and restarts Kodi). `lineup [FILE.json]` writes the
  3-channel test lineup (or yours), turns on the test commercials (`/root/library/ads`)
  and starts schedules afresh; `setting ID=VALUE...` sets CableBox settings (Kodi is
  stopped around it, or it writes its own copy back); `status` says what's installed
  and running.
- **Kodi 21's add-on settings dialog: Back cancels, only OK saves.** From a list item
  it's `Right Right Select` (the scrollbar takes the first Right).
- **Kodi repository checker:** `bash .claude/kodi21-test-vm.sh check ../test-builds/<zip>` runs
  `kodi-addon-checker --branch omega` on the unzipped build (installed in the rig in its own
  venv `/opt/kac`, on PATH; `ensure` and `setup` install it if it's missing). Expected result:
  0 problems and 1 warning, *403 Forbidden for url: https://forum.kodi.tv/...*: Kodi's forum
  blocks the checker's request, so it can't check the `<forum>` link (1.1.1 had it too).
  Only file endings on its whitelist pass: sounds ship as `.wav` (not mp3/ogg), clips as `.mp4`.
  *ERROR: 'Repository' object has no attribute 'addons'* (1 problem) means it couldn't
  download Kodi's omega repository index for the dependency check: run it again.
- **Drive it:** `send Down Select 2 Back` (numbers are pauses), `shot FILE.png`,
  `rec FILE.mp4 SECS [actions]` (picture + sound), `log [N]`, `sh 'CMD'`, `zap`, `stop`.
- **Break gaps** (`.claude/tools/`): `gaps.py [HOURS] [-v]` (inside the rig:
  `sh 'python3 /mnt/g/CableBox42/script.cablebox42/.claude/tools/gaps.py 6'`) lists every
  break's length, what its clips really play (ffprobe) and the leftover, flags a clip in a
  longer slot and spot repeats, and ends PASS/FAIL. `gaps_user.py ADDON_DATA HOURS` does
  the same read-only on a real Kodi's schedules (Windows Python, durations.json lengths).
  `notes.py SECS OUT` logs Kodi's player events with times (switch = OnStop -> next
  OnAVStart); `queue.py` plays three spots in a plain Kodi playlist as a reference.
  `recbreak.sh CH_ID CH_NUM` records the channel's next break and lists every switch,
  black frame and silence; `queue_test.py zap|back|refresh` checks the queued item never
  plays on the wrong channel, after Back, or after a replan; `breaks.py CH_ID [N]` prints
  breaks item by item. `lineup-gaps.json` is the 4-channel lineup with the movie channel.
  On Windows: `fill_replay.py ADDON_DATA [HOURS]` replays a real Kodi's breaks through
  this repo's `_fill` offline; `build_zip.py OUT.zip` builds a test zip (Git Bash has no zip).
  House breaks: `house_check.py [HOURS]` (rig; `CB_DATA=DIR` reads another addon_data read-only) checks cross-channel promos against the
  other schedule, repeats and system-ad availability, and per gap: a promo target not twice in 10 min nor over 3 times, each system / retro ad once,
  'tomorrow' before off-air at most twice (`lineup-gapvariety.json` with `SHORTS=2`: Shorties TV's 22-min gaps and its 04:00-07:00 off-air, Beacon off-air 02:00-06:00); `ab.sh save|run|diff` plans two
  builds from the same saved state and compares them entry by entry; `shots_at.sh`
  screenshots at given times; `check_strings.py` checks every `_()` text is in strings.po.
  Retro ads: `retro_check.py [HOURS] [-v]` (rig) checks repeats, the 2-hour rule, running
  gags, kids' channels, seasons, that videocassette cards name library movies and the
  per-break caps (2, 4 Movies; 3 a run, 4 Movies), video-themed limits (one a break, not two breaks running, 1 in 6 General / 1 in 3 Movies /
  1 in 4 others; prints per channel ads per break, video shares and `retro_stats` fallbacks);
  `lineup-retro.json` adds a kids-flavour channel; `lineup-names.json` is the same with long
  names (The Exploration Channel with its logo, a 40-character name without one). The rig's `lineup` turns the test
  commercials on: `setting commercials_path=` for house breaks.
  `plan_check.sh ZIP LINEUP OUT [refresh]` (Git Bash; `SHORTS=2` for one short per slot) installs,
  plans 24 h and runs retro_check, gaps, house_check and `guide_check.py` (every channel has a
  guide row; no "tick failed" in kodi.log), then optionally Tools > Refresh schedules and
  retro_check again on the files it left. `retro_check.py --data DIR --db FILE` reads a real
  Kodi's schedules read-only (blocks planned by an earlier build set aside). `lineup-shorts.json`
  adds Shorties TV (the rig's `shorts` command makes the 8-minute Shorties show) and All Movies
  (the rig's 2-minute films air as *Short Subjects*); `lineup-upnext.json` adds a Boombox channel
  on `/root/library/mv/` (the rig's `mvs` command makes 14 music videos). `SKIP=0..3` sets
  *Skip episodes shorter than* for `plan_check.sh`.
  Squeezed credits: `squeeze_check.py [HOURS] [-v]` (rig) checks every planned episode's squeeze start against the rules (chapters / final 30 s fallback / none for movies, under 15 min, a pinned-slot cut); `lineup-squeeze.json` has each case (set Sign-off TV's off-air window just ahead to check live that nothing squeezes before off-air). `lineup-bulk.json`: 12 channels over the 60 *Bulk Show* folders that `/mnt/g/CableBox42/rig/mkbig.sh` makes (4,200 episodes with act-break chapters; move them out of `/root/library/tv` and clean the library after).
  `shadow_check.py` (Windows or rig) fails on a function whose local variable hides a module it
  uses (the retro14 guide bug: `promos = []` in `fill_guide`).
- **Fresh start without rebuilding:** `reset-profile` wipes only the Kodi profile and
  the test library (Kodi stays), then makes and scans a new library; install again.
- **Snapshots:** `baseline.tar` is the clean rig (library, commercials, no CableBox).
  `ensure` restores the newest snapshot if the distro is missing or broken.
- **Snapshot / restore** (an export stops the distro first):
  `bash .claude/kodi21-test-vm.sh snapshot NAME` and
  `bash .claude/kodi21-test-vm.sh restore NAME.tar`, or by hand:
  `wsl --terminate CableBoxRig`, then
  `wsl --export CableBoxRig G:\CableBox42\rig\snapshots\NAME.tar`; restore with
  `wsl --unregister CableBoxRig`, then
  `wsl --import CableBoxRig C:\Users\mrdav\AppData\Local\wsl\CableBoxRig G:\CableBox42\rig\snapshots\NAME.tar`.
  (`wsl --manage CableBoxRig --move DIR` moves its disk; `wsl --shutdown` first.)
- Why it works under WSL: Xvfb, PulseAudio and Kodi start with `setsid nohup`; WSLg's
  `PULSE_SERVER` and its read-only `/tmp/.X11-unix` are put aside; ALSA goes to Pulse.
  On a plain Linux cloud VM the same script uses a chroot (`setup` builds it there).

## Release checklist

1. Bump `version` in `addon.xml`; put the release notes at the top of `<news>`
   (≤1500 chars total) and of `changelog.txt`.
2. Update README/HOWTO if behaviour or menus changed.
3. Build the zip from a clean tree, top folder `script.cablebox42/`, excluding
   dot-folders, caches and `tools/` (the retro-ad art scripts):
   `zip -qr -X script.cablebox42-X.Y.Z.zip script.cablebox42 -x "*/.*" "*/__pycache__/*" "*.pyc" "script.cablebox42/tools/*"`
4. Run `kodi-addon-checker --branch omega` on the unzipped build (`kodi21-test-vm.sh check ZIP`):
   0 problems; the only warning allowed is the forum link's 403 (see Test rig).
5. Install the zip in Kodi 21 and smoke-test (TV on, flip channels, turn off).
6. Branch `release/X.Y.Z` → pull request → the maintainer merges.
7. GitHub release `vX.Y.Z` on `main` with the zip attached: **the maintainer creates
   releases** (sessions may not be allowed to).
8. Kodi repository: one commit titled `[script.cablebox42] X.Y.Z` that replaces the
   `script.cablebox42/` folder, on a branch of the fork `SeadogMcGrog/repo-scripts`
   based on `xbmc/repo-scripts` **omega**; the maintainer opens the PR to `omega`.
   Kodi asks for at most one or two updates a month.

## Open items (as of 2026-11-08)

- **Boombox (music videos)** (`briefs/boombox-wizard.md`, on `dev`): the N2 Step 1 switch test (23.976 ->
  29.97 -> 25 video -> episode in a plain Kodi playlist: blackout length, receiver dropouts on stereo <-> 5.1
  and PCM <-> AC-3; two same-rate videos back to back: no blackout) is still to do - record it under
  *Hard-won lessons*. Then on the N2: wizard scan time with 200+ videos, first background measuring without
  stutter, an hour of Boombox (switches only at block boundaries, caption smooth at 1080p).
- **Schedule promos** (branch `feature/schedule-promos`, off by default): the N2 Step 1
  test (video, then theme.mp3, then video, with AC3 passthrough and refresh rate
  'On start/stop') is still to be done. Record the result under *Hard-won lessons*.
  If the audio-only item blacks out or drops audio, set the *Promo music* default
  to silent. Themes play at their own level (see *Never change Kodi's volume*); if
  they are much louder than episodes on the N2, that is a content issue, not a volume
  setting to touch.
- Kodi pull request in `xbmc/repo-scripts` still holds **1.1.0**; replace with 1.1.1
  (force-push the fork branch — ask the maintainer first).
- GitHub release v1.1.1 not yet published (maintainer).
- Atmos (TrueHD/E-AC-3) passthrough not yet tested with channel flipping.
- Ideas parked: Channel manager row hints; one-time README.txt in the stations root;
  matching improvements (auto-placed leftovers scored as weak, studio "contains" below
  network, "(US)" network suffixes, balancing limit, tie-breaks, duplicate titles,
  separating automatic hides from the user's); music-video channels.
