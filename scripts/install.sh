#!/usr/bin/env bash
set -euo pipefail

project_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
deps_dir="$project_dir/.deps"
config_home="${XDG_CONFIG_HOME:-$HOME/.config}"
data_home="${XDG_DATA_HOME:-$HOME/.local/share}"
config_dir="$config_home/limity-ai-widget"
data_dir="$data_home/limity-ai-widget"
unit_dir="$config_home/systemd/user"

mkdir -p "$deps_dir" "$config_dir" "$data_dir" "$unit_dir"
chmod 700 "$config_dir" "$data_dir"

if ! python3 -c 'from PyQt6 import QtWebEngineCore, QtWebEngineWidgets' >/dev/null 2>&1; then
    if [[ ! -f "$deps_dir/usr/lib/python3/dist-packages/PyQt6/QtWebEngineCore.abi3.so" ]]; then
        download_dir="$(mktemp -d)"
        (
            cd "$download_dir"
            apt download python3-pyqt6.qtwebengine python3-pyqt6.qtwebchannel
            for package in ./*.deb; do
                dpkg-deb -x "$package" "$deps_dir"
            done
        )
        rm -rf "$download_dir"
    fi
fi

package_dir="$(mktemp -d)"
trap 'rm -rf "$package_dir"' EXIT
cp -a "$project_dir/plasmoid" "$package_dir/plasmoid"

python3 - "$config_dir/config.json" "$data_dir" "$package_dir/plasmoid/contents/code/Config.js" <<'PY'
import json
import secrets
import sys
from pathlib import Path

config_path, data_dir, js_path = map(Path, sys.argv[1:])
config = json.loads(config_path.read_text()) if config_path.exists() else {}
config.setdefault("token", secrets.token_hex(24))
config.setdefault("port", 41817)
config["dataDir"] = str(data_dir)
config_path.write_text(json.dumps(config, indent=2) + "\n")
config_path.chmod(0o600)
js_path.write_text(
    '.pragma library\n\nvar port = ' + str(config["port"]) + ';\n'
    + 'var token = ' + json.dumps(config["token"]) + ';\n'
)
PY

if kpackagetool6 -t Plasma/Applet -l | rg -q 'org\.limityai\.widget'; then
    kpackagetool6 -t Plasma/Applet -u "$package_dir/plasmoid"
else
    kpackagetool6 -t Plasma/Applet -i "$package_dir/plasmoid"
fi
chmod 600 "$data_home/plasma/plasmoids/org.limityai.widget/contents/code/Config.js"

if kpackagetool6 -t KWin/Script -l | rg -q 'limity_ai_fullscreen'; then
    kpackagetool6 -t KWin/Script -u "$project_dir/kwin"
else
    kpackagetool6 -t KWin/Script -i "$project_dir/kwin"
fi

kwriteconfig6 --file kwinrc --group Plugins --key limity_ai_fullscreenEnabled true
qdbus6 org.kde.KWin /KWin reconfigure >/dev/null 2>&1 || true

cat > "$unit_dir/limity-ai-widget.service" <<EOF
[Unit]
Description=Limity AI browser reader
After=graphical-session.target

[Service]
Type=simple
Environment=QT_QPA_PLATFORM=offscreen
ExecStart=/usr/bin/python3 $project_dir/backend/app.py
Restart=on-failure
RestartSec=5

[Install]
WantedBy=default.target
EOF

systemctl --user daemon-reload
systemctl --user enable --now limity-ai-widget.service

echo "Zainstalowano widżet „Limity AI” z projektu AIQuotaPeek. Dodaj go do panelu Plasma, jeśli nie jest jeszcze widoczny."
echo "Przy pierwszym użyciu kliknij widżet, aby otworzyć dedykowanego Falkona i zalogować się."
