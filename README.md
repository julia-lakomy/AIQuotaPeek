# AIQuotaPeek

AIQuotaPeek is the project behind **Limity AI**, a personal KDE Plasma 6 panel widget. It shows the percentage of each ChatGPT and Claude usage limit that **remains**. Open the widget to see available session and weekly limits, reset times, and the time of the last successful reading.

Example panel text: `GPT 42% · Claude 12%`. When a service provides two limits, the panel shows the lower remaining percentage. Open the widget for the individual values. `—` means that no value is available for that service yet.

## Quick start

The project has been tested on Ubuntu 26.04 with KDE Plasma 6. The installer expects Falkon at `/usr/bin/falkon`, Python 3, Plasma and KWin tools, `systemctl --user`, and `rg`. If PyQt6 WebEngine modules are missing, it downloads the required packages with `apt download` and extracts them into the project's `.deps` directory. It does not install Falkon itself.

From the project directory, run:

```bash
bash scripts/install.sh
```

The installer adds the widget, a KWin script that detects fullscreen windows, and the `limity-ai-widget.service` user service. It does not require an administrator password. If the widget is not already on your panel, add it in KDE under the name **Limity AI**.

1. Click the widget to open ChatGPT and Claude Usage pages in a dedicated Falkon profile.
2. Sign in on both sites as usual. Enter passwords and verification codes on the sites, not in the widget.
3. Click **Zakończ logowanie** (“Finish sign-in”) in the widget, or close every window of the dedicated Falkon instance. This lets the background reader reopen the profile.
4. Wait for the first reading. Falkon can stay closed afterward.

Falkon opens only after an action in the widget. If a sign-in session expires, clicking the widget opens the page that needs you to sign in again.

## Using the widget

| Display | Meaning |
| --- | --- |
| `GPT 42% · Claude 12%` | The lowest available remaining percentage for each service. |
| **Obecna sesja** (“Current session”) | The remaining percentage of the shorter session limit, if the Usage page provides it. |
| **Limit tygodniowy** (“Weekly limit”) | The remaining percentage of the weekly limit. |
| **Reset** | The reset day and time in the `Europe/Warsaw` time zone. A leading `~` means the time was calculated from a relative countdown shown by the service. |
| **Odczyt** (“Read”) | The time of the last successful reading for that service. |
| **brak danych** (“no data”) | The page does not provide that limit, it has not been read yet, or the reading failed. |

The background reader refreshes the pages every five minutes. The **⟳** button requests a manual refresh. **ChatGPT ↗** and **Claude ↗** open the selected page in the dedicated Falkon profile, for example when you need to sign in again.

Automatic readings pause while the active window is fullscreen. The panel keeps the last known values, and the expanded widget shows **Wstrzymano podczas pełnego ekranu** (“Paused during fullscreen”). Reading resumes about 15 seconds after you leave fullscreen. No window opens at that point.

On the ChatGPT account used to test this project, the Usage page shows a weekly percentage but no separate percentage for the current session. The widget therefore shows **brak danych** for the ChatGPT session; it does not infer a session value from the weekly limit. Claude provides both percentages.

## Troubleshooting

| Symptom | What to check |
| --- | --- |
| The panel shows `—` | Open the widget. If it asks you to sign in, use the dedicated Falkon window. If it shows **Usługa widgetu nie działa** (“Widget service is not running”), check the service with the command below. |
| **Przeglądarka jest otwarta** (“Browser is open”) remains after closing one window | Another window of the dedicated Falkon profile may still be open. Click **Zakończ logowanie** in the widget. |
| **Wstrzymano podczas pełnego ekranu** appears | This is expected during fullscreen games. Leave fullscreen and wait about 15 seconds. |
| **Oczekiwanie na stan pełnego ekranu z KDE** (“Waiting for KDE fullscreen status”) appears | The KWin script has not reported its state yet. Run `bash scripts/install.sh`; if the message persists, sign out of KDE and sign back in. |
| The ChatGPT session shows **brak danych** | The tested ChatGPT Usage page does not currently expose a session percentage. The weekly limit should still be available. |
| The panel still shows an old layout after an update | Follow the steps in “Updating and removing” below. |

Check the service and its recent messages:

```bash
systemctl --user status limity-ai-widget.service
journalctl --user -u limity-ai-widget.service -n 50 --no-pager
```

Check the current state without opening a browser:

```bash
python3 scripts/check_live.py
```

Request a fresh reading of both pages:

```bash
python3 scripts/check_live.py --refresh
```

The `--refresh` check refuses to run while a fullscreen window is active or the dedicated Falkon instance is open. `GREEN` means three expected percentages are available: ChatGPT weekly, Claude session, and Claude weekly. A separate ChatGPT session value is not required by this check.

## Updating and removing

After changing the code, rerun the installer and restart the service so it loads the new Python code:

```bash
bash scripts/install.sh
systemctl --user restart limity-ai-widget.service
```

If you change the widget's appearance and the panel still shows the old version, reload the panel outside a game:

```bash
systemctl --user restart plasma-plasmashell.service
```

The panel may briefly disappear and return. Reloading it does not open a sign-in window. The user service points to the **current project directory**; rerun the installer if you move the project.

To remove the service and KDE packages:

```bash
bash scripts/uninstall.sh
```

The uninstall script **keeps** the dedicated browser profile and its saved sessions, normally under `~/.local/share/limity-ai-widget`. Remove that directory separately only if you also want to delete that data. The local service configuration and token remain under `~/.config/limity-ai-widget`.

## Privacy, resource use, and limitations

Falkon and the invisible Qt WebEngine reader use a dedicated profile. They do not use Firefox, Brave, or Vivaldi profiles. The widget receives percentages, reset times, reading status, and the last reading time. You enter passwords directly on the services' sites. The widget connects to the reader through `127.0.0.1` using a token stored in files owned by the user.

In a measurement on the test machine before signing in, the idle reader used about **183 MiB PSS** and 0.01 s of CPU time over five seconds. Falkon with two pages open used about **1.1 GiB PSS**, so it runs only when requested. Resource use after signing in may differ.

The project reads text from the Usage pages rather than using an API for personal account limits. Changes to those pages may require parser updates. Values reflect the last successful reading and can become stale between refreshes. Implementation details are in the [technical documentation (Polish)](docs/ARCHITECTURE.md).
