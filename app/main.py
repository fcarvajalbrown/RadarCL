"""Entry point. Launches the PySide6 application."""

import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QIcon

from app.ui.main_window import MainWindow


def _assets_path() -> Path:
    """Return assets directory, works both in dev and PyInstaller .exe."""
    if getattr(sys, 'frozen', False):
        return Path(sys._MEIPASS) / 'assets' # type: ignore
    return Path(__file__).parent.parent / 'assets'


def main() -> None:
    """Initialise Qt application and show main window."""
    app = QApplication(sys.argv)
    app.setApplicationName("RadarCL")
    app.setOrganizationName("Área de Innovación Tecnológica - Instituto Igualdad")
    app.setWindowIcon(QIcon(str(_assets_path() / 'icon.ico')))
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()