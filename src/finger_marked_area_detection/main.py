import load_scan
import cut_finger
from cut_finger import cut_finger_main
import draw_area_on_scan


def show_scan(path):
        try:
            handscan_mesh = load_scan.load_whole_folder(path)
            print("Scan erfolgreich geladen.")
        except Exception as e:
            print(f"Fehler beim Laden des Scanss: {e}")
            return

        try:
            handscan_mesh.show()
        except Exception as e:
            print(f"Fehler beim Anzeigen des Scans: {e}")

def main():
    pfad = input("Pfad: ")

    print("Wähle Funktion: ")
    print("1: Zeige Scan")
    print("2: Cut Scan")
    print("3: Kreise Scan ein")
    input_user = input()
    if input_user == "1":
        show_scan(pfad)
    elif(input_user == "2"):
        cut_finger_main(load_scan.load_whole_folder(pfad))
    elif(input_user == "3"):
        #Unfinished
        print("unfinished")
        my_area_drawer = draw_area_on_scan.DrawCircleViewer(load_scan.load_whole_folder(pfad), pfad)
        my_area_drawer.draw_circle_on_mesh(load_scan.load_whole_folder(pfad), pfad)
    


if __name__ == "__main__":
    main()

#/home/simonbichler/Arbeit/UKR/Fingerscans/Zwischensicherung_3Dscans/Patient 14/Patient 14 Woche 2/P14 W2 vectra final
#/home/simonbichler/Arbeit/UKR/Fingerscans/Zwischensicherung_3Dscans/Kollegen betäubt/Marc betäubt/Marc final vectra