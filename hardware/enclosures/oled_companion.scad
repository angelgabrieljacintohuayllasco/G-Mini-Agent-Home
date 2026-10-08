// G-Mini Home - carcasa del compañero OLED ("cabecita robot").
//
// Entra una OLED de 0,96" (o SH1106 de 1,3" cambiando oled_*), un ESP32-S3
// DevKitC-1 o un Arduino Nano, un INMP441, un MAX98357A, un parlante de 28-40 mm
// y dos pulsadores de 12 mm. Se imprime en dos piezas sin soportes:
//   part = "shell"    cuerpo con la ventana de los ojos (boca abajo sobre la cara)
//   part = "back"     tapa trasera con rejilla del parlante y salida USB
//   part = "assembly" vista de conjunto (solo para renders)
//
// Exportar:  openscad -D 'part="shell"' -o oled_companion_shell.stl oled_companion.scad
//
// Licencia: CC BY-SA 4.0 (ver LICENSE-hardware.md)

part = "assembly";            // [shell, back, assembly]

/* [Cuerpo] */
body = [78, 62, 48];          // ancho, alto, profundidad exteriores (mm)
corner_r = 14;                // radio de las esquinas vistas de frente
edge_r = 4;                   // redondeo de los cantos
wall = 2.2;

/* [OLED] */
oled_pcb = [27.6, 28.0];      // placa del modulo (mide la tuya)
oled_pcb_t = 1.7;             // espesor de la placa
oled_glass = [26.8, 19.6];    // vidrio
oled_glass_dy = 2.6;          // desplazamiento del vidrio hacia arriba respecto del centro de la placa
oled_window = [23.6, 12.6];   // abertura visible (zona activa de 21,7 x 10,9 + margen)
oled_center_z = 7;            // altura del centro de la pantalla sobre el centro del cuerpo

/* [Botones y audio] */
talk_d = 12.4;                // agujero del boton grande (capuchon de 12 mm)
mode_d = 6.6;                 // agujero del boton chico
mic_d = 2.2;
speaker_d = 40;               // parlante en la tapa trasera
usb = [12.5, 6.5];            // abertura USB-C / micro-USB en la tapa

/* [Tornillos] */
screw_d = 2.6;                // M2,5 autorroscante en el cuerpo
screw_head_d = 5.2;
boss_d = 7;

/* [Detalle] */
antenna = true;
$fn = 48;

eps = 0.01;
inner = [body[0] - 2 * wall, body[1] - 2 * wall];
lid_t = 2.4;
boss_inset = 7.5;

// Caja redondeada hecha con hull() de esferas y cilindros (rapida en CGAL).
module rounded_box(size, r, e) {
  hull() {
    for (x = [-1, 1], y = [-1, 1]) {
      translate([x * (size[0] / 2 - r), y * (size[1] / 2 - r), e])
        cylinder(r = r, h = size[2] - 2 * e);
      translate([x * (size[0] / 2 - r), y * (size[1] / 2 - r), 0])
        cylinder(r = r - e, h = size[2]);
    }
  }
}

module body_solid() {
  rounded_box([body[0], body[1], body[2]], corner_r, edge_r);
}

module cavity() {
  translate([0, 0, wall])
    rounded_box([inner[0], inner[1], body[2]], corner_r - wall, edge_r * 0.6);
}

module boss_positions() {
  for (x = [-1, 1], y = [-1, 1])
    translate([x * (inner[0] / 2 - boss_inset), y * (inner[1] / 2 - boss_inset), 0]) children();
}

