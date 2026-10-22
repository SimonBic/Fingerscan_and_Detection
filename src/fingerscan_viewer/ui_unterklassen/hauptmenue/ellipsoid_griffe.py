import numpy as np
import pyvista as p_v
import vtk

from PySide6.QtCore import Qt, QEvent, QObject, QTimer
from PySide6.QtWidgets import QApplication

import konstanten as k


class EllipsoidGriffe(QObject):
    # Drei Pfeile am Schnittellipsoid bei "Selbst justieren". Pfeil ziehen
    # streckt oder staucht diese Achse, Feststelltaste halten und ziehen
    # verschiebt den ganzen Ellipsoid.
    # Die Klasse rechnet nur Mauswege in mm um. Was daraus fuer die Regler
    # wird, entscheidet das HauptFenster in bei_ziehen(griff, delta):
    #   griff "laenge"/"breite"/"dicke": delta = mm entlang des Pfeils seit dem Klick
    #   griff "verschieben": delta = Verschiebung als Vektor in mm seit dem Klick
    # bei_start() kommt beim Klick, damit sich das HauptFenster den Stand merkt.

    ACHSEN = ("laenge", "breite", "dicke")

    def __init__(self, plotter, pfeil_laenge, bei_start, bei_ziehen):
        super().__init__()
        self._plotter = plotter
        self._pfeil_laenge = pfeil_laenge
        self._bei_start = bei_start
        self._bei_ziehen = bei_ziehen

        self._geometrie = None
        # je Achse (Fuss, Richtung), Richtung zeigt vom Ellipsoid weg
        self._pfeile = {}
        self._actors = {}
        self._hover = None
        self._feststell_gehalten = False
        # None, "verschieben" oder eine Achse, solange gezogen wird
        self._ziehen = None
        self._ziehen_start = None

        self._picker = vtk.vtkCellPicker()
        self._picker.SetTolerance(0.005)
        self._picker.PickFromListOn()

        # App-weit statt nur auf dem Viewer, weil die Feststelltaste bei
        # jedem Widget ankommen kann (z.B. wenn gerade ein Regler den Fokus
        # hat). Die Mausereignisse des Viewers laufen da auch durch, also
        # reicht der eine Filter. Ein zweiter auf dem Viewer wuerde jedes
        # Ereignis doppelt sehen.
        QApplication.instance().installEventFilter(self)

    # ---------- Pfeile ----------

    def zeige(self, geometrie):
        # Nach jeder Aenderung am Ellipsoid, egal ob Regler oder Ziehen
        self._geometrie = geometrie
        self._pfeile_setzen()

    def _pfeile_setzen(self):
        if self._geometrie is None:
            return
        mitte = self._geometrie["mitte"]
        kamera = np.array(self._plotter.camera.position)
        for achse in self.ACHSEN:
            richtung = self._geometrie["achsen"][achse]
            # Laenge immer an der Spitze oben. Breite und Dicke auf der Seite,
            # die zur Kamera zeigt, sonst stecken sie je nach Hand und
            # Blickwinkel hinter dem Finger.
            if achse != "laenge" and np.dot(richtung, kamera - mitte) < 0:
                richtung = -richtung
            fuss = mitte + self._geometrie["halbachsen"][achse] * richtung
            self._pfeile[achse] = (fuss, richtung)

            pfeil = p_v.Arrow(start=fuss, direction=richtung, scale=self._pfeil_laenge,
                              tip_length=0.3, tip_radius=0.12, shaft_radius=0.045)
            self._actors[achse] = self._plotter.add_mesh(
                pfeil, color=self._farbe(achse), name=f"ellipsoid_pfeil_{achse}",
                smooth_shading=True, reset_camera=False, render=False)
        self._plotter.render()

    def _farbe(self, achse):
        if achse == self._hover or achse == self._ziehen:
            return k.ISOLIEREN_PFEIL_HOVER
        return k.ISOLIEREN_PFEIL_FARBEN[achse]

    def _hover_setzen(self, achse):
        if achse == self._hover:
            return
        alt, self._hover = self._hover, achse
        for a in (alt, achse):
            if a in self._actors:
                self._actors[a].prop.color = self._farbe(a)
        self._plotter.render()

    def entfernen(self):
        # Bei Bestaetigen, Abbrechen und Fehler. Danach ist der Viewer wieder
        # ganz normal, kein Filter und kein Cursor bleiben haengen.
        QApplication.instance().removeEventFilter(self)
        for achse in self.ACHSEN:
            self._plotter.remove_actor(f"ellipsoid_pfeil_{achse}", reset_camera=False, render=False)
        self._actors = {}
        self._geometrie = None
        self._ziehen = None
        self._plotter.interactor.unsetCursor()
        self._plotter.render()

    # ---------- Umrechnung Bildschirm <-> Welt ----------

    def _maus_pixel(self, event):
        # VTK zaehlt die Bildzeilen von UNTEN, Qt von oben, und rechnet in
        # echten Pixeln statt in Qt-Punkten
        position = event.position()
        skala = self._plotter.interactor.devicePixelRatioF()
        _, fenster_hoehe = self._plotter.render_window.GetSize()
        return np.array([position.x() * skala, fenster_hoehe - 1 - position.y() * skala])

    def _welt_zu_bild(self, punkt):
        renderer = self._plotter.renderer
        renderer.SetWorldPoint(*punkt, 1.0)
        renderer.WorldToDisplay()
        return np.array(renderer.GetDisplayPoint())

    def _bild_zu_welt(self, pixel, tiefe):
        renderer = self._plotter.renderer
        renderer.SetDisplayPoint(pixel[0], pixel[1], tiefe)
        renderer.DisplayToWorld()
        welt = np.array(renderer.GetWorldPoint())
        return welt[:3] / welt[3]

    def _pfeil_unter_maus(self, pixel):
        if not self._actors:
            return None
        self._picker.InitializePickList()
        for actor in self._actors.values():
            self._picker.AddPickList(actor)
        if not self._picker.Pick(pixel[0], pixel[1], 0, self._plotter.renderer):
            return None
        getroffen = self._picker.GetActor()
        for achse, actor in self._actors.items():
            if actor is getroffen:
                return achse
        return None

    # ---------- Ziehen ----------

    def _ziehen_beginnen(self, griff, pixel):
        if griff == "verschieben":
            # Die Maus bewegt die Mitte in der Bildebene, die durch die Mitte
            # geht. Dafuer die Bildtiefe der Mitte festhalten.
            tiefe = self._welt_zu_bild(self._geometrie["mitte"])[2]
            self._ziehen_start = {"pixel": pixel, "tiefe": tiefe,
                                  "welt": self._bild_zu_welt(pixel, tiefe)}
        else:
            # Pixel pro mm entlang des Pfeils. Einmal beim Klick, waehrend des
            # Ziehens wandert der Pfeil ja mit.
            fuss, richtung = self._pfeile[griff]
            bild_fuss = self._welt_zu_bild(fuss)[:2]
            bild_spitze = self._welt_zu_bild(fuss + richtung * self._pfeil_laenge)[:2]
            pro_mm = (bild_spitze - bild_fuss) / self._pfeil_laenge
            if np.linalg.norm(pro_mm) * self._pfeil_laenge < k.ISOLIEREN_PFEIL_MIN_PIXEL:
                print(f"Arrow '{griff}' points almost straight at the camera, rotate the view to drag it")
                return False
            self._ziehen_start = {"pixel": pixel, "pro_mm": pro_mm}
        self._ziehen = griff
        self._bei_start()
        self._cursor_setzen()
        return True

    def _ziehen_weiter(self, pixel):
        start = self._ziehen_start
        if self._ziehen == "verschieben":
            delta = self._bild_zu_welt(pixel, start["tiefe"]) - start["welt"]
        else:
            pro_mm = start["pro_mm"]
            delta = float(np.dot(pixel - start["pixel"], pro_mm) / np.dot(pro_mm, pro_mm))
        self._bei_ziehen(self._ziehen, delta)

    def _ziehen_beenden(self):
        griff, self._ziehen = self._ziehen, None
        self._ziehen_start = None
        if griff in self._actors:
            self._actors[griff].prop.color = self._farbe(griff)
            self._plotter.render()
        self._cursor_setzen()

    def _cursor_setzen(self):
        interactor = self._plotter.interactor
        if self._ziehen in self.ACHSEN:
            interactor.setCursor(Qt.ClosedHandCursor)
        elif self._ziehen == "verschieben" or self._feststell_gehalten:
            interactor.setCursor(Qt.SizeAllCursor)
        elif self._hover is not None:
            interactor.setCursor(Qt.OpenHandCursor)
        else:
            interactor.unsetCursor()

    # ---------- Ereignisse ----------

    def eventFilter(self, obj, event):
        typ = event.type()

        if typ in (QEvent.KeyPress, QEvent.KeyRelease) and event.key() == Qt.Key_CapsLock:
            if not event.isAutoRepeat():
                self._feststell_gehalten = typ == QEvent.KeyPress
                self._cursor_setzen()
            return False

        # Faellt das Loslassen in ein anderes Fenster, kommt hier nie ein
        # KeyRelease oder MouseButtonRelease an
        if typ == QEvent.WindowDeactivate and obj is self._plotter.interactor.window():
            self._feststell_gehalten = False
            if self._ziehen is not None:
                self._ziehen_beenden()
            self._cursor_setzen()
            return False

        if obj is not self._plotter.interactor or self._geometrie is None:
            return False

        # Der zweite Klick eines Doppelklicks kommt als eigener Typ, sonst
        # wuerde der bei schnellem Nachgreifen am Pfeil die Kamera drehen
        if typ in (QEvent.MouseButtonPress, QEvent.MouseButtonDblClick) and event.button() == Qt.LeftButton:
            pixel = self._maus_pixel(event)
            if self._feststell_gehalten:
                griff = "verschieben"
            else:
                griff = self._pfeil_unter_maus(pixel)
            # Verschlucken, sonst dreht VTK beim Ziehen die Kamera mit. Kein
            # Pfeil getroffen: ganz normal die Kamera drehen.
            return griff is not None and self._ziehen_beginnen(griff, pixel)

        if typ == QEvent.MouseMove:
            pixel = self._maus_pixel(event)
            if self._ziehen is not None:
                self._ziehen_weiter(pixel)
                return True
            # Waehrend die Kamera gedreht wird, nicht nebenbei Pfeile anfaerben
            if event.buttons() == Qt.NoButton:
                self._hover_setzen(self._pfeil_unter_maus(pixel))
                self._cursor_setzen()
            return False

        if typ == QEvent.MouseButtonRelease:
            if self._ziehen is not None and event.button() == Qt.LeftButton:
                self._ziehen_beenden()
                return True
            # Kamera wurde gedreht oder verschoben, Breite und Dicke wieder auf
            # die sichtbare Seite. Erst wenn VTK das Loslassen selbst
            # verarbeitet hat, also im naechsten Durchlauf.
            QTimer.singleShot(0, self._pfeile_setzen)
            return False

        return False
