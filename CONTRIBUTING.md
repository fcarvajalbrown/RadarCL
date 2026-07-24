# Cómo contribuir

Gracias por el interés. RadarCL es una herramienta de OSINT para contactos
públicos `.cl`, así que antes de nada conviene leer el
[aviso legal del README](README.md#aviso-legal--uso-responsable): los aportes
que faciliten spam, acoso o recolección masiva de datos personales no se
aceptan.

## Preparar el entorno

Para trabajar solo en el núcleo o en la CLI no hace falta instalar PySide6:

```bash
python -m venv venv
venv\Scripts\activate
pip install -r requirements-core.txt
pip install pytest
```

Si vas a tocar la interfaz gráfica, usa `requirements.txt`, que además trae
PySide6 y PyInstaller.

Sin conexión a internet también se puede instalar, desde las dependencias
incluidas en el repositorio:

```bash
pip install --no-index --find-links=vendor --require-hashes -r requirements-core.lock
```

## Antes de abrir un pull request

```bash
pytest -m "not smtp"          # suite completa sin red
python scripts/vendor.py --check   # solo si tocaste dependencias
```

La suite tiene que quedar verde. Las pruebas marcadas con `smtp` necesitan
internet (consultas DNS o handshake SMTP) y quedan fuera de esa ejecución a
propósito, porque son las únicas que dependen de servidores de terceros.

Si agregas una función, agrega también su prueba. `app/core/` se prueba
directamente; `app/ui/` y `app/workers/` no tienen pruebas automáticas por
decisión de diseño
([ADR-0002](docs/adr/0002-async-core-qthread-worker-bridge.md)), así que los
cambios ahí se verifican ejecutando la aplicación.

## Reglas del proyecto

**Idioma.** Todo lo que lee una persona usuaria va en español: README,
descripción del repositorio, textos de la interfaz, mensajes de estado y de
error, y estas guías. El código, los comentarios, los docstrings, los
mensajes de commit y los ADR van en inglés. Los nombres de subcomandos y
opciones de la CLI también quedan en inglés, porque son identificadores de
interfaz y no prosa traducible.

**Capas.** `app/core/` no importa Qt, nunca. Toda la lógica de rastreo y
verificación vive ahí como funciones async y dataclasses, sin dependencia de
la interfaz. `app/workers/` es el único punto donde Qt y `core` se tocan, y
`app/ui/` consume solo señales de esos workers. Hay una prueba que lo
verifica: `tests/test_cli.py::test_importing_cli_does_not_load_qt`.

**Dependencias.** Si agregas o subes una dependencia del núcleo, actualiza
`requirements-core.txt` y después ejecuta `python scripts/vendor.py`, que
regenera `vendor/`, el manifiesto `SHA256SUMS.txt` y
`requirements-core.lock`. Los tres archivos van en el mismo commit. El
porqué está en [ADR-0008](docs/adr/0008-vendored-core-dependencies.md).

**Decisiones de diseño.** Las decisiones que cambian la arquitectura se
registran como ADR en [docs/adr/](docs/adr/). Un ADR aceptado no se edita:
si una decisión cambia, se escribe uno nuevo con el número siguiente y se
marca el anterior como superado. El caso más reciente es
[ADR-0007](docs/adr/0007-smtp-response-classification.md), que reemplazó al
0004.

**Commits.** En inglés, en modo imperativo, explicando el porqué y no solo
el qué. Sin emojis y sin atribución a herramientas de IA.

## Dónde mirar primero

- [PRD.md](PRD.md) — el problema, el público objetivo y lo que RadarCL
  explícitamente no pretende ser.
- [ROADMAP.md](ROADMAP.md) — qué viene, por versión. Si buscas por dónde
  empezar, los puntos sin marcar de la versión más baja son el mejor
  candidato.
- [CLAUDE.md](CLAUDE.md) — arquitectura y comandos, en inglés.
- [docs/adr/](docs/adr/) — por qué las cosas son como son.
