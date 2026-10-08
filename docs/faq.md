# Preguntas frecuentes

**¿Qué es G-Mini Home?**
El compañero físico de G-Mini Agent: una carita que escucha y responde. El
"cerebro" (el agente, la memoria, las tareas y el control de la PC) sigue en tu
PC o en tu servidor; el dispositivo es la cara, el micrófono y el parlante.

**¿Necesito internet?**
Solo lo que necesite tu G-Mini (por ejemplo, el proveedor de IA). Los
dispositivos hablan únicamente con tu G-Mini, en tu red.

**¿Funciona sin la PC prendida?**
Las variantes WiFi y la Raspberry Pi necesitan un G-Mini encendido en algún
lado. Si quieres que esté siempre disponible, usa el modo servidor en una mini
PC o laptop vieja (24/7) y apunta los dispositivos ahí.

**¿Puedo conectar el ESP32 a G-Mini de escritorio?**
Sí, si activas "Permitir conexiones" en todas las redes (Ajustes > Dispositivos >
Este equipo). Con la opción de Tailscale no: el ESP32 no puede unirse a
Tailscale. Ver [conectar con G-Mini](connect-gmini.md).

**¿El micrófono escucha todo el tiempo?**
No por defecto: se graba solo mientras mantienes el botón. Si activas la
palabra de activación, el dispositivo detecta voz localmente y manda frases
cortas a tu G-Mini para ver si dijiste "Oye G-Mini". En la Raspberry Pi puedes
usar openWakeWord para que esa detección sea local.

**¿Por qué "Oye G-Mini" se detecta en el servidor y no en el ESP32?**
Un detector de palabra clave en el ESP32 necesita un modelo entrenado por
palabra (y memoria y trabajo de afinado). Con `/voice/wake` el servidor usa el
mismo reconocedor de voz que ya tiene, entiende el nombre que le hayas puesto
a tu agente y además devuelve lo que pediste en la misma frase.

**¿Puedo cambiar el nombre "G-Mini"?**
El nombre lo defines en la identidad del agente, dentro de los ajustes de
G-Mini. La cara muestra "Conectada a <nombre>" y la palabra de activación usa
ese nombre.

**¿Qué pasa si el agente quiere prender un relé?**
`relay.set` es una superficie sensible: pasa por la política de aprobaciones
del agente igual que cualquier acción local (te pedirá confirmación si así lo
configuraste).

**¿Puedo usar otra placa?**
Cualquier ESP32 con dos periféricos I2S sirve: cambia los pines con
`build_flags`. El ESP32-C3 tiene un solo I2S (micrófono o parlante, no ambos a
la vez con este firmware). Para pantallas, cualquier controlador soportado por
U8g2 o LovyanGFX se agrega en `src/ui.cpp`.

**¿Por qué el Uno usa una fuente sin tildes y dibuja las tildes aparte?**
La fuente con todos los caracteres de ISO-8859-1 ocupaba 1 KB más y el sketch
no entraba en el Nano. Las vocales con tilde, la ñ y la ü se dibujan como la
letra base más su marca.

**¿Es un holograma de verdad?**
No: ninguna técnica de la guía es holografía (interferencia de luz). Son
ilusiones de imagen flotante muy efectivas: reflejos (Pepper), proyección en
medios casi invisibles (niebla, humo, tul) o persistencia de la visión (POV).
Ver [hologramas](holograms/README.md).

**¿Puedo vender lo que construya?**
Sí. El código es MIT y los diseños CC BY-SA 4.0: puedes fabricar y vender,
dando crédito y publicando tus cambios a los diseños bajo la misma licencia.

**¿Dónde reporto un problema?**
En el repositorio, con la variante, el comando que usaste y la salida de la
consola. Problemas de seguridad: [SECURITY.md](../SECURITY.md).
