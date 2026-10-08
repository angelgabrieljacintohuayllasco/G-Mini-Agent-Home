// G-Mini Home - piramide de Pepper: marco imprimible y vista de conjunto.
//
// Las caras son laminas (PET o acrilico) cortadas con las plantillas de
// hardware/templates/. Este marco las sostiene a 45 grados sin pegamento:
//   part = "frame"    marco con ranuras (imprimir boca abajo, sin soportes)
//   part = "assembly" marco + laminas + pantalla (renders)
//
// Medidas por defecto: telefono de 6,1" (b = 60, a = 10). Para otra pantalla
// usa los valores de hardware/templates/README.md, p. ej. tablet de 10,1":
//   openscad -D b=128 -D a=21 -D sheet=0.75 -D 'part="frame"' -o marco.stl pepper_pyramid.scad
//
// Licencia: CC BY-SA 4.0 (ver LICENSE-hardware.md)

part = "assembly";            // [frame, assembly]

b = 60;                       // lado mayor (arriba)
a = 10;                       // lado menor (sobre la pantalla)
sheet = 0.5;                  // espesor de la lamina
slot_clear = 0.35;            // juego de la ranura
bar = 4;                      // ancho de las barras del marco
screen = [72, 152, 8];        // telefono de referencia para el render

$fn = 32;
eps = 0.01;
H = (b - a) / 2;              // altura (caras a 45 grados)

// Plano de una cara: trapecio inclinado 45 grados hacia afuera, del lado -y.
module face_plane(thick) {
  hull() {
    translate([-a / 2, -a / 2 - thick / 2, 0]) cube([a, thick, eps]);
    translate([-b / 2, -b / 2 - thick / 2, H]) cube([b, thick, eps]);
  }
}

// Ranura: la cara engrosada al espesor de la lamina mas el juego.
module slot() {
  face_plane(sheet + slot_clear);
}

module top_ring() {
  translate([0, 0, H - bar]) difference() {
    translate([-b / 2 - bar, -b / 2 - bar, 0]) cube([b + 2 * bar, b + 2 * bar, bar]);
    translate([-b / 2 + bar, -b / 2 + bar, -eps]) cube([b - 2 * bar, b - 2 * bar, bar + 2 * eps]);
  }
}

module bottom_ring() {
  difference() {
    translate([-a / 2 - bar, -a / 2 - bar, 0]) cube([a + 2 * bar, a + 2 * bar, bar]);
    translate([-a / 2 + 0.6, -a / 2 + 0.6, -eps]) cube([a - 1.2, a - 1.2, bar + 2 * eps]);
  }
}

// Aristas de la piramide: postes que unen los dos aros.
module edges() {
  for (r = [0, 90, 180, 270]) rotate(r)
    hull() {
      translate([-a / 2, -a / 2, 0]) cube([bar * 0.8, bar * 0.8, bar], center = true);
      translate([-b / 2, -b / 2, H - bar / 2]) cube([bar, bar, bar], center = true);
    }
}

module frame() {
  difference() {
    union() {
      top_ring();
      bottom_ring();
      edges();
    }
    for (r = [0, 90, 180, 270]) rotate(r) slot();
  }
}

module sheets() {
  for (r = [0, 90, 180, 270]) rotate(r) face_plane(sheet);
}

if (part == "frame") {
  frame();
} else {
  color("#1b2631") translate([-screen[0] / 2, -screen[1] / 2, -screen[2]]) cube(screen);
  color("#3fe0ff") for (r = [0, 90, 180, 270]) rotate(r) translate([-9, -a / 2 - H * 0.75, -0.2]) cube([18, 7, 0.3]);
  color("#e6eef2") frame();
  color("#bfefff", 0.35) sheets();
}
