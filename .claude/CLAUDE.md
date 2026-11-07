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
| `resources/lib/library.py` | Kodi library queries (JSON-RPC) |
| `.claude/make-promo-art.py` | Rebuilds the 90s promo art (`media/promo90s/`: Bebas Neue letter pictures, bands, shapes). Not shipped |
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
  *Tools → Rebuild schedules* uses them at once. Don't promise "from the next break".
- `kodi-addon-checker` rejects `<news>` over 1500 characters. Keep the newest release
  notes there and the full history in `changelog.txt`.

## Testing

- `python3 -m pyflakes resources/lib/*.py` and `python3 -m py_compile resources/lib/*.py`.
- Check `strings.po` covers every `_("...")` literal and has no stale entries.
- Real Kodi: `.claude/kodi21-test-vm.sh` builds a headless Kodi 21.3 (Ubuntu 26.04
  chroot, Xvfb, PulseAudio null sink you can record) and has helpers to install the
  add-on, start the TV, flip channels and count audio errors. Linux with root only
  (a cloud session, or WSL). Audio timing in the VM is not hardware-accurate; the N2
  has the final word.
- Promo cards: `python .claude/promo-contact-sheet.py --kodi G:/Kodi` renders every
  library show's promo at 1080p and 720p in a portable *copy* of Kodi (own profile; the
  user's library DB and CableBox data are copied in, never written) and writes
  `G:/CableBox42/promo-contact-sheet/index.html`. Windows only; Kodi must be closed
  (one copy at a time). Cards come from `promo_preview.card_for_show`, the same code as
  *Settings → Advanced → Preview promo*.
- Hardware: the maintainer tests on the N2. On CoreELEC, `pastekodi` uploads the log;
  BusyBox tools (`ps`, `sed`) have fewer options than GNU.

## Release checklist

1. Bump `version` in `addon.xml`; put the release notes at the top of `<news>`
   (≤1500 chars total) and of `changelog.txt`.
2. Update README/HOWTO if behaviour or menus changed.
3. Build the zip from a clean tree, top folder `script.cablebox42/`, excluding
   dot-folders and caches:
   `zip -qr -X script.cablebox42-X.Y.Z.zip script.cablebox42 -x "*/.*" "*/__pycache__/*" "*.pyc"`
4. Run `kodi-addon-checker --branch omega` on the unzipped build: 0 problems.
5. Install the zip in Kodi 21 and smoke-test (TV on, flip channels, turn off).
6. Branch `release/X.Y.Z` → pull request → the maintainer merges.
7. GitHub release `vX.Y.Z` on `main` with the zip attached: **the maintainer creates
   releases** (sessions may not be allowed to).
8. Kodi repository: one commit titled `[script.cablebox42] X.Y.Z` that replaces the
   `script.cablebox42/` folder, on a branch of the fork `SeadogMcGrog/repo-scripts`
   based on `xbmc/repo-scripts` **omega**; the maintainer opens the PR to `omega`.
   Kodi asks for at most one or two updates a month.

## Open items (as of 2026-11-06)

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
