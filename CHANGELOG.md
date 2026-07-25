# Changelog

Todos los cambios relevantes de RadarCL, versión por versión.

El formato sigue [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/)
y el proyecto usa [versionado semántico](https://semver.org/lang/es/).
Cada sección de este archivo es, tal cual, el texto de las notas del
release correspondiente. Cómo se escribe una entrada nueva está en
[docs/release-notes.md](docs/release-notes.md).

## [0.4.0] - 2026-07-24

RadarCL tenía ocho fuentes chilenas escritas a mano y cuatro habían
dejado de ser lo que decían: munitel.cl vende departamentos. Se repararon
una por una, se les puso una prueba que verifica que cada página siga
nombrando a su institución, y recién ahí se midió qué devolvían de
verdad: 451 páginas rastreadas, 97 correos encontrados, ninguno del
dominio que se estaba buscando. También entró CertSpotter como respaldo,
porque crt.sh estuvo caído unos quince minutos justo mientras se escribía
esta versión. La lista curada no sobrevivió a su propia medición.

### Eliminado
- La etapa de fuentes chilenas curadas, completa. Sembraba sitios
  institucionales (subdere.gov.cl, portaltransparencia.cl y otros) en
  cada escaneo, y su puntuación de enlaces nunca llegó a activarse:
  ninguna portada institucional enlaza por URL al dominio que uno busca.
  Rastrear cada fuente por separado dio 97 correos `.cl` y ninguno del
  dominio objetivo. En siete de ocho dominios de prueba las semillas ni
  siquiera pasaban el corte de `max_seeds`, y en el octavo se llevaron el
  60% del presupuesto de páginas sin devolver nada
  ([ADR-0013](docs/adr/0013-curated-source-stage-removed-after-measurement.md)).
- `transparencia.cl`, `munitel.cl`, `cna.cl` y `fach.cl`, que ya estaban
  equivocadas antes de todo esto. Tres seguían respondiendo 200 mientras
  tanto, así que revisar si la página carga no habría servido de nada.

### Añadido
- CertSpotter como respaldo de crt.sh dentro de la primera etapa del
  descubrimiento de semillas. Antes una caída de crt.sh se tragaba la
  etapa completa y no decía nada. Sin clave de API y sin registro
  ([ADR-0011](docs/adr/0011-ct-fallback-and-source-hygiene.md)).
- La cadena se detiene en la primera fuente que devuelve algo. Una fuente
  que responde sin registros ya respondió, así que devuelve vacío en vez
  de fallar; solo cuando todas fallan hay error, la misma distinción que
  [ADR-0009](docs/adr/0009-mx-resolution-failure-is-unknown.md) hizo para
  el DNS.

### Cambiado
- El tiempo de espera de crt.sh baja de 30 a 20 segundos. Una consulta
  fría de crt.sh tardó 76,7 y 60,3 segundos, y una ya en caché, uno; no
  hay plazo razonable que cubra las dos. Veinte segundos cubren la caché
  y le pasan el resto a CertSpotter, que contesta en 0,6. El costo está
  dicho sin adornos en el ADR: en un dominio frío se cambian los trece
  nombres de crt.sh por los cuatro de CertSpotter.
- El rastreador y el descubridor de semillas mandan el mismo User-Agent
  de navegador. `portaltransparencia.cl` y `anid.cl` respondían 403 al
  anterior, así que el rastreador bajaba cero páginas de esos dos sitios.
- Al puntuar enlaces ahora solo cuentan los que llevan el dominio en el
  host. Antes bastaba con que apareciera en cualquier parte de la
  dirección, así que un enlace a otro sitio con `?ref=nunoa.cl` pasaba
  por interno.
- MerkleMap quedó descartado y está anotado como tal para que nadie lo
  reintente: responde 401 sin clave y su único plan cuesta 49 euros al
  mes, sin capa gratuita de API.

### Corregido
- La Biblioteca del Congreso Nacional se clasificaba como empresa.
  Faltaba `bcn` en la tabla de palabras clave, que es la que decide qué
  puntuación de enlaces y qué consultas de búsqueda se usan.
- `scripts/release_notes.py` escribía en la codificación local de Windows
  al redirigir su salida, así que las notas de una versión salían con los
  acentos rotos. Ahora escribe UTF-8.
- `PRD.md` se movió a `docs/` y dejó enlaces rotos en `ROADMAP.md`,
  `CONTRIBUTING.md` y en el propio documento.

### Antes de instalar
El ejecutable no está firmado digitalmente, así que Windows SmartScreen
puede advertir al abrirlo. Algunos antivirus marcan como sospechoso
cualquier ejecutable empaquetado con PyInstaller, sin que haya nada
sospechoso adentro; es un problema conocido del empaquetado y está
anotado en la hoja de ruta. El código está completo en este repositorio
para quien prefiera compilarlo por su cuenta.

RadarCL es para investigación OSINT legítima. No está autorizado su uso
para envío masivo de correo no solicitado, acoso, ni ningún otro fin
malicioso.

## [0.3.5] - 2026-07-24

Un rastreo de nunoa.cl encontró dieciséis direcciones municipales
publicadas y marcó las dieciséis como inválidas. Eran todas reales. El
resolutor DNS de esa máquina no contestaba, y el verificador trataba ese
silencio igual que un dominio inexistente. Esta versión corrige eso,
agrega exportación en JSON y HTML, y termina de dejar la interfaz en
español.

### Añadido
- Exportación en JSON y HTML además del CSV. El formato sale de la
  extensión de `--output`, y `--format csv|json|html` lo fuerza.
- El JSON y el HTML llevan todos los resultados con su estado y el motivo
  de la falla; el CSV sigue llevando solo las direcciones válidas
  ([ADR-0010](docs/adr/0010-export-contents-differ-by-format.md)).
- Reporte HTML de un solo archivo: sin JavaScript, sin hojas de estilo
  externas, sin imágenes remotas. Se abre sin conexión.
- Resolución DNS con transportes de respaldo en `app/core/dns_lookup.py`:
  resolutor del sistema, luego `8.8.8.8` y `1.1.1.1`, luego DNS sobre
  HTTPS. La última existe porque funciona en redes que filtran el
  puerto UDP 53.
- Dependencias del núcleo incluidas en `vendor/` con manifiesto SHA-256 y
  un `requirements-core.lock` fijado por hash, así una copia limpia se
  instala sin red y sobrevive a que un paquete desaparezca de PyPI
  ([ADR-0008](docs/adr/0008-vendored-core-dependencies.md)).
- Integración continua en GitHub Actions: la suite sin red, la integridad
  de `vendor/` y que la CLI arranque.
- `CONTRIBUTING.md` y plantillas de issue y de pull request, en español.

### Corregido
- Una consulta DNS sin respuesta se informaba como dirección inválida, lo
  mismo que un dominio que no existe. Ahora es desconocida
  ([ADR-0009](docs/adr/0009-mx-resolution-failure-is-unknown.md)).
- Un dominio sin registro MX pero con registro A se informaba como
  inválido. Ahora se resuelve por MX implícito, según la sección 5.1 del
  RFC 5321.
- Tres pruebas del verificador hacían consultas DNS reales sin estar
  marcadas, así que `pytest -m "not smtp"` no corría realmente sin red.
  La suite sin conexión pasó de unos 20 segundos a unos 5.
- El panel de control, la tabla de resultados y el feed de la terminal
  todavía tenían botones, mensajes, tooltips y diálogos en inglés.

### Cambiado
- El asistente del instalador quedó en español.
- `dist/` e `installer/` salieron del control de versiones. Los binarios
  pesaban 57 MB cada uno y habían llevado el repositorio sobre los 110 MB.
  Ahora se distribuyen como archivos adjuntos a un release.

### Antes de instalar
El ejecutable no está firmado digitalmente, así que Windows SmartScreen
puede advertir al abrirlo. Algunos antivirus marcan como sospechoso
cualquier ejecutable empaquetado con PyInstaller, sin que haya nada
sospechoso adentro; es un problema conocido del empaquetado y está
anotado en la hoja de ruta. El código está completo en este repositorio
para quien prefiera compilarlo por su cuenta.

RadarCL es para investigación OSINT legítima. No está autorizado su uso
para envío masivo de correo no solicitado, acoso, ni ningún otro fin
malicioso.

## 0.3.0 - 2026-07-24

RadarCL dejó de ser solo una aplicación de escritorio. `app/core/` no
importa Qt en ninguna parte, y ahora hay una CLI que lo maneja
directamente, así que la herramienta corre en un servidor, en una tarea
programada o dentro de otro script.

### Añadido
- `python -m app.cli` con tres subcomandos: `discover`, `scan` y `verify`.
  Los datos salen por stdout y el progreso en español por stderr, así que
  el resultado se puede encadenar con otros comandos.
- `app/core/pipeline.py`, el orquestador sin Qt que comparten la CLI y los
  hilos de la interfaz gráfica, para que cada bucle tenga una sola
  implementación.
- `requirements-core.txt` para instalar el núcleo sin PySide6.

### Corregido
- Una respuesta SMTP distinta de 250 marcaba la dirección como inválida,
  incluso cuando el servidor solo estaba pidiendo reintentar más tarde.
  Ahora se clasifica por clase de código: 250 válido, 5xx inválido, 4xx y
  252 desconocido
  ([ADR-0007](docs/adr/0007-smtp-response-classification.md)).

## 0.2.0 - 2026-07-24

La versión en que el proyecto se hizo público de verdad: licencia,
número de versión y un README que parte por lo que hace la herramienta.

### Añadido
- Licencia Apache 2.0.
- Los resultados del rastreo se guardan en disco durante la corrida, no
  solo al final.
- README con logo, insignias y la sección "Aviso legal / uso
  responsable".

### Estado de la herramienta en esta versión
- Descubrimiento automático de semillas vía crt.sh, sondeo DNS y
  puntuación semántica de enlaces.
- Rastreo sensible al tipo de entidad: municipalidad, gobierno,
  universidad o empresa.
- Feed de correos en vivo en la terminal.
- Verificación multietapa: sintaxis, MX y SMTP.
- Generación de candidatos por patrón para dominios que no publican
  direcciones.
- Exportación automática a CSV en el Escritorio.
- Ajuste de concurrencia y ritmo según el hardware detectado.
- Pausa y reanudación conservando el estado de la sesión.

---

Antes de la 0.2.0 el proyecto no llevaba versiones. Esa historia está en
los commits.

La 0.3.5 es la primera versión con etiqueta y release publicados. Las dos
anteriores quedaron registradas aquí, pero no tienen etiqueta en el
repositorio, así que no hay nada que enlazar.

[0.3.5]: https://github.com/fcarvajalbrown/RadarCL/releases/tag/v0.3.5
