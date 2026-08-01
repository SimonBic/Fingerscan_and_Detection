#!/bin/bash
# Installer, dass man es sofort verwenden kann.

#HOW TO INSTALL:
#Only testet on Fedora / Linux. 

#1:
#Ein Terminal oeffnen:
#Strg+Alt+T

#2:
#In das Terminal eingeben:
#cd /pfad/zum/repo/Fingerscan_and_Detection/src/installer

#3:
#Dann im Terminal eingeben:
#bash ./install.sh

#App wird dann im Anwendungsmenue und auf dem Desktop als "Fingerscan Viewer" zu finden sein.

set -e  # Skript abbrechen, falls n Befehl fehlschlaegt

#Herausfinden, wo dieses Skript leigt
INSTALLER_ORDNER="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
REPO_ORDNER="$( dirname "$( dirname "$INSTALLER_ORDNER" )" )"
APP_ORDNER="$REPO_ORDNER/src/finger_marked_area_detection"
ICON_PFAD="$INSTALLER_ORDNER/logo.svg"

echo "Installer-Ordner gefunden: $INSTALLER_ORDNER"
echo "App-Ordner:                $APP_ORDNER"

# Pruefen, ob die wichtigsten Dateien tatsaechlich da sind:
if [ ! -f "$APP_ORDNER/userinterface.py" ]; then
    echo "FEHLER: userinterface.py wurde nicht gefunden unter $APP_ORDNER"
    exit 1
fi

if [ ! -f "$ICON_PFAD" ]; then
    echo "FEHLER: Icon wurde nicht gefunden unter $ICON_PFAD"
    exit 1
fi

#.desktop-Datei mit den richtigen Pfaden bauen
DESKTOP_INHALT="[Desktop Entry]
Type=Application
Name=Fingerscan Viewer
Comment=UKR Fingerscan-Analyse-Tool
Exec=python3 userinterface.py
Path=$APP_ORDNER
Icon=$ICON_PFAD
Terminal=false
Categories=Science;Graphics;"

#An beide ueblichen Stellen installieren
APPLIKATIONEN_ORDNER="$HOME/.local/share/applications"
mkdir -p "$APPLIKATIONEN_ORDNER"

echo "$DESKTOP_INHALT" > "$APPLIKATIONEN_ORDNER/fingerscan-viewer.desktop"
chmod +x "$APPLIKATIONEN_ORDNER/fingerscan-viewer.desktop"
echo "Im Anwendungsmenue installiert: $APPLIKATIONEN_ORDNER/fingerscan-viewer.desktop"

if [ -d "$HOME/Desktop" ]; then
    echo "$DESKTOP_INHALT" > "$HOME/Desktop/fingerscan-viewer.desktop"
    chmod +x "$HOME/Desktop/fingerscan-viewer.desktop"

    # GNOME vertraut neuen Desktop-Dateien standardmaessig nicht -
    # dieses Flag setzt automatisch, was sonst per Rechtsklick ->
    # "Starten erlauben" gesetzt werden muesste
    if command -v gio &> /dev/null; then
        gio set "$HOME/Desktop/fingerscan-viewer.desktop" "metadata::trusted" true 2>/dev/null || true
    fi

    echo "Auf dem Desktop installiert: $HOME/Desktop/fingerscan-viewer.desktop"
fi

echo ""
echo "Installation abgeschlossen. Die App sollte jetzt im Anwendungsmenue"
echo "und auf dem Desktop als 'Fingerscan Viewer' zu finden sein."