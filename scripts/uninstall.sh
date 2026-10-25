#!/usr/bin/env bash
set -euo pipefail

systemctl --user disable --now limity-ai-widget.service || true
rm -f "${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user/limity-ai-widget.service"
systemctl --user daemon-reload
kpackagetool6 -t Plasma/Applet -r org.limityai.widget || true
kpackagetool6 -t KWin/Script -r limity_ai_fullscreen || true
kwriteconfig6 --file kwinrc --group Plugins --key limity_ai_fullscreenEnabled false
qdbus6 org.kde.KWin /KWin reconfigure >/dev/null 2>&1 || true
echo "Usunięto usługę i widżet. Dane przeglądarki pozostały w ~/.local/share/limity-ai-widget."
