import pyvista as p_v
import numpy as np
from pathlib import Path
import trimesh
from scipy.spatial import cKDTree
from PIL import Image


def hole_textur_bild(material):
    if material.image is not None:
        return material.image.convert("RGB")

    farbe = getattr(material, "diffuse", None)
    if farbe is None:
        farbe = getattr(material, "main_color", [200, 200, 200, 255])
    farbe_rgb = tuple(int(c) for c in farbe[:3])
    return Image.new("RGB", (8, 8), farbe_rgb)


def load_teilmeshe_mit_textur(obj_pfad: str):
    geladen = trimesh.load(str(obj_pfad[0]), process=False)
 
    if isinstance(geladen, trimesh.Scene):
        teile = list(geladen.geometry.values())
    else:
        teile = [geladen]
 
    count_vertices = 0
    ergebnis = []
    for tmesh in teile:
        if tmesh.visual.uv is None:
            print(f"Teilmesh ohne UV-Koordinaten gefunden.")
            continue

        faces_vtk = np.hstack(
            [np.full((len(tmesh.faces), 1), 3), tmesh.faces]
        ).astype(np.int64)

        count_vertices += len(tmesh.vertices)
        pv_mesh = p_v.PolyData(tmesh.vertices, faces_vtk)
        pv_mesh.active_texture_coordinates = tmesh.visual.uv
        pv_mesh = pv_mesh.compute_normals(point_normals=True, auto_orient_normals=True)
 
        bild_array = np.array(hole_textur_bild(tmesh.visual.material))
        tex = p_v.Texture(bild_array)
 
        ergebnis.append((pv_mesh, tex))
 
    print(f"Erfolgreich geladen, {count_vertices} Vertices gesamt.")
    return ergebnis
 

def zeige_mit_texturen(plotter: p_v.Plotter, teile: list) -> None:
    for teil, tex in teile:
        plotter.add_mesh(teil, texture=tex)
 
 
def transformiere_teile(teile: list, transform_matrix) -> list:
    return [(teil.transform(transform_matrix, inplace=False), tex) for teil, tex in teile]
 
 
def clippe_teile(teile: list, zylinder: p_v.PolyData) -> list:
    ergebnis = []
    for teil, tex in teile:
        geschnitten = teil.clip_surface(zylinder, invert = False)
        if geschnitten.n_points > 0:
            ergebnis.append((geschnitten, tex))
    return ergebnis


def pick_finger_point(plotter, mesh):
    punkte = []
    print("Bitte Wählen Sie den Fingernagel des verlezten Fingers")

    def callback(point, picker):
        punkte.append(np.array(point))
        print(f"Punkt {len(punkte)} gewählt bei: {point}")

        if len(punkte) < 2:
            print("Bitte jetzt den Fingernagel des Nachbar-Fingers anklicken")
        else:
            plotter.disable_picking()
            plotter.close()

    plotter.enable_point_picking(
        callback=callback,
        use_picker=True,
        show_point=True,
        color="red",
        point_size=15,
    )

    plotter.show()

    return punkte[0], punkte[1]


def rotationsmatrix(seed: np.ndarray, second_finger: np.ndarray, centroid: np.ndarray) -> np.ndarray:
    
    v = second_finger - seed
    v_hat = v / np.linalg.norm(v)
 
    m = (seed + second_finger) / 2 - centroid
 
    m_parallel = np.dot(m, v_hat) * v_hat
    m_perp = m - m_parallel
    m_perp_norm = np.linalg.norm(m_perp)
 
    if m_perp_norm < 1e-8:
        beliebige = np.array([0, 0, 1.0]) if abs(v_hat[2]) < 0.9 else np.array([1.0, 0, 0])
        m_perp_hat = beliebige - np.dot(beliebige, v_hat) * v_hat
        m_perp_hat /= np.linalg.norm(m_perp_hat)
    else:
        m_perp_hat = m_perp / m_perp_norm
 
    lokale_basis = np.column_stack([v_hat, m_perp_hat, np.cross(v_hat, m_perp_hat)])
    ziel_basis = np.column_stack([[1, 0, 0], [0, 0, 1], np.cross([1, 0, 0], [0, 0, 1])])
 
    return ziel_basis @ lokale_basis.T
 
 
