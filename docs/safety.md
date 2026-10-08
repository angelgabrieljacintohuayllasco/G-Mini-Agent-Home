# Seguridad

Lee esta página antes de construir. La mayoría de las variantes trabajan con
5 V de un cargador USB y son seguras; los riesgos reales están en los relés con
220 V, las baterías de litio, el agua cerca de la electricidad y los vidrios y
solventes de los hologramas.

## Tensión de red (relés)

- Los relés de los módulos para Arduino/ESP32 pueden conmutar 220 V, pero el
  **cableado de 220 V es peligroso**: una descarga puede matar y un mal empalme
  puede iniciar un incendio.
- Desenchufa todo antes de tocar los bornes. Usa caja cerrada (nada de
  protoboard con 220 V), cable de la sección adecuada, terminales con
  aislamiento, fusible y alivio de tensión en los cables.
- Respeta las distancias del módulo: no apoyes los bornes de 220 V sobre metal
  ni cerca de la placa del ESP32.
- Si no tienes experiencia, usa solo cargas de 5-12 V (tiras LED, ventiladores)
  o un enchufe inteligente comercial.
- `relay.set` pasa por la política de aprobaciones de G-Mini: no la desactives
  para cargas peligrosas (estufas, calentadores, bombas).

## Baterías de litio

- Usa celdas 18650 o LiPo con circuito de protección y un cargador para litio
  (TP4056 con protección, o un power bank). Nunca cargues una celda directa
  desde 5 V.
- No perfores, dobles ni aplastes baterías; si una se hincha, desconéctala y
  llévala a un punto de reciclaje.
- No dejes cargando sin supervisión dentro de carcasas cerradas de PLA: el PLA
  se deforma a ~60 °C.

## Herramientas y armado

- **Cautín**: superficie no inflamable, soporte, ventilación (el humo del
  flux irrita) y lávate las manos después de soldar (el estaño puede tener
  plomo).
- **Pistola de silicona**: la punta y la silicona queman (más de 150 °C).
  No la uses sobre cables de 220 V como aislante.
- **Cutter y acrílico**: regla metálica, corte hacia afuera del cuerpo, varias
  pasadas suaves. Lentes de protección al romper acrílico por la marca.
- **Impresora 3D**: no la dejes sola en las primeras capas; ventila si
  imprimes ABS o ASA.

## Agua, niebla y humo (hologramas)

- Los nebulizadores ultrasónicos funcionan en agua: alimenta siempre con una
  **fuente de 12/24 V de baja tensión** y deja la fuente de 220 V lejos del
  depósito y por encima del nivel del agua.
- Usa agua destilada: el agua de caño deja polvo blanco (minerales) en todo.
- Mantén proyectores, laptops y placas fuera del alcance de la niebla y de
  posibles derrames. Un trapo absorbente bajo el depósito ayuda.
- Máquinas de humo: el fluido de glicol irrita las vías respiratorias y activa
  detectores de humo; ventila la sala. El **hielo seco** desplaza el oxígeno:
  nunca en espacios cerrados ni en contacto con la piel (quema por frío).

## LCD transparente

- El vidrio de los LCD se rompe en astillas muy filosas: guantes anticorte y
  lentes durante todo el desarme.
- **Retroiluminación**: los monitores viejos con CCFL (tubos) tienen
  inversores de alta tensión (más de 1000 V) que retienen carga; desenchufa,
  espera varios minutos y no toques el inversor. Los tubos contienen mercurio:
  no los rompas y llévalos a reciclaje.
- **Polarizador**: para despegar adhesivos usa calor suave (secador de pelo) o
  alcohol isopropílico. **No uses acetona sobre el vidrio ni sobre plásticos**:
  disuelve los polarizadores y el acrílico. Trabaja ventilado y lejos de
  llamas (el alcohol es inflamable).
- No presiones el vidrio del LCD sin su marco: se agrieta y deja de funcionar.

## Ventiladores POV y piezas giratorias

- Las aspas giran a cientos de RPM: usa siempre la cúpula o protección,
  fíjalos firmes a la pared o a una base pesada y mantenlos fuera del alcance
  de niños y mascotas.
- Los proyectos volumétricos de barrido requieren equilibrado y una cubierta
  transparente cerrada: una pieza que se suelta a alta velocidad es un
  proyectil.

## Láser y proyectores

- No mires directo al haz de un proyector ni de un láser; en cortinas de humo
  apunta la proyección por encima de la altura de los ojos.

## Red y tokens

- Cada dispositivo tiene su propio token: si lo pierdes, lo regalas o lo
  desarmas, **revócalo** en Ajustes > Dispositivos.
- En el ESP32 el token se guarda en la NVS sin cifrar (lo puede leer quien
  tenga la placa en la mano). Para producción activa el cifrado de flash y de
  NVS de ESP-IDF; para casa, revocar alcanza.
- Las direcciones `https://` en el ESP32 cifran la conexión pero **no
  verifican el certificado** del servidor. Úsalas solo con tu propio proxy y
  prefiere la red local o una VPN.
- Con la palabra de activación encendida, frases cortas de lo que se dice cerca
  viajan a tu servidor G-Mini (no a terceros). Avisa a quienes vivan contigo.
- No expongas el puerto 8765 a internet ni actives "todas las redes" en una
  WiFi pública.
