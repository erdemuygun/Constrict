# window.py
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

from gi.repository import Adw, Gtk, Gdk, Gio, GLib
from constrict.constrict_utils import compress, get_encode_settings, get_resolution, get_framerate, get_duration
from constrict.enums import FpsMode, VideoCodec
import threading
import subprocess

class StagedVideo:
    def __init__(self, filepath, row, width, height, fps, duration):
        self.filepath = filepath
        self.row = row
        self.suffix = None
        self.width, self.height = width, height
        self.fps = fps
        self.duration = duration

    def clear_suffix(self):
        if self.suffix:
            self.row.remove(self.suffix)

        self.suffix = None

    def set_suffix(self, suffix):
        self.clear_suffix()

        self.row.add_suffix(suffix)
        self.suffix = suffix

    def __string__(self):
        return f'{self.filepath} - {self.width}×{self.height}@{self.fps} ({self.duration}s)'


def preview(target_size_MiB, fps_mode, width, height, fps, duration):
    encode_settings = get_encode_settings(
        target_size_MiB,
        fps_mode,
        width,
        height,
        fps,
        duration
    )

    if not encode_settings:
        return ''

    _, _, preset_height, target_fps = encode_settings

    if height > width:
        height = width

    return f'{height}p@{fps} → {preset_height}p@{target_fps}'


