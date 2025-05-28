from gi.repository import GLib
from pathlib import Path

def get_tmp_dir():
    tmp_dir = GLib.get_tmp_dir()
    constrict_tmp_dir = Path(tmp_dir) / 'constrict'

    mkdir_result = GLib.mkdir_with_parents(str(constrict_tmp_dir), 0o755)
    successful = mkdir_result == 0

    if not successful:
        print('Warning: could not get tmp directory')

    return constrict_tmp_dir if successful else None
