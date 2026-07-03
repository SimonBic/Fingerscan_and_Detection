import load_scan


def main():
    pfad = input("Pfad: ")
    try:
        handscan_mesh = load_scan.load_whole_folder(pfad)
        print("Scan erfolgreich geladen.")
    except Exception as e:
        print(f"Fehler beim Laden des Scans: {e}")
        return

    try:
        handscan_mesh.show()
    except Exception as e:
        print(f"Fehler beim Anzeigen des Scans: {e}")


if __name__ == "__main__":
    main()

#/home/simonbichler/Arbeit/UKR/Fingerscans/Zwischensicherung_3Dscans/Patient 14/Patient 14 Woche 2/P14 W2 vectra final
#/home/simonbichler/Arbeit/UKR/Fingerscans/Zwischensicherung_3Dscans/Kollegen betäubt/Marc betäubt/Marc final vectra