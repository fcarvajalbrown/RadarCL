"""Entry point. Launches the PySide6 application."""

import sys
from PySide6.QtWidgets import QApplication
from app.ui.main_window import MainWindow


def main() -> None:
    """Initialise Qt application and show main window."""
    app = QApplication(sys.argv)
    app.setApplicationName("RadarCL")
    app.setOrganizationName("Instituto Igualdad")
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()