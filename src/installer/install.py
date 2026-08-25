
# Plattformuebergreifender Installer (Windows/macOS) - legt eine .venv
# an, installiert die exakt gepinnten Pakete aus requirements.txt, und
# richtet ein echtes Programm-Icon ein (Desktop-Verknuepfung unter
# Windows, .app-Bundle unter macOS).

# Fuer Linux weiterhin install.sh nutzen (kuemmert sich zusaetzlich um
# die System-Bibliothek xcb-util-cursor/libxcb-cursor0 und ein
# .desktop-Icon).

# Aufruf:
#     python install.py

import platform
import shutil
import subprocess
import sys
from pathlib import Path

INSTALLER_ORDNER = Path(__file__).resolve().parent
REPO_ORDNER = INSTALLER_ORDNER.parent.parent
APP_ORDNER = REPO_ORDNER / "src" / "finger_marked_area_detection"
VENV_PFAD = REPO_ORDNER / ".venv"
REQUIREMENTS_PFAD = REPO_ORDNER / "requirements.txt"
LOGO_PNG_PFAD = INSTALLER_ORDNER / "logo.png"

VENV_PYTHON = VENV_PFAD / ("Scripts" if platform.system() == "Windows" else "bin") / (
    "python.exe" if platform.system() == "Windows" else "python"
)


def fehler(text: str) -> None:
    print(f"FEHLER: {text}")
    sys.exit(1)


def python_314_befehl() -> list:
    if platform.system() == "Windows":
        try:
            ergebnis = subprocess.run(["py", "-3.14", "--version"], capture_output=True, text=True)
            if ergebnis.returncode == 0 and "3.14" in ergebnis.stdout:
                return ["py", "-3.14"]
        except FileNotFoundError:
            pass
        fehler(
            "Python 3.14 wurde nicht gefunden. Bitte von https://www.python.org/downloads/ "
            "installieren (Haken bei 'Add python.exe to PATH' nicht vergessen)."
        )

    for kandidat in ("python3.14", "python3.14.exe"):
        if shutil.which(kandidat):
            return [kandidat]

    fehler(
        "Python 3.14 wurde nicht gefunden. "
        + ("Auf macOS z.B. mit: brew install python@3.14" if platform.system() == "Darwin" else "")
    )


def venv_sicherstellen() -> None:
    python_befehl = python_314_befehl()

    if VENV_PFAD.exists():
        try:
            ergebnis = subprocess.run([str(VENV_PYTHON), "--version"], capture_output=True, text=True)
            if "3.14" in ergebnis.stdout:
                print(f"Bestehende virtuelle Umgebung passt bereits ({ergebnis.stdout.strip()}).")
                return
        except FileNotFoundError:
            pass
        print("Bestehende virtuelle Umgebung passt nicht, wird neu angelegt...")
        shutil.rmtree(VENV_PFAD)

    print(f"Erstelle virtuelle Umgebung unter {VENV_PFAD} ...")
    subprocess.run([*python_befehl, "-m", "venv", str(VENV_PFAD)], check=True)


def abhaengigkeiten_installieren() -> None:
    print("Installiere/prüfe Abhängigkeiten (exakte Versionen aus requirements.txt)...")
    subprocess.run([str(VENV_PYTHON), "-m", "pip", "install", "--upgrade", "pip", "--quiet"], check=True)
    subprocess.run([str(VENV_PYTHON), "-m", "pip", "install", "-r", str(REQUIREMENTS_PFAD)], check=True)
    print("Abhängigkeiten erfolgreich installiert.")


