// G-Mini Home - "puck" parlante con ESP32-S3 y anillo de LEDs.
//
// Cilindro bajo con rejilla superior, anillo WS2812 de 24 LEDs bajo un aro
// difusor, dos botones arriba, microfono al frente y USB-C atras.
//   part = "base"     cuerpo con la cuna del ESP32-S3 DevKitC-1
//   part = "top"      tapa con rejilla del parlante y canal del difusor
//   part = "diffuser" aro difusor (PETG natural o PLA blanco, 100 % relleno)
//   part = "bottom"   fondo a presion con huecos para patas de goma de 10 mm
//   part = "assembly" vista de conjunto (renders)
//
// El INMP441 y el MAX98357A van pegados con cinta doble faz (no tienen
// agujeros de montaje). El anillo LED se pega bajo la tapa, centrado.
//
// Licencia: CC BY-SA 4.0 (ver LICENSE-hardware.md)

part = "assembly";            // [base, top, diffuser, bottom, assembly]

/* [Cuerpo] */
outer_d = 104;
height = 42;                  // alto del cuerpo (sin tapa)
wall = 2.4;
floor_t = 3.2;                // 1,6 mm de piso + 1,6 mm de rebaje para el fondo

/* [Parlante] */
speaker_d = 40;               // parlante de 40 mm, 3-5 W
speaker_mount_d = 44;         // aro donde apoya el parlante

/* [Anillo LED (24 LEDs: 66 / 52 mm)] */
ring_od = 66;
ring_id = 52;
diffuser_w = 8;

/* [Placa] */
board = [25.6, 69];           // ESP32-S3-DevKitC-1 (ancho, largo)
rail_h = 13;                  // alto de la cuna: los pines de los headers no tocan el fondo
ledge = 1.6;                  // escalon donde apoya la placa

/* [Botones y conectores] */
button_d = [12.4, 8.2];       // hablar, modo
usb = [12.5, 6.5];

$fn = 72;
eps = 0.01;
top_t = 3;
groove_d = 2.2;
r_out = outer_d / 2;
r_in = r_out - wall;
diff_r = (ring_od + ring_id) / 4;  // radio medio del anillo
board_y0 = -r_in + 1.5;            // extremo USB de la placa, contra la pared trasera
boss_r = r_in - 3.6;               // los bosses quedan unidos a la pared

module annulus(r1, r2, h) {
  difference() {
    cylinder(r = r2, h = h);
    translate([0, 0, -eps]) cylinder(r = r1, h = h + 2 * eps);
  }
}

module base() {
  difference() {
    union() {
      difference() {
        cylinder(r = r_out, h = height);
        translate([0, 0, floor_t]) cylinder(r = r_in, h = height);
      }
      // Bosses de la tapa a 120 grados, lejos de los botones (90 y 270 grados).
      for (a = [0, 120, 240]) rotate(a) translate([boss_r, 0, 0]) cylinder(d = 8, h = height - top_t);
      // Cuna de la placa: dos rieles con escalon.
      for (s = [-1, 1])
        translate([s * (board[0] / 2 + 1.5) - 1.5, board_y0 + 4, 0]) cube([3, board[1] - 10, floor_t + rail_h]);
    }
    for (a = [0, 120, 240]) rotate(a) translate([boss_r, 0, floor_t + 2]) cylinder(d = 2.6, h = height);
    // Escalon: la placa apoya a rail_h y queda trabada entre los rieles.
    translate([-board[0] / 2 - 0.3, board_y0, floor_t + rail_h - ledge]) cube([board[0] + 0.6, board[1], ledge + 1]);
    // USB-C atras (lado -y), a la altura del conector sobre la cuna.
    translate([0, -r_out + wall / 2, floor_t + rail_h + 2.2]) rotate([90, 0, 0])
      hull() for (x = [-1, 1]) translate([x * (usb[0] - usb[1]) / 2, 0, 0]) cylinder(d = usb[1], h = wall * 3, center = true, $fn = 24);
    // Microfono (INMP441 pegado por dentro, lado +y) y alivio del sonido.
    translate([0, r_out - wall / 2, height * 0.5]) rotate([90, 0, 0]) cylinder(d = 2, h = wall * 3, center = true, $fn = 16);
    // Ranuras de ventilacion/sonido en la parte baja del frente.
    for (i = [-2 : 2]) rotate(i * 7) translate([0, r_out - wall / 2, 8]) rotate([90, 0, 0])
      hull() for (z = [0, 8]) translate([0, z, 0]) cylinder(d = 2.4, h = wall * 3, center = true, $fn = 12);
    // Rebaje inferior donde encaja el fondo.
    translate([0, 0, -eps]) cylinder(r = r_in + 0.8, h = 1.6);
  }
}

