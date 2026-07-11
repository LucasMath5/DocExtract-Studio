"""Application icon and Windows taskbar integration."""

from __future__ import annotations

import ctypes
import logging
import sys
from pathlib import Path

from PySide6.QtGui import QIcon

LOGGER = logging.getLogger(__name__)
WINDOWS_APP_USER_MODEL_ID = "LucasMath5.DocExtractStudio"


def application_icon_path() -> Path:
    """Return the packaged icon suitable for the current platform."""
    icon_name = "app.ico" if sys.platform == "win32" else "app.png"
    return Path(__file__).resolve().parent.parent / "resources" / "icons" / icon_name


def load_application_icon() -> QIcon:
    """Load the packaged application icon and report missing resources."""
    icon_path = application_icon_path()
    icon = QIcon(str(icon_path))
    if icon.isNull():
        LOGGER.warning("Ícone da aplicação não encontrado: %s", icon_path)
    return icon


def configure_windows_app_user_model_id() -> None:
    """Give the process a stable identity for Windows taskbar grouping."""
    if sys.platform != "win32":
        return
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(  # type: ignore[attr-defined]
            WINDOWS_APP_USER_MODEL_ID
        )
    except (AttributeError, OSError):
        LOGGER.warning("Não foi possível configurar a identidade da aplicação no Windows")