@Gtk.Template(resource_path='/com/github/wartybix/Constrict/window.ui')
class ConstrictWindow(Adw.ApplicationWindow):
    __gtype_name__ = 'ConstrictWindow'

    split_view = Gtk.Template.Child()
    view_stack = Gtk.Template.Child()
    export_button = Gtk.Template.Child()
    video_queue = Gtk.Template.Child()
    add_videos_button = Gtk.Template.Child()
    target_size_row = Gtk.Template.Child()
    target_size_input = Gtk.Template.Child()
    auto_row = Gtk.Template.Child()
    auto_check_button = Gtk.Template.Child()
    clear_row = Gtk.Template.Child()
    clear_check_button = Gtk.Template.Child()
    smooth_row = Gtk.Template.Child()
    smooth_check_button = Gtk.Template.Child()
    codec_dropdown = Gtk.Template.Child()
    extra_quality_toggle = Gtk.Template.Child()
    tolerance_row = Gtk.Template.Child()
    tolerance_input = Gtk.Template.Child()

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.staged_videos = []

        self.toggle_sidebar_action = Gio.SimpleAction(name="toggle-sidebar")
        self.toggle_sidebar_action.connect("activate", self.toggle_sidebar)
        self.add_action(self.toggle_sidebar_action)

        self.open_action = Gio.SimpleAction(name="open")
        self.open_action.connect("activate", self.open_file_dialog)
        self.add_action(self.open_action)

        self.export_action = Gio.SimpleAction(name="export")
        self.export_action.connect("activate", self.export_file_dialog)
        self.export_action.set_enabled(bool(self.staged_videos))
        self.add_action(self.export_action)

        self.clear_all_action = Gio.SimpleAction(name="clear_all")
        self.clear_all_action.connect("activate", self.delist_all)
        self.add_action(self.clear_all_action)

        self.target_size_input.connect("value-changed", self.refresh_previews)
        self.auto_check_button.connect("activate", self.refresh_previews)
        self.clear_check_button.connect("activate", self.refresh_previews)
        self.smooth_check_button.connect("activate", self.refresh_previews)

        self.settings = Gio.Settings(schema_id='com.github.wartybix.Constrict')
        self.settings.bind(
            'window-width',
            self,
            'default-width',
            Gio.SettingsBindFlags.GET | Gio.SettingsBindFlags.GET_NO_CHANGES
        )
        self.settings.bind(
            'window-height',
            self,
            'default-height',
            Gio.SettingsBindFlags.GET | Gio.SettingsBindFlags.GET_NO_CHANGES
        )
        self.settings.bind(
            'window-maximized',
            self,
            'maximized',
            Gio.SettingsBindFlags.GET | Gio.SettingsBindFlags.GET_NO_CHANGES
        )
        self.settings.bind(
            'target-size',
            self.target_size_input,
            'value',
            Gio.SettingsBindFlags.GET | Gio.SettingsBindFlags.GET_NO_CHANGES
        )
        self.settings.bind(
            'extra-quality',
            self.extra_quality_toggle,
            'active',
            Gio.SettingsBindFlags.GET | Gio.SettingsBindFlags.GET_NO_CHANGES
        )
        self.settings.bind(
            'tolerance',
            self.tolerance_input,
            'value',
            Gio.SettingsBindFlags.GET | Gio.SettingsBindFlags.GET_NO_CHANGES
        )

        fps_mode = self.settings.get_enum('fps-mode')
        video_codec = self.settings.get_enum('video-codec')

        self.set_fps_mode(fps_mode)
        self.set_video_codec(video_codec)

        content = Gdk.ContentFormats.new_for_gtype(Gdk.FileList)
        target = Gtk.DropTarget(formats=content, actions=Gdk.DragAction.COPY)
        target.connect('drop', self.on_drop)
        target.connect('enter', self.on_enter)

        self.view_stack.add_controller(target)

        # TRANSLATORS: 'FPS' meaning 'frames per second'.
        # {} represents the FPS value, for example 30 or 60.
        # Please use U+202F Narrow no-break space (' ') between value and unit.
        fps_label = _('{} FPS')

        self.clear_row.set_title(fps_label.format('30'))
        self.smooth_row.set_title(fps_label.format('60'))


    def on_drop(self, drop_target, value: Gdk.FileList, x, y, user_data=None):
        files: List[Gio.File] = value.get_files()

        self.stage_videos(files)

    def on_enter(self, drop_target, x, y):
        # Custom code...
        # Tell the callee to continue
        return Gdk.DragAction.COPY

    def set_controls_lock(self, is_locked):
        self.target_size_row.set_sensitive(not is_locked)
        self.auto_row.set_sensitive(not is_locked)
        self.clear_row.set_sensitive(not is_locked)
        self.smooth_row.set_sensitive(not is_locked)
        self.codec_dropdown.set_sensitive(not is_locked)
        self.extra_quality_toggle.set_sensitive(not is_locked)
        self.tolerance_row.set_sensitive(not is_locked)

        self.clear_all_action.set_enabled(not is_locked)
        self.export_action.set_enabled(not is_locked)

    def refresh_previews(self, _):
        target_size = self.get_target_size()
        fps_mode = self.get_fps_mode()

        for video in self.staged_videos:
            subtitle = preview(
                target_size,
                fps_mode,
                video.width,
                video.height,
                video.fps,
                video.duration
            )
            video.row.set_subtitle(subtitle)

    def get_target_size(self):
        return int(self.target_size_input.get_value())

    def get_fps_mode(self):
        if self.auto_check_button.get_active():
            return FpsMode.AUTO
        if self.clear_check_button.get_active():
            return FpsMode.PREFER_CLEAR
        if self.smooth_check_button.get_active():
            return FpsMode.PREFER_SMOOTH

        raise Exception('Tried to get fps mode, but none was set.')

    def set_fps_mode(self, mode):
        match mode:
            case FpsMode.AUTO:
                self.auto_check_button.set_active(True)
            case FpsMode.PREFER_CLEAR:
                self.clear_check_button.set_active(True)
            case FpsMode.PREFER_SMOOTH:
                self.smooth_check_button.set_active(True)
            case _:
                self.auto_check_button.set_active(True)

    def get_video_codec(self):
        return self.codec_dropdown.get_selected()

    def set_video_codec(self, codec_index):
        self.codec_dropdown.set_selected(codec_index)

    def get_extra_quality(self):
        return self.extra_quality_toggle.get_active()

    def get_tolerance(self):
        return int(self.tolerance_input.get_value())

    def toggle_sidebar(self, action, _):
        sidebar_shown = self.split_view.get_show_sidebar()
        self.split_view.set_show_sidebar(not sidebar_shown)

    def delist_all(self, action, _):
        for video in self.staged_videos:
            self.video_queue.remove(video.row)

        self.staged_videos = []

        self.view_stack.set_visible_child_name('status_page')
        self.export_action.set_enabled(False)

    def export_file_dialog(self, action, parameter):
        native = Gtk.FileDialog()

        # TODO: change folder select UI? idk
        native.select_folder(self, None, self.on_export_response)

    def on_export_response(self, dialog, result):
        # TODO: process video locally before moving to real directory?
        # TODO: remove multi-window file conflicts by checking if file exists
        # on pass 2 (rather than at the start)
        # TODO: cancel compression on window close (w/ dialog)

        folder = dialog.select_folder_finish(result)

        if not folder:
            return

        folder_path = folder.get_path()
        print(folder_path)

        thread = threading.Thread(target=self.bulk_compress, args=[folder_path])
        thread.daemon = True
        thread.start()

    def bulk_compress(self, destination):
        self.set_controls_lock(True)

        target_size = self.get_target_size()
        fps_mode = self.get_fps_mode()
        codec = self.get_video_codec()
        extra_quality = self.get_extra_quality()
        tolerance = self.get_tolerance()

        for video in self.staged_videos:
            # compressing_text = Gtk.Label.new('Compressing…')

            # TODO: look into compact progress bar...
            progress_bar = Gtk.ProgressBar()
            progress_bar.set_valign(Gtk.Align['CENTER'])
            progress_bar.set_show_text(True)
            if codec == VideoCodec.VP9:
                # TRANSLATORS: please use U+2026 Horizontal ellipsis (…) instead of '...', if applicable to your language
                progress_bar.set_text(_('Analyzing…'))
            video.set_suffix(progress_bar)

            def update_progress(fraction):
                print(f'progress updated - {round(fraction * 100)}%')
                if fraction == 0.0 and codec == VideoCodec.VP9:
                    GLib.idle_add(progress_bar.pulse)
                    print('pulsed')
                else:
                    if progress_bar.get_text():
                        GLib.idle_add(progress_bar.set_text, None)
                    GLib.idle_add(progress_bar.set_fraction, fraction)

            # def update_txt: compressing_text.set_label

            compress(
                video.filepath,
                target_size,
                fps_mode,
                extra_quality,
                codec,
                tolerance,
                destination,
                update_progress,
                self.get_id()
            )

            complete_text = Gtk.Label.new(_('Complete'))
            complete_text.add_css_class('success')

            video.set_suffix(complete_text)

        self.set_controls_lock(False)

    def fetch_thumbnail(self, video_path):
        subprocess.run(['totem-video-thumbnailer', video_path, 'thumb.jpg'])

        img = Gtk.Image.new_from_file('thumb.jpg')
        img.set_pixel_size(64)
        img.set_valign(Gtk.Align.CENTER)
        img.add_css_class('icon-dropshadow')

        return img

    def stage_videos(self, video_list):
        # TODO: better error handling
        # ie. corrupt files etc.
        self.video_queue.remove(self.add_videos_button)

        existing_paths = list(map(lambda x: x.filepath, self.staged_videos))
        print(f'existing: {existing_paths}')

        for video in video_list:
            # TODO: make async query?
            video_path = video.get_path()

            if video_path in existing_paths:
                continue

            info = video.query_info(
                'standard::display-name,standard::content-type',
                Gio.FileQueryInfoFlags.NONE
            )
            content_type = info.get_content_type()
            print(f'content type: {content_type}')

            if not content_type:
                continue

            is_video = content_type.startswith('video/')
            print(f'IS VIDEO: {is_video}')

            if not is_video:
                continue

            display_name = info.get_display_name() if info else video.get_basename()
            print(f'{video.get_basename()} - {video_path}')

            # TODO: Add thumbnail -- I think Nautilus generates one from a
            # frame 1/3 through the video

            target_size = self.get_target_size()
            fps_mode = self.get_fps_mode()

            action_row = Adw.ActionRow()
            action_row.set_title(display_name)

            # cache metadata
            width, height = get_resolution(video)
            fps = get_framerate(video)
            duration = get_duration(video)

            # TODO: don't forget, perhaps change this for RTL users
            subtitle = preview(target_size, fps_mode, width, height, fps, duration)
            action_row.set_subtitle(subtitle)

            action_row.set_valign(Gtk.Align.FILL)

            thumb = self.fetch_thumbnail(video)

            thumb.set_margin_top(4)
            thumb.set_margin_bottom(4)
            thumb.set_margin_end(4)

            action_row.add_prefix(thumb)

            self.video_queue.add(action_row)

            staged_video = StagedVideo(video.get_path(), action_row, width, height, fps, duration)
            self.staged_videos.append(staged_video)

        self.video_queue.add(self.add_videos_button)

        if self.staged_videos:
            self.view_stack.set_visible_child_name('queue_page')

        self.export_action.set_enabled(True)
        self.export_button.grab_focus()

    def open_file_dialog(self, action, parameter):
        # Create new file selection dialog, using "open" mode
        native = Gtk.FileDialog()
        video_filter = Gtk.FileFilter()

        video_filter.add_mime_type('video/*')
        video_filter.set_name(_('Videos'))

        native.set_default_filter(video_filter)
        native.set_title(_('Pick Videos'))

        native.open_multiple(self, None, self.on_open_response)

    def on_open_response(self, dialog, result):
        files = dialog.open_multiple_finish(result)

        if not files:
            return

        self.stage_videos(files)

        existing_paths = list(map(lambda x: x.filepath, self.staged_videos))
        print(f'new list: {existing_paths}')

    def save_window_state(self):
        self.settings.set_boolean('window-maximized', self.is_maximized())

        width, height = self.get_default_size()
        self.settings.set_int('window-width', width)
        self.settings.set_int('window-height', height)
        self.settings.set_int('target-size', self.get_target_size())
        self.settings.set_enum('fps-mode', self.get_fps_mode())
        self.settings.set_enum('video-codec', self.get_video_codec())
        self.settings.set_boolean('extra-quality', self.get_extra_quality())
        self.settings.set_int('tolerance', self.get_tolerance())

    def do_close_request(self):
        print('close request made')

        self.save_window_state()

        return False
