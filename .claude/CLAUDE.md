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
- **Kodi caches an add-on's strings until Kodi restarts.** After editing `strings.po`,
  restart Kodi before testing: `_()` finds the id in the new file but Kodi returns the
  old text for it (a changed `%s` count then raises "not enough arguments").
- **Kodi's yes/no dialog text box shows 4 lines** (Estuary, 720p and 1080p); more
  scrolls the top lines out of sight. Put a long question in the dialog's heading.
  `yesnocustom` buttons read yes / no / custom from left to right, focus on *no*.
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

- Kodi pull request in `xbmc/repo-scripts` still holds **1.1.0**; replace with 1.1.1
  (force-push the fork branch — ask the maintainer first).
- GitHub release v1.1.1 not yet published (maintainer).
- Atmos (TrueHD/E-AC-3) passthrough not yet tested with channel flipping.
- Ideas parked: Channel manager row hints; one-time README.txt in the stations root;
  matching improvements (auto-placed leftovers scored as weak, studio "contains" below
  network, "(US)" network suffixes, balancing limit, tie-breaks, duplicate titles,
  separating automatic hides from the user's); music-video channels.