def richte_hand_aus(mesh, verlezter_finger: np.ndarray, second_finger: np.ndarray):
    ist_pyvista = isinstance(mesh, p_v.PolyData)
    centroid = np.asarray(mesh.points if ist_pyvista else mesh.centroid, dtype=float)

    if ist_pyvista:
        centroid = mesh.points.mean(axis=0)
    else:
        centroid = mesh.centroid
 
    R = rotationsmatrix(verlezter_finger, second_finger, centroid)
 
    transform = np.eye(4)
    transform[:3, :3] = R
    transform[:3, 3] = -R @ centroid
 
    if ist_pyvista:
        ausgerichtetes_mesh = mesh.transform(transform, inplace=False)
    else:
        ausgerichtetes_mesh = mesh.copy()
        ausgerichtetes_mesh.apply_transform(transform)
 
    seed_neu = R @ (verlezter_finger - centroid)
    second_finger_neu = R @ (second_finger - centroid)
 
    return ausgerichtetes_mesh, seed_neu, second_finger_neu, transform

def djikstra_und_tiefster_punkt(mesh: p_v.PolyData, verlezter_finger: np.ndarray, second_finger: np.ndarray):
    idx_a = mesh.find_closest_point(verlezter_finger)
    idx_b = mesh.find_closest_point(second_finger)
 
    pfad_mesh = mesh.geodesic(idx_a, idx_b)
    pfad_punkte = pfad_mesh.points
 
    tiefster_index = np.argmin(pfad_punkte[:, 2])
    tiefster_punkt = np.array(pfad_punkte[tiefster_index])
 
    kugel_radius = mesh.length * 0.01  # relativ zur Mesh-Groesse, damit sie immer sichtbar passt
    kugel = p_v.Sphere(radius=kugel_radius, center=tiefster_punkt)
 
    return tiefster_punkt, pfad_mesh, kugel


