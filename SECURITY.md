# Seguridad

## Reportar una vulnerabilidad

No abras un issue público. Usa el reporte privado de vulnerabilidades del
repositorio en GitHub (pestaña Security > Report a vulnerability) con:

- versión o commit afectado y variante (ESP32, puente, Pi, kiosco);
- pasos para reproducirlo y el impacto que ves;
- si es posible, una propuesta de corrección.

Respondemos en un plazo de 7 días y coordinamos la publicación del arreglo
antes de divulgar los detalles.

## Alcance

Entra en el alcance: el firmware, el puente USB, el cliente de pantalla, la
página de kiosco, los scripts de instalación y la forma en que estos usan la
G-Mini Remote API. Las vulnerabilidades del núcleo de G-Mini se reportan en su
propio repositorio.

## Decisiones y límites conocidos

- **Tokens.** Cada dispositivo tiene un token propio que se revoca en G-Mini.
  En el ESP32 se guarda en la NVS sin cifrar: quien tenga la placa puede leerlo.
  Para un despliegue que lo requiera, activa el cifrado de flash y de NVS de
  ESP-IDF. En PC se usa el llavero del sistema si está disponible y, si no, un
  archivo con permisos 600. En la Raspberry Pi, `/var/lib/gmini-home` con
  permisos 700 para el usuario del servicio.
- **TLS en el ESP32.** Las direcciones `https://` cifran la conexión pero no
  verifican el certificado del servidor (`setInsecure`). Úsalas solo con tu
  propio proxy; prefiere la red local o una VPN.
- **Palabra de activación.** Con "Oye G-Mini" encendido, frases cortas de lo
  que se dice cerca del dispositivo viajan a tu servidor G-Mini. Viene apagada
  por defecto.
- **Kiosco.** La página no recibe el token. Con `kiosk.listen = "0.0.0.0:8088"`
  cualquiera en tu red ve la cara y los subtítulos (que pueden incluir
  respuestas del agente); por defecto escucha solo en `127.0.0.1`.
- **Portal WiFi.** El punto de acceso de configuración usa una clave fija
  (`gminihome`) y se cierra a los 5 minutos o al guardar.
- **Relés.** `relay.set` controla cargas físicas y pasa por la política de
  aprobaciones del agente. No la desactives para cargas peligrosas.
- **Contenido no confiable.** Los textos que llegan al dispositivo (avisos,
  subtítulos) se muestran, nunca se ejecutan.