def windows_icon_einrichten() -> None:
    ico_pfad = INSTALLER_ORDNER / "logo.ico"

    # Laeuft ueber die VENV-Python (dort ist Pillow schon installiert),
    # NICHT ueber die System-Python, die install.py selbst ausfuehrt
    konvertier_skript = (
        f'from PIL import Image; '
        f'Image.open(r"{LOGO_PNG_PFAD}").save(r"{ico_pfad}", '
        f'sizes=[(16,16),(32,32),(48,48),(128,128),(256,256)])'
    )
    subprocess.run([str(VENV_PYTHON), "-c", konvertier_skript], check=True)
    print(f"Icon erzeugt: {ico_pfad}")

    main_py_pfad = APP_ORDNER / "main.py"

    ps_skript = f'''
        $WshShell = New-Object -comObject WScript.Shell

        $ZielPfade = @(
            "$env:USERPROFILE\\Desktop\\Fingerscan Viewer.lnk",
            "$env:APPDATA\\Microsoft\\Windows\\Start Menu\\Programs\\Fingerscan Viewer.lnk"
        )

        foreach ($Pfad in $ZielPfade) {{
            $Shortcut = $WshShell.CreateShortcut($Pfad)
            $Shortcut.TargetPath = "{VENV_PYTHON}"
            $Shortcut.Arguments = '"{main_py_pfad}"'
            $Shortcut.WorkingDirectory = "{APP_ORDNER}"
            $Shortcut.IconLocation = "{ico_pfad}"
            $Shortcut.Save()
            Write-Host "Verknuepfung angelegt: $Pfad"
        }}
        '''
    
    ps_datei = INSTALLER_ORDNER / "_verknuepfung_erstellen.ps1"
    ps_datei.write_text(ps_skript)

    subprocess.run(
        ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(ps_datei)],
        check=True,
    )
    ps_datei.unlink()


def macos_app_bundle_einrichten() -> None:
    iconset_ordner = INSTALLER_ORDNER / "Icon.iconset"
    iconset_ordner.mkdir(exist_ok=True)

    konvertier_skript = f'''
        from PIL import Image
        bild = Image.open(r"{LOGO_PNG_PFAD}").convert("RGBA")
        for groesse in (16, 32, 128, 256, 512):
            bild.resize((groesse, groesse)).save(r"{iconset_ordner}/icon_{{}}x{{}}.png".format(groesse, groesse))
            bild.resize((groesse*2, groesse*2)).save(r"{iconset_ordner}/icon_{{}}x{{}}@2x.png".format(groesse, groesse))
        '''
    subprocess.run([str(VENV_PYTHON), "-c", konvertier_skript], check=True)

    icns_pfad = INSTALLER_ORDNER / "logo.icns"
    subprocess.run(["iconutil", "-c", "icns", str(iconset_ordner), "-o", str(icns_pfad)], check=True)
    shutil.rmtree(iconset_ordner)
    print(f"Icon erzeugt: {icns_pfad}")

    app_pfad = Path.home() / "Desktop" / "Fingerscan Viewer.app"
    (app_pfad / "Contents" / "MacOS").mkdir(parents=True, exist_ok=True)
    (app_pfad / "Contents" / "Resources").mkdir(parents=True, exist_ok=True)

    info_plist = f'''<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleExecutable</key>
    <string>launcher</string>
    <key>CFBundleIconFile</key>
    <string>logo.icns</string>
    <key>CFBundleIdentifier</key>
    <string>de.ukr.fingerscanviewer</string>
    <key>CFBundleName</key>
    <string>Fingerscan Viewer</string>
    <key>CFBundlePackageType</key>
    <string>APPL</string>
</dict>
</plist>
'''
    (app_pfad / "Contents" / "Info.plist").write_text(info_plist)
    shutil.copy(icns_pfad, app_pfad / "Contents" / "Resources" / "logo.icns")

    launcher_pfad = app_pfad / "Contents" / "MacOS" / "launcher"
    launcher_pfad.write_text(f'#!/bin/bash\n"{VENV_PYTHON}" "{APP_ORDNER / "main.py"}"\n')
    launcher_pfad.chmod(0o755)

    print(f"App-Bundle angelegt: {app_pfad}")
    print("Beim allerersten Start: Rechtsklick -> 'Öffnen', sonst blockiert Gatekeeper unsignierte Apps.")


if __name__ == "__main__":
    if not (APP_ORDNER / "main.py").exists():
        fehler(f"main.py wurde nicht gefunden unter {APP_ORDNER}")

    if not LOGO_PNG_PFAD.exists():
        fehler(
            f"logo.png wurde nicht gefunden unter {INSTALLER_ORDNER}. "
            "Bitte einmalig aus Inkscape als PNG exportieren (logo.svg -> logo.png, mind. 512x512)."
        )

    venv_sicherstellen()
    abhaengigkeiten_installieren()

    if platform.system() == "Windows":
        windows_icon_einrichten()
    elif platform.system() == "Darwin":
        macos_app_bundle_einrichten()

    print("\nInstallation abgeschlossen.")