def rotationsmatrix_a_nach_b(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    #Verwendete Rodriques Rotationsformel.
    a = a / np.linalg.norm(a)
    b = b / np.linalg.norm(b)
    achse = np.cross(a, b)
    sin_winkel = np.linalg.norm(achse)
    cos_winkel = np.dot(a, b)
 
    if sin_winkel < 1e-8:
        if cos_winkel > 0:
            return np.eye(3)
        beliebig = np.array([1.0, 0, 0]) if abs(a[0]) < 0.9 else np.array([0, 1.0, 0])
        achse2 = np.cross(a, beliebig)
        achse2 /= np.linalg.norm(achse2)
        K = np.array([[0, -achse2[2], achse2[1]], [achse2[2], 0, -achse2[0]], [-achse2[1], achse2[0], 0]])
        return np.eye(3) + 2 * K @ K
 
    achse = achse / sin_winkel
    K = np.array([[0, -achse[2], achse[1]], [achse[2], 0, -achse[0]], [-achse[1], achse[0], 0]])
    return np.eye(3) + K * sin_winkel + K @ K * (1 - cos_winkel)


def finger_normale(mesh: p_v.PolyData, verletzter_finger: np.ndarray, anzahl_punkte: int = 2000) -> np.ndarray:

    if anzahl_punkte > mesh.n_points:
        raise ValueError(
            f"anzahl_punkte ({anzahl_punkte}) ist größer als die Gesamtzahl "
            f"der Vertices im Mesh ({mesh.n_points})."
        )
 
    baum = cKDTree(mesh.points)
    _, indices = baum.query(verletzter_finger, k = anzahl_punkte)
    nahe_punkte = mesh.points[indices]
 
    zentriert = nahe_punkte - nahe_punkte.mean(axis=0)
    kovarianz = np.cov(zentriert.T)
    eigenwerte, eigenvektoren = np.linalg.eigh(kovarianz)
 
    normale = eigenvektoren[:, np.argmax(eigenwerte)]
 
    # Vorzeichen festlegen: Achse soll vom Hand-Schwerpunkt WEG zeigen
    # (Finger zeigen anatomisch immer nach aussen, unabhaengig von der Pose)
    hand_schwerpunkt = mesh.points.mean(axis=0)
    richtung_vom_zentrum = verletzter_finger - hand_schwerpunkt

    if np.dot(normale, richtung_vom_zentrum) < 0:
        normale = -normale
 
    return normale, nahe_punkte, nahe_punkte.mean(axis = 0)


def erstelle_schnitt_ellipsoid(
        lokales_zentrum: np.ndarray, 
        normale: np.ndarray,
        verwendete_punkte: np.ndarray, 
        tiefster_punkt: np.ndarray,
        radius_faktor = 2.0,
        laengen_faktor = 0.8,
        unterschreitung: float = 0.6) -> p_v.PolyData:

    if abs(normale[2]) < 1e-8:
        raise ValueError(
            "Fingerachse verläuft horizontal zur Ellipsoid-Ausrichtung kann nicht eindeutig auf eine Höhe z bezogen werden."
        )
 
    t_boden = (tiefster_punkt[2] - lokales_zentrum[2]) / normale[2]
 
    relative_punkte = verwendete_punkte - lokales_zentrum
    axiale_projektionen = relative_punkte @ normale
    radiale_komponenten = relative_punkte - np.outer(axiale_projektionen, normale)
    radius_original = np.linalg.norm(radiale_komponenten, axis=1).max()
 
    t_oben = axiale_projektionen.max()
    if t_oben <= t_boden:
        raise ValueError(
            "Der Wurzel-Punkt liegt auf oder ueber der obersten PCA-Nachbarschaft - "
            "pruefe tiefster_punkt/lokales_zentrum auf Plausibilitaet."
        )
 
    original_laenge = t_oben - t_boden
    aequator_radius = radius_faktor * radius_original
    halbe_hauptachse = laengen_faktor * original_laenge
    unten_spitze_t = t_boden - unterschreitung * original_laenge
    zentrum_t = unten_spitze_t + halbe_hauptachse
    ellipsoid_mitte = lokales_zentrum + normale * zentrum_t
 
    # Ellipsoid entlang X bauen (Standard-Ausrichtung von
    # ParametricEllipsoid), dann auf 'normale' drehen + verschieben
    basis_ellipsoid = p_v.ParametricEllipsoid(
        xradius=halbe_hauptachse, yradius=aequator_radius, zradius=aequator_radius
    )
    R = rotationsmatrix_a_nach_b(np.array([1.0, 0, 0]), normale)
    transform = np.eye(4)
    transform[:3, :3] = R
    transform[:3, 3] = ellipsoid_mitte
 
    return basis_ellipsoid.transform(transform, inplace = False)


def berechne_finale_ausrichtung(normale: np.ndarray, achsen_punkt: np.ndarray, kerben_punkt: np.ndarray) -> np.ndarray:
    R1 = rotationsmatrix_a_nach_b(normale, np.array([0, 0, 1.0]))
    achsen_punkt_rot = R1 @ achsen_punkt
    kerben_punkt_rot = R1 @ kerben_punkt

    naechster_punkt = np.array([achsen_punkt_rot[0], achsen_punkt_rot[1], kerben_punkt_rot[2]])
    kerben_verschoben = kerben_punkt_rot - naechster_punkt

    theta = np.arctan2(kerben_verschoben[1], kerben_verschoben[0])
    c, s = np.cos(-theta), np.sin(-theta)
    R3 = np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]])

    R_gesamt = R3 @ R1
    verschiebung = -R3 @ naechster_punkt

    transform = np.eye(4)
    transform[:3, :3] = R_gesamt
    transform[:3, 3] = verschiebung
    return transform


