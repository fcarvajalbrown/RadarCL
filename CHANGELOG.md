# Changelog

Todos los cambios relevantes de RadarCL, versión por versión.

El formato sigue [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/)
y el proyecto usa [versionado semántico](https://semver.org/lang/es/).
Cada sección de este archivo es, tal cual, el texto de las notas del
release correspondiente. Cómo se escribe una entrada nueva está en
[docs/release-notes.md](docs/release-notes.md).

## [0.5.5] - 2026-07-25

Cada vez que RadarCL comprobaba una dirección se presentaba ante el
servidor de correo como verify.cl, un dominio registrado a nombre de otra
persona, así que cualquier reclamo o bloqueo que se ganara esta
herramienta caía sobre un tercero. Esa resultó ser una confusión de seis,
todas iguales por dentro: leer una respuesta que habla del remitente, de
la ruta o del protocolo como si hablara de la dirección. Un 550 que
significa "a ti no te acepto" ya no marca la dirección como inválida, y un
buzón lleno tampoco, porque estar lleno prueba que existe. Quedan menos
inválidos, y los que quedan pesan más.

### Añadido
- Un cuarto estado, "Acepta todo". Hay servidores que responden 250 a
  cualquier destinatario, así que aceptar no prueba que el buzón exista.
  Se detecta con dos sondas de veinte caracteres aleatorios sobre la
  conexión ya abierta, una vez por dominio y no una vez por dirección,
  porque aceptar todo es una propiedad del servidor. Queda fuera del CSV,
  por la misma razón que los desconocidos, y aparece en JSON y HTML
  ([ADR-0016](docs/adr/0016-catch-all-domains-are-not-valid.md)). Medido
  sobre veinte dominios `.cl` reales: 17% de los alcanzables acepta todo.
- Las respuestas 4xx que se leen como greylisting quedan marcadas como
  dignas de reintentar, con el motivo escrito en el detalle. Esas
  direcciones están vivas y contestan distinto más tarde. El 421 queda
  fuera a propósito: reintentar rápido a un servidor saturado es
  exactamente como una demora se convierte en un bloqueo.
- JSON y HTML dicen ahora si una dirección fue generada a partir de un
  patrón o encontrada publicada. Son dos afirmaciones distintas y hasta
  ahora se veían iguales
  ([ADR-0018](docs/adr/0018-generation-stays-in-cl-and-a-guess-says-so.md)).
- `RADARCL_HELO` para quien ejecute RadarCL desde un equipo con dominio
  propio y PTR que calce. Es la única forma correcta de mejorar la
  aceptación: la otra es nombrar un dominio que no es suyo.

### Cambiado
- RadarCL se presenta con el nombre de su propio equipo y usa el remitente
  nulo, la convención para sondas que nunca envían y lo que usa la
  verificación de direcciones de Postfix. Antes decía `verify.cl` y
  `check@verify.cl`, un dominio con registro y servidores de nombres a
  nombre de un tercero
  ([ADR-0017](docs/adr/0017-a-reply-is-evidence-only-about-its-subject.md)).
- Un 5xx ya no es inválido por empezar con 5. El dígito del medio del
  código extendido (RFC 3463) dice de qué habla la respuesta: solo los
  temas 1 y 2 hablan del destinatario. Política, ruta, protocolo y
  problemas del sistema del otro lado pasan a desconocido, con el motivo
  explicado. Un 5xx sin código extendido sigue siendo inválido.
- Un MX nulo (RFC 7505) pasa a inválido. El dominio está diciendo con
  todas sus letras que no acepta correo, y eso se registraba como si nadie
  hubiera contestado.
- La generación por patrón se limita a `.cl`, igual que la extracción.
  Apuntar a un dominio `.com` producía candidatos que la verificación
  rechazaba después como "formato inválido", lo que era falso: el formato
  estaba bien y lo que sobraba era el alcance. Donde una empresa tiene
  personal en Chile suele tener también un dominio de correo `.cl`, y ese
  RadarCL ya lo soporta entero.

**Cambio incompatible, solo para quien use `app/core/` como biblioteca.**
`verify()` y `pipeline.verify_all()` dejan de aceptar el parámetro
`api_key`, y `VerificationResult` pierde el campo `api_status`. Para
migrar, borre el argumento de sus llamadas: no hacía nada, ninguna interfaz
lo exponía y nada leía su resultado. Quien recorra los estados por su
nombre debe además contemplar `catch_all`, que es nuevo.

### Eliminado
- La etapa 4 del verificador, la "API de terceros". Era un marcador de
  posición que ninguna interfaz alcanzaba: ni la línea de comandos ni la
  aplicación de escritorio pasaban jamás una clave, nada leía lo que
  escribía, y solo podía ejecutarse después de un SMTP completo. Se cerró
  la pregunta en vez de construirla: los servicios comerciales cuestan y
  aciertan entre 70% y 85% en dominios que aceptan todo, que es justamente
  el caso que hacía falta resolver
  ([ADR-0015](docs/adr/0015-no-third-party-verification-api.md)).

### Corregido
- Un buzón lleno (`X.2.2`) se marcaba como inválido. Estar lleno prueba
  que el buzón existe, así que ahora queda como desconocido con el motivo
  escrito.
- `docs/research/dotcom-attribution.md` ordenaba seis señales por lo que
  cada una probaría si estuviera presente, sin haber comprobado si alguna
  lo estaba. La primera no apareció en ninguna de las 200 páginas
  rastreadas. Las mediciones quedaron agregadas y el orden viejo quedó
  marcado, no borrado.
- `docs/PRD.md` decía que el filtro `.cl` era una frontera permanente.
  Cubría lo extraído y nunca cubrió lo generado. Ahora lo cubre.

### Antes de instalar
Esta versión no trae instalador. Es un hito de código, no de
distribución, y la aplicación de escritorio se reconstruye en la próxima
versión 0.1. Quien quiera estos cambios hoy los tiene clonando el
repositorio y ejecutando `python -m app.main` o `python -m app.cli`.

RadarCL es para investigación OSINT legítima. No está autorizado su uso
para envío masivo de correo no solicitado, acoso, ni ningún otro fin
malicioso.

## [0.5.0] - 2026-07-24

Un candidato generado para bhp.com salía en la misma lista que
sarah.wilson@bhp.com, una dirección de Melbourne, bajo el rótulo de
contactos chilenos. Esta versión salió a medir si la nacionalidad se puede
deducir de una dirección .com y la respuesta fue no: el RUT, la señal que
parecía más fuerte, no apareció en ninguna de las 200 páginas rastreadas,
y ampliar el filtro no habría sumado ni una dirección en Codelco,
Falabella ni Sonda. RadarCL ya no deduce el país. Anota lo que vio.

### Añadido
- Cada dirección encontrada lleva las señales chilenas de la página donde
  apareció: `lang-es-cl`, `rut`, `phone-cl`, `lexicon` y `path-cl`. Es una
  marca, nunca un filtro. Sobre siete empresas chilenas con dominio .com
  la cascada se activó en cuatro, así que usarla para decidir qué se
  recoge habría descartado en silencio direcciones reales en las otras
  tres ([ADR-0014](docs/adr/0014-country-is-never-inferred-from-a-com-address.md)).
- Las exportaciones JSON y HTML incluyen esas señales. El informe HTML
  suma una columna "Evidencia" y explica, ahí mismo, que no afirma la
  nacionalidad de la empresa: teck.com la activa porque su página de
  contacto publica una oficina en Las Condes y un teléfono chileno real,
  y eso es correcto. La señal habla de la página, no de quién es dueño
  del dominio.
- `python-stdnum` y `phonenumbers` en `vendor/`, con sus hashes
  ([ADR-0008](docs/adr/0008-vendored-core-dependencies.md)). La segunda
  trae el plan de numeración chileno, que es lo que permite reconocer un
  número escrito 22 818 5000, sin el +56 adelante.

### Cambiado
- El CSV conserva exactamente sus columnas y la salida estándar del CLI
  sus tres campos separados por tabulación. Quien ya procesa esa salida no
  tiene que tocar nada: la evidencia va al JSON y al HTML, que son el
  registro de la corrida, y no a la lista que se usa para escribir correos
  ([ADR-0010](docs/adr/0010-export-contents-differ-by-format.md)).
- `pipeline.verify_all` acepta pares `(correo, origen)` o tríos
  `(correo, origen, evidencia)`. Los dos siguen funcionando, porque el
  subcomando `verify` lee direcciones sueltas de un archivo y no tiene
  página detrás de dónde sacar evidencia. En esos registros la clave
  `evidence` no aparece, en vez de aparecer vacía: vacía significa que se
  revisó la página y no había nada, y ausente significa que nadie miró.
- La aplicación de escritorio recoge la evidencia y no la muestra en la
  tabla de resultados. Llega igual al JSON y al HTML exportados desde la
  interfaz.

### Corregido
- `docs/PRD.md` decía que el filtro .cl era una frontera de alcance
  permanente. Cubre las direcciones extraídas de una página y nunca cubrió
  los candidatos generados por patrón, que toman el dominio que uno
  escriba. Dos versiones sostuvieron eso mientras el código hacía otra
  cosa. Ahora el documento dice lo que el programa hace.
- `docs/research/dotcom-attribution.md` ordenaba seis señales por lo que
  cada una probaría si estuviera presente, sin haber comprobado si alguna
  lo estaba. La que iba primera no apareció nunca. Las mediciones quedaron
  agregadas al archivo y el orden viejo quedó marcado, no borrado.

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

## [0.4.0] - 2026-07-24

crt.sh estuvo caído unos quince minutos justo mientras se escribía esta
versión, y hasta ahora eso bastaba para que la primera etapa del
descubrimiento de semillas no devolviera nada ni dijera por qué. Ahora
tiene respaldo: CertSpotter contesta en 0,6 segundos, sin clave y sin
registro. De paso se midió qué devolvían las ocho fuentes chilenas
escritas a mano, y el resultado fue 451 páginas rastreadas, 97 correos
encontrados, ninguno del dominio que se buscaba, así que esa etapa se
eliminó completa. Los ocho dominios de prueba siguieron encontrando
exactamente las mismas direcciones, con menos páginas gastadas.

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
- Quitar esa etapa no cambió ni una dirección encontrada. Se midió con la
  tubería completa en los ocho dominios de prueba, con y sin la etapa, y
  las dos versiones devolvieron exactamente la misma cantidad.
- `transparencia.cl`, `munitel.cl`, `cna.cl` y `fach.cl`, que ya estaban
  equivocadas antes de todo esto. Tres seguían respondiendo 200 mientras
  tanto, así que revisar si la página carga no habría servido de nada.

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
