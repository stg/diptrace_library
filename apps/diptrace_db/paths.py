"""Resolve the visible default database location without creating directories."""
import os
from pathlib import Path
import shlex
import sys


def _windows_documents() -> Path:
    # Ask Windows rather than assuming Documents is under the profile: it may
    # have been redirected to another drive, a network share or a sync folder.
    import ctypes
    from uuid import UUID

    shell = ctypes.WinDLL("shell32")
    ole = ctypes.WinDLL("ole32")
    shell.SHGetKnownFolderPath.argtypes = [
        ctypes.c_void_p, ctypes.c_uint32, ctypes.c_void_p,
        ctypes.POINTER(ctypes.c_void_p),
    ]
    shell.SHGetKnownFolderPath.restype = ctypes.c_long
    ole.CoTaskMemFree.argtypes = [ctypes.c_void_p]
    ole.CoTaskMemFree.restype = None
    ole.CoInitializeEx.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
    ole.CoInitializeEx.restype = ctypes.c_long
    ole.CoUninitialize.argtypes = []
    ole.CoUninitialize.restype = None

    initialized = ole.CoInitializeEx(None, 2)
    # An existing COM apartment can still service the folder query. Only undo
    # initialization when this call actually acquired an initialization count.
    if initialized < 0 and initialized != -2147417850:  # RPC_E_CHANGED_MODE
        raise OSError("cannot initialize the Windows Documents folder query")
    folder = (ctypes.c_ubyte * 16).from_buffer_copy(
        UUID("FDD39AD0-238F-46AF-ADB4-6C85480369C7").bytes_le
    )
    pointer = ctypes.c_void_p()
    try:
        status = shell.SHGetKnownFolderPath(ctypes.byref(folder), 0, None, ctypes.byref(pointer))
        if status < 0:
            raise OSError("cannot resolve the Windows Documents folder; supply --out instead")
        return Path(ctypes.wstring_at(pointer))
    finally:
        ole.CoTaskMemFree(pointer)
        if initialized >= 0:
            ole.CoUninitialize()


def _xdg_documents(home: Path) -> Path:
    config = Path(os.environ.get("XDG_CONFIG_HOME", home / ".config"))
    if not config.is_absolute():
        config = home / ".config"
    try:
        lines = (config / "user-dirs.dirs").read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeError):
        lines = []
    for line in lines:
        name, separator, value = line.partition("=")
        if not separator or name.strip() != "XDG_DOCUMENTS_DIR":
            continue
        try:
            words = shlex.split(value, comments=True)
        except ValueError:
            continue
        if len(words) != 1:
            continue
        # Parse configuration as data, never by sourcing a shell script.
        value = words[0]
        for marker in ("${HOME}", "$HOME"):
            if value == marker or value.startswith(marker + "/"):
                value = str(home) + value[len(marker):]
                break
        path = Path(value)
        if path.is_absolute():
            return path
    return home / "Documents"


def default_database_path() -> Path:
    """Use the user's Documents folder, respecting OS folder configuration."""
    if sys.platform == "win32":
        documents = _windows_documents()
    elif sys.platform == "darwin":
        documents = Path.home() / "Documents"
    else:
        documents = _xdg_documents(Path.home())
    return documents / "DipTraceLibrary" / "component_db.json"
