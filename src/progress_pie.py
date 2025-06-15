# progress_pie.py
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


# Acknowledgements: the circular progress indicator is taken from GNOME
# Builder, written by Christian Hergert. It was originally written in C, and I
# have converted it to Python code here.
# - https://gitlab.gnome.org/GNOME/gnome-builder/-/blob/a85d4873db23dcee066736b746d23eb2e5b7b4ac/src/libide/gtk/ide-progress-icon.c

from gi.repository import Adw, Gtk, Gdk
import cairo
from math import pi

def draw(pie, ctx: cairo.Context, width, height):
    rgba = pie.get_color()

    foreground_alpha = rgba.alpha
    background_alpha = 0.15

    rgba.alpha = background_alpha

    Gdk.cairo_set_source_rgba(ctx, rgba)

    ctx.arc(
        width / 2,
        height / 2,
        width / 2,
        0.0,
        2 * pi
    )
    ctx.fill()

    if pie.fraction > 0.0:
        rgba.alpha = foreground_alpha
        Gdk.cairo_set_source_rgba(ctx, rgba)

        ctx.arc(
            width / 2,
            height / 2,
            width / 2,
            -0.5 * pi,
            (2 * pie.fraction * pi) - (0.5 * pi)
        )

        if pie.fraction != 1.0:
            ctx.line_to(width / 2, height / 2)
            ctx.line_to(width / 2, 0)

        ctx.fill()


class ProgressPie(Gtk.DrawingArea):
    __gtype_name__ = "ProgressPie"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.fraction = 0

        self.set_valign(Gtk.Align.CENTER)
        self.set_halign(Gtk.Align.CENTER)

        self.set_draw_func(draw)

        self.queue_draw()

    def set_fraction(self, fraction):
        self.fraction = fraction
        self.queue_draw()
