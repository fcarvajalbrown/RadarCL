"""Entry point. Launches the PySide6 application."""

import sys
from PySide6.QtWidgets import QApplication
import app
from app.ui.main_window import MainWindow


def main() -> None:
    """Initialise Qt application and show main window."""
    app = QApplication(sys.argv)
    app.setApplicationName("RadarCL")
    app.setOrganizationName("Área de Innovación Tecnológica - Instituto Igualdad")
    from PySide6.QtGui import QIcon
    from pathlib import Path
    app.setWindowIcon(QIcon(str(Path(__file__).parent.parent / 'assets' / 'icon.ico')))
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()