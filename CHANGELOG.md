# Changelog

Todos los cambios relevantes de RadarCL, versión por versión.

El formato sigue [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/)
y el proyecto usa [versionado semántico](https://semver.org/lang/es/).
Cada sección de este archivo es, tal cual, el texto de las notas del
release correspondiente. Cómo se escribe una entrada nueva está en
[docs/release-notes.md](docs/release-notes.md).

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
