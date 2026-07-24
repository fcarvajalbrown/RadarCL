<div align="center">
<img src="assets/icon.svg" width="120" alt="Logo de RadarCL: rastreador asíncrono y verificador para descubrir contactos de correo público en Chile (.cl)">

# RadarCL

![versión](https://img.shields.io/badge/versi%C3%B3n-0.2.0-blue)
![licencia](https://img.shields.io/badge/licencia-Apache%202.0-green)
![plataforma](https://img.shields.io/badge/plataforma-Windows-slate)
![tecnología](https://img.shields.io/badge/tecnolog%C3%ADa-Python%20%7C%20PySide6-blue)
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
puede reutilizarse por separado — ver `CLAUDE.md` para el detalle de la
arquitectura.

## Instalación
```bash
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python -m app.main
```

## Tecnologías
- Interfaz gráfica: PySide6 (Qt6)
- HTTP: httpx + BeautifulSoup4
- Verificación: dnspython + smtplib
- Almacenamiento: SQLite (stdlib)
- Empaquetado: PyInstaller + Nuitka

## Historial de versiones

### v0.2.0 (actual)
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