def speichere_isolierten_finger(scan_ordner_pfad: str, texture_teile_isoliert: list) -> Path:
    scan_ordner = Path(scan_ordner_pfad)
    originale_scans_ordner = scan_ordner.parent
    patienten_ordner = originale_scans_ordner.parent
 
    isolierte_scans_ordner = patienten_ordner / "isolierte_scans"
    isolierte_scans_ordner.mkdir(exist_ok=True)
 
    ziel_name = scan_ordner.name + "_isoliert"
    ziel_ordner = isolierte_scans_ordner / ziel_name
    return_ordner = ziel_ordner
    ziel_ordner.mkdir(exist_ok=True)
 
    save_path = ziel_ordner / f"{ziel_name}.obj"
 
    geometrien = {}
    for i, (pv_mesh, tex) in enumerate(texture_teile_isoliert):
        dreiecks_mesh = pv_mesh.triangulate()
        faces = dreiecks_mesh.faces.reshape(-1, 4)[:, 1:]
 
        if dreiecks_mesh.active_texture_coordinates is None:
            print(f"Warnung: Teil {i} hat keine Textur-Koordinaten, wird uebersprungen.")
            continue
 
        uv = np.asarray(dreiecks_mesh.active_texture_coordinates)
        bild = Image.fromarray(tex.to_array())
 
        tmesh = trimesh.Trimesh(vertices=dreiecks_mesh.points, faces=faces, process=False)
        tmesh.visual = trimesh.visual.texture.TextureVisuals(uv=uv, image=bild)
        geometrien[f"teil_{i}"] = tmesh
 
    if not geometrien:
        raise ValueError("Keine gueltigen texturierten Teile zum Speichern gefunden.")
 
    scene = trimesh.Scene(geometrien)
    scene.export(str(save_path))
 
    print(f"Isolierter Finger ({len(geometrien)} Materialien) gespeichert unter: {save_path}")
    return return_ordner

###!!! Der Spaß ist jetzt n Generator, also mit "for _ in isoltae_finer(...): \n\tab pass" aufrufen!!!

