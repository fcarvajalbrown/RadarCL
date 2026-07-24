<div align="center">
<img src="assets/icon.svg" width="120" alt="Logo de RadarCL: rastreador asíncrono y verificador para descubrir contactos de correo público en Chile (.cl)">

# RadarCL

![versión](https://img.shields.io/badge/versi%C3%B3n-0.3.0-blue)
![licencia](https://img.shields.io/badge/licencia-Apache%202.0-green)
![plataforma](https://img.shields.io/badge/plataforma-Windows%20(GUI)%20%7C%20CLI%20sin%20Qt-slate)
![tecnología](https://img.shields.io/badge/tecnolog%C3%ADa-Python%20%7C%20PySide6-blue)
![alcance](https://img.shields.io/badge/alcance-solo%20.cl-orange)
</div>

Rastreador asíncrono y verificador multietapa para descubrir contactos de
correo público en sitios web chilenos (`.cl`). Automatiza el proceso que
las herramientas de OSINT y civic-tech normalmente tienen que armar a mano
para este dominio: descubrimiento de semillas sensible al tipo de entidad
(registros de Certificate Transparency vía crt.sh, verificación de
actividad por DNS, puntuación semántica de enlaces y fuentes chilenas de
alto valor ya conocidas), un rastreador por fases que se mantiene acotado
a `.cl` por defecto, extracción de correos con desofuscación, y
verificación por etapas (sintaxis → MX → SMTP).

Se distribuye como aplicación de escritorio en PySide6 para usuarios no
técnicos, pero `app/core/` es Python/asyncio puro sin dependencia de Qt y
puede reutilizarse por separado (ver `CLAUDE.md` para el detalle de la
arquitectura).

Desarrollado por Felipe Carvajal Brown, investigador independiente, para
quienes construyen herramientas de civic-tech, govtech u OSINT sobre
datos chilenos (`.cl`).

## Instalación
```bash
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python -m app.main
```

## Uso desde la línea de comandos

La CLI no depende de Qt, así que sirve para scripts, tareas programadas y
máquinas sin entorno gráfico. Instala solo lo que necesita el núcleo:

```bash
pip install -r requirements-core.txt
```

Tres subcomandos:

```bash
# Solo descubrir semillas, sin rastrear
python -m app.cli discover nunoa.cl

# Pipeline completo: descubre, rastrea, extrae y verifica
python -m app.cli scan nunoa.cl --pattern "{first}.{last}" --output correos.csv

# Verificar una lista que ya tienes
python -m app.cli verify --input correos.txt --no-smtp
```

Los datos salen por stdout y los mensajes de progreso por stderr, así que el
resultado se puede encadenar directamente:

```bash
python -m app.cli scan nunoa.cl --quiet | cut -f1 > direcciones.txt
```

`scan` ajusta concurrencia, retardo y límite de páginas según el hardware que
detecta. Las opciones `--concurrency`, `--delay` y `--max-pages` lo
sobrescriben. Cada ejecución queda registrada en `~/.radarcl/sessions.db`
salvo que uses `--no-session`. El listado completo de opciones está en
`python -m app.cli --help`.

## Uso como biblioteca

`app/core/` es Python/asyncio puro y se puede importar por separado, sin la
interfaz gráfica:

```python
import asyncio
from app.core.pipeline import crawl_and_extract, verify_all
from app.core.seed_discoverer import discover_seeds

async def main():
    semillas = await discover_seeds("nunoa.cl")
    hallazgos = [d async for d in crawl_and_extract(semillas, "nunoa.cl")]
    for registro in verify_all([(d.email, d.source_url) for d in hallazgos]):
        print(registro["email"], registro["status"])

asyncio.run(main())
```

Los módulos del núcleo son independientes entre sí: `seed_discoverer`,
`crawler`, `extractor`, `pattern_generator` y `verifier` funcionan sueltos, y
`pipeline` solo los encadena.

## Tecnologías
- Interfaz gráfica: PySide6 (Qt6)
- HTTP: httpx + BeautifulSoup4
- Verificación: dnspython + smtplib
- Almacenamiento: SQLite (stdlib)
- Empaquetado: PyInstaller

## Historial de versiones

### v0.3.0 (actual)
- Modo CLI sin Qt (`python -m app.cli`) con tres subcomandos: `discover`,
  `scan` y `verify`
- `app/core/` documentado y utilizable como biblioteca independiente
- `requirements-core.txt` para instalar el núcleo sin PySide6
- Clasificación SMTP por clase de código: 250 válido, 5xx inválido,
  4xx y 252 desconocido

### v0.2.0
- Descubrimiento automático de semillas vía crt.sh, sondeo DNS y
  puntuación semántica
- Rastreo sensible al tipo de entidad (municipalidad, gobierno,
  universidad, empresa)
- Feed de correos en vivo en la terminal
- Verificación multietapa (sintaxis, MX, SMTP)
- Exportación automática a CSV en el Escritorio
- Ajuste de rendimiento según el hardware
- Pausa/reanudación con estado de sesión preservado

## Hoja de ruta

Los planes a futuro están en [ROADMAP.md](ROADMAP.md), con las decisiones
de diseño registradas en [docs/adr/](docs/adr/).

## Aviso legal / uso responsable

RadarCL está pensado para investigación OSINT legítima: verificación de
contactos públicos, due diligence y trabajo de civic-tech/govtech. No está
autorizado su uso para envío masivo de correo no solicitado (spam), acoso,
ni ningún otro fin malicioso. El uso indebido de esta herramienta es
responsabilidad exclusiva de quien la ejecuta; el proyecto se reserva el
derecho de reportar abusos y de iniciar las acciones legales que
correspondan.

## Licencia

Apache 2.0. Ver [LICENSE](LICENSE).
