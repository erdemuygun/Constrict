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
    """ Return the path of system temp directory, to store temporary files like
    ffmpeg log files and video thumbnails. If the temp directory cannot be
    located, None will be returned.
    """
    tmp_dir = GLib.get_tmp_dir()
    constrict_tmp_dir = Path(tmp_dir) / 'constrict'

    mkdir_result = GLib.mkdir_with_parents(str(constrict_tmp_dir), 0o755)
    successful = mkdir_result == 0

    if not successful:
        print('Warning: could not get tmp directory')

    return constrict_tmp_dir if successful else None

def update_ui(function: Callable, arg: Any, daemon: bool) -> None:
    """ A helper function to determine whether to run a passed function
    directly, or through GLib.idle_add if running in a separate, daemonic
    thread (like UI updates while videos are being compressed).

    Without using GLib.idle_add, the UI can freeze when the window is inactive,
    stopping compression progress being shown from the daemon thread. It can
    also cause the UI to glitch out or disappear sometimes. But running
    GLib.idle_add functions from the main thread also seems to cause bugs.
    This just prevented me from writing too much boilerplate code.
    """
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