def isolate_finger(path: str,
                plotter = None,
                radius_faktor = 2.0,
                laengen_faktor = 0.8,
                unterschreitung = 0.45,
                zeige_zwischenschritte = True):
    path = Path(path)
    obj_file = list(path.glob("*.obj"))

    texture_teile = load_teilmeshe_mit_textur(obj_file)
    hand_mesh = p_v.merge([teil for teil, tex in texture_teile])

    if plotter is not None:
        plotter.clear()
        zeige_mit_texturen(plotter, texture_teile)
        plotter.reset_camera()

        punkte = []
        def punkt_callback(point, picker):
            punkte.append(np.array(point))
            print(f"Punkt {len(punkte)} gewählt bei: {point}")

        plotter.enable_point_picking(
            callback=punkt_callback, use_picker=True, show_point=True, color="red", point_size=15
        )

        yield   # Nutzer klickt jetzt 2 Punkte, dann "Fertig markiert"/"Weiter"

        plotter.disable_picking()

        if len(punkte) < 2:
            raise ValueError("Nicht genug Punkte gewählt - bitte 2 Punkte anklicken, bevor weitergemacht wird.")

        hurt_finger, second_finger = punkte[0], punkte[1]
    else:
        my_p_v_plotter = p_v.Plotter()
        zeige_mit_texturen(my_p_v_plotter, texture_teile)
        hurt_finger, second_finger = pick_finger_point(my_p_v_plotter, hand_mesh)
    if (hurt_finger is None) or (second_finger is None):
        raise ValueError("Ungenügend Fingerspitzen gewählt")
    
    print("Finger korrekt gewählt.")
    print(f"Koordinaten des verlzten Fingers: {hurt_finger}")
    print(f"Finger des benachbarten Fingers: {second_finger}")

    
    
    #Handausrichten
    hand_ausgerichtet, hurt_finger, second_finger, transformierungsmatrix = richte_hand_aus(hand_mesh, hurt_finger, second_finger)
    texture_teile = transformiere_teile(texture_teile, transformierungsmatrix) 

    #Djikstra & gleichzeitig tiefster Punkt (still, kein Zwischenschritt mehr)
    tiefster_punkt, pfad_mesh, kugel = djikstra_und_tiefster_punkt(hand_ausgerichtet, hurt_finger, second_finger)

    #Normale mit PCA (still, kein Zwischenschritt mehr)
    normale, verwendete_vertices, avg_point_of_hurt_finger = finger_normale(hand_ausgerichtet, hurt_finger, 3000)

    #Einziger verbleibender Zwischenschritt: Ellipsoid live einstellbar.
    if zeige_zwischenschritte and plotter is not None:
        plotter.clear()
        zeige_mit_texturen(plotter, texture_teile)
        plotter.reset_camera()


        empfangene_werte = yield {
            "avg_point_of_hurt_finger": avg_point_of_hurt_finger,
            "normale": normale,
            "verwendete_vertices": verwendete_vertices,
            "tiefster_punkt": tiefster_punkt,
        }
        if empfangene_werte is not None:
            radius_faktor = empfangene_werte.get("radius_faktor", radius_faktor)
            laengen_faktor = empfangene_werte.get("laengen_faktor", laengen_faktor)
            unterschreitung = empfangene_werte.get("unterschreitung", unterschreitung)

    elif zeige_zwischenschritte:
        ellipsoid_vorschau = erstelle_schnitt_ellipsoid(
            avg_point_of_hurt_finger, normale, verwendete_vertices, tiefster_punkt,
            radius_faktor=radius_faktor, laengen_faktor=laengen_faktor, unterschreitung=unterschreitung
        )
        ellipsoid_plotter = p_v.Plotter()
        zeige_mit_texturen(ellipsoid_plotter, texture_teile)
        ellipsoid_plotter.add_mesh(ellipsoid_vorschau, color="cyan", opacity=0.3)
        ellipsoid_plotter.show()

    #Schnittellipsoid bestimmen (mit den finalen, evtl. per Slider angepassten Parametern)
    ellipsoid = erstelle_schnitt_ellipsoid(
        avg_point_of_hurt_finger, 
        normale, 
        verwendete_vertices, 
        tiefster_punkt,
        radius_faktor = radius_faktor,
        laengen_faktor = laengen_faktor,
        unterschreitung = unterschreitung)

    #Cutten
    finger_isoliert = hand_ausgerichtet.clip_surface(ellipsoid, invert = False)
    texture_teile_isoliert = clippe_teile(texture_teile, ellipsoid)

    #Finale Ausrichtung: Fingerachse -> Z-Achse, Kerbenpunkt -> +X-Achse
    finale_transform = berechne_finale_ausrichtung(normale, avg_point_of_hurt_finger, tiefster_punkt)
    texture_teile_isoliert = transformiere_teile(texture_teile_isoliert, finale_transform)

    if plotter is not None:
        plotter.clear()
        zeige_mit_texturen(plotter, texture_teile_isoliert)
        plotter.reset_camera()
    else:
        iso_finger_plotter = p_v.Plotter()
        zeige_mit_texturen(iso_finger_plotter, texture_teile_isoliert)
        iso_finger_plotter.show()

    #Finger speichern
    markierungsordner = speichere_isolierten_finger(path, texture_teile_isoliert)

    return markierungsordner

# path_string = input("Pfad eingeben:")
# isolate_finger(path_string)