module top() {
  difference() {
    union() {
      cylinder(r = r_out, h = top_t);
      // Pestaña que entra en el cuerpo.
      translate([0, 0, -3]) annulus(r_in - 2.1, r_in - 0.3, 3 + eps);
      // Aro de apoyo del parlante.
      translate([0, 0, -4]) annulus(speaker_mount_d / 2 - 0.8, speaker_mount_d / 2 + 1.5, 4 + eps);
    }
    // Rejilla sobre el parlante: anillos concentricos de agujeros.
    for (rr = [6 : 6 : speaker_d / 2 - 4])
      for (k = [0 : floor(2 * PI * rr / 8) - 1])
        rotate(k * 360 / floor(2 * PI * rr / 8)) translate([rr, 0, -eps]) cylinder(d = 2.6, h = top_t + 2 * eps, $fn = 12);
    translate([0, 0, -eps]) cylinder(d = 3, h = top_t + 1, $fn = 12);
    // Canal del difusor desde arriba...
    translate([0, 0, top_t - groove_d]) annulus(diff_r - diffuser_w / 2 - 0.2, diff_r + diffuser_w / 2 + 0.2, groove_d + eps);
    // ...y ventanas hacia el anillo LED, con tres rayos que sostienen el centro.
    difference() {
      translate([0, 0, -eps]) annulus(diff_r - diffuser_w / 2 + 0.8, diff_r + diffuser_w / 2 - 0.8, top_t);
      for (a = [90, 210, 330]) rotate(a) translate([0, -2, -1]) cube([r_out, 4, top_t + 2]);
    }
    // Botones entre el anillo y el borde.
    translate([0, r_out - 11, -eps]) cylinder(d = button_d[0], h = top_t + 2 * eps);
    translate([0, -(r_out - 11), -eps]) cylinder(d = button_d[1], h = top_t + 2 * eps);
    // Tornillos avellanados.
    for (a = [0, 120, 240]) rotate(a) translate([boss_r, 0, -eps]) {
      cylinder(d = 2.9, h = top_t + 1);
      translate([0, 0, top_t - 1.6 + 2 * eps]) cylinder(d1 = 2.9, d2 = 5.6, h = 1.6);
    }
  }
}

module diffuser() {
  annulus(diff_r - diffuser_w / 2, diff_r + diffuser_w / 2, groove_d);
  translate([0, 0, groove_d]) difference() {
    cylinder(r1 = diff_r + diffuser_w / 2, r2 = diff_r + diffuser_w / 2 - 1, h = 1.2);
    translate([0, 0, -eps]) cylinder(r1 = diff_r - diffuser_w / 2, r2 = diff_r - diffuser_w / 2 + 1, h = 1.2 + 2 * eps);
  }
}

module bottom() {
  difference() {
    cylinder(r = r_in + 0.6, h = 1.6);
    // Va a presion en el rebaje del cuerpo (o con tres puntos de pegamento).
    for (a = [0 : 90 : 270]) rotate(a + 45) translate([r_in - 12, 0, 0.8]) cylinder(d = 10.5, h = 1);
  }
}

if (part == "base") {
  base();
} else if (part == "top") {
  top();
} else if (part == "diffuser") {
  diffuser();
} else if (part == "bottom") {
  bottom();
} else {
  // Vista explotada.
  color("#e9eef1") base();
  color("#2b3a44") translate([0, 0, height + 12]) top();
  color("#7fe8ff") translate([0, 0, height + 12 + top_t - groove_d + 4]) diffuser();
  color("#c9d3da") translate([0, 0, -12]) bottom();
  color("#1b5e8a") translate([-board[0] / 2, board_y0, floor_t + rail_h - ledge]) cube([board[0], board[1], 1.6]);
  color("#0f2533") translate([0, r_out - 11, height + 12 + top_t]) cylinder(d = button_d[0] - 0.8, h = 3);
  color("#5b6b7b") translate([0, -(r_out - 11), height + 12 + top_t]) cylinder(d = button_d[1] - 0.8, h = 2);
}
