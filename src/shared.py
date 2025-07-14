# shared.py
#
# Copyright 2025 Wartybix
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.
#
# SPDX-License-Identifier: GPL-3.0-or-later

from gi.repository import GLib
from pathlib import Path
from typing import Optional, Any, Callable

def get_tmp_dir() -> Optional[Path]:
    tmp_dir = GLib.get_tmp_dir()
    constrict_tmp_dir = Path(tmp_dir) / 'constrict'

    mkdir_result = GLib.mkdir_with_parents(str(constrict_tmp_dir), 0o755)
    successful = mkdir_result == 0

    if not successful:
        print('Warning: could not get tmp directory')

    return constrict_tmp_dir if successful else None

def update_ui(function: Callable, arg: Any, daemon: bool) -> None:
    if daemon:
        if arg is not None:
            GLib.idle_add(function, arg)
        else:
            GLib.idle_add(function)
    else:
        if arg is not None:
            function(arg)
        else:
            function()