// El cuerpo se modela con la cara apoyada en z = 0 (asi se imprime).
module shell() {
  difference() {
    union() {
      difference() {
        body_solid();
        cavity();
      }
      // Bosses para los tornillos de la tapa.
      boss_positions()
        translate([0, 0, wall - eps]) cylinder(d = boss_d, h = body[2] - wall - lid_t + eps);
      // Marco que sostiene la placa de la OLED contra la cara.
      translate([0, oled_center_z - oled_glass_dy, wall - eps])
        difference() {
          translate([-(oled_pcb[0] + 3.2) / 2, -(oled_pcb[1] + 3.2) / 2, 0])
            cube([oled_pcb[0] + 3.2, oled_pcb[1] + 3.2, oled_pcb_t + 2.2]);
          translate([-(oled_pcb[0] + 0.4) / 2, -(oled_pcb[1] + 0.4) / 2, -eps])
            cube([oled_pcb[0] + 0.4, oled_pcb[1] + 0.4, oled_pcb_t + 3]);
        }
    }
    // Ventana de los ojos con chaflan exterior.
    translate([0, oled_center_z, -eps])
      hull() {
        translate([-oled_window[0] / 2, -oled_window[1] / 2, 0]) cube([oled_window[0], oled_window[1], wall + 2 * eps]);
        translate([-(oled_window[0] + 2.4) / 2, -(oled_window[1] + 2.4) / 2, 0]) cube([oled_window[0] + 2.4, oled_window[1] + 2.4, eps]);
      }
    // Rebaje para el vidrio (queda al ras del interior de la cara).
    translate([-(oled_glass[0] + 0.6) / 2, oled_center_z - (oled_glass[1] + 0.6) / 2, wall - 0.8])
      cube([oled_glass[0] + 0.6, oled_glass[1] + 0.6, 1]);
    // Botones en la parte de arriba (lado +y).
    translate([-12, body[1] / 2 - wall / 2, body[2] * 0.55]) rotate([-90, 0, 0])
      cylinder(d = talk_d, h = wall * 3, center = true);
    translate([12, body[1] / 2 - wall / 2, body[2] * 0.55]) rotate([-90, 0, 0])
      cylinder(d = mode_d, h = wall * 3, center = true);
    // Microfono: agujero en la cara, abajo al centro, y "sonrisa" decorativa.
    translate([0, -body[1] / 2 + 13, -eps]) cylinder(d = mic_d, h = wall * 3);
    translate([0, -body[1] / 2 + 13, wall - 0.6]) cylinder(d = 9, h = 1);
    // Agujeros guia de los tornillos.
    boss_positions() translate([0, 0, wall + 3]) cylinder(d = screw_d, h = body[2]);
  }
  if (antenna) {
    translate([-14, body[1] / 2 - 1, body[2] * 0.35]) rotate([-90, 0, -12]) {
      cylinder(d = 3.2, h = 12);
      translate([0, 0, 12]) sphere(d = 7);
    }
  }
}

module back() {
  lip = 1.6;
  difference() {
    union() {
      translate([0, 0, 0]) rounded_box([body[0] - 0.4, body[1] - 0.4, lid_t], corner_r - 0.2, 0.8);
      // Pestaña que entra en el cuerpo y centra la tapa.
      difference() {
        rounded_box([inner[0] - 0.5, inner[1] - 0.5, lid_t + 3], corner_r - wall - 0.25, 0.5);
        translate([0, 0, -eps]) rounded_box([inner[0] - 0.5 - 2 * lip, inner[1] - 0.5 - 2 * lip, lid_t + 4], corner_r - wall - lip, 0.4);
        // Huecos de los bosses.
        boss_positions() translate([0, 0, -eps]) cylinder(d = boss_d + 1, h = lid_t + 4);
      }
    }
    // Rejilla del parlante: ranuras (mas livianas para CGAL que cientos de agujeros).
    for (i = [-3:3])
      translate([i * 5, 6, -eps])
        hull() {
          translate([0, -sqrt(max(1, pow(speaker_d / 2 - 3, 2) - pow(i * 5, 2))) + 3, 0]) cylinder(d = 2.4, h = lid_t + 5, $fn = 16);
          translate([0, sqrt(max(1, pow(speaker_d / 2 - 3, 2) - pow(i * 5, 2))) - 3, 0]) cylinder(d = 2.4, h = lid_t + 5, $fn = 16);
        }
    // USB.
    translate([0, -inner[1] / 2 + 6, -eps])
      hull() for (x = [-1, 1]) translate([x * (usb[0] - usb[1]) / 2, 0, 0]) cylinder(d = usb[1], h = lid_t + 5, $fn = 24);
    // Tornillos con avellanado.
    boss_positions() {
      translate([0, 0, -eps]) cylinder(d = screw_d + 0.4, h = lid_t + 5);
      translate([0, 0, -eps]) cylinder(d1 = screw_head_d, d2 = screw_d + 0.4, h = 1.6);
    }
  }
}

module oled_mock() {
  color("#1b5e8a") translate([-oled_pcb[0] / 2, -oled_pcb[1] / 2, 0]) cube([oled_pcb[0], oled_pcb[1], oled_pcb_t]);
  color("#05080a") translate([-oled_glass[0] / 2, oled_glass_dy - oled_glass[1] / 2, -1.2]) cube([oled_glass[0], oled_glass[1], 1.2]);
  // Ojos encendidos (dos rectangulos redondeados, como en la pantalla real).
  color("#3fe0ff") for (x = [-1, 1])
    translate([x * 5.6, oled_glass_dy, -1.6])
      hull() for (dx = [-1, 1], dy = [-1, 1]) translate([dx * 3.2, dy * 3.2, 0]) cylinder(r = 1.2, h = 0.4, $fn = 16);
}

if (part == "shell") {
  shell();
} else if (part == "back") {
  back();
} else {
  // Conjunto: cara hacia -y (la vista frontal de OpenSCAD) y la parte de arriba hacia +z.
  rotate([0, 0, 180]) rotate([90, 0, 0]) {
    color("#eef2f4") shell();
    translate([0, oled_center_z - oled_glass_dy, wall + 1.2]) oled_mock();
    color("#cfd8dd") translate([0, 0, body[2] + 6]) mirror([0, 0, 1]) back();
  }
}
