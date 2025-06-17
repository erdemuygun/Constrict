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

from gi.repository import Adw, Gtk, Gdk, Gio, GLib, GObject
from constrict.constrict_utils import compress
from constrict.shared import get_tmp_dir
from constrict.enums import FpsMode, VideoCodec, SourceState
from constrict.sources_row import SourcesRow
from constrict.sources_list_box import SourcesListBox
from constrict.error_dialog import ErrorDialog
import threading
import subprocess
from pathlib import Path


@Gtk.Template(resource_path='/com/github/wartybix/Constrict/window.ui')
class ConstrictWindow(Adw.ApplicationWindow):
    __gtype_name__ = 'ConstrictWindow'

    split_view = Gtk.Template.Child()
    view_stack = Gtk.Template.Child()
    export_bar = Gtk.Template.Child()
    export_button = Gtk.Template.Child()
    cancel_bar = Gtk.Template.Child()
    cancel_button = Gtk.Template.Child()
    sources_list_box = Gtk.Template.Child()
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
    toast_overlay = Gtk.Template.Child()

    # TODO: add dialog on window close

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.cancelled = False
        self.currently_processed = ''

        self.toggle_sidebar_action = Gio.SimpleAction(name="toggle-sidebar")
        self.toggle_sidebar_action.connect("activate", self.toggle_sidebar)
        self.add_action(self.toggle_sidebar_action)

        self.open_action = Gio.SimpleAction(name="open")
        self.open_action.connect("activate", self.open_file_dialog)
        self.add_action(self.open_action)

        self.export_action = Gio.SimpleAction(name="export")
        self.export_action.connect("activate", self.export_file_dialog)
        self.export_action.set_enabled(bool(self.sources_list_box.any()))
        self.add_action(self.export_action)

        self.cancel_action = Gio.SimpleAction(name="cancel")
        self.cancel_action.connect("activate", self.cancel_dialog)
        self.add_action(self.cancel_action)

        self.clear_all_action = Gio.SimpleAction(name="clear_all")
        self.clear_all_action.connect("activate", self.delist_all)
        self.add_action(self.clear_all_action)

        self.target_size_input.connect("value-changed", self.refresh_previews)
        self.auto_check_button.connect("toggled", self.refresh_previews)
        self.clear_check_button.connect("toggled", self.refresh_previews)
        self.smooth_check_button.connect("toggled", self.refresh_previews)

        self.codec_dropdown.connect("notify::selected", self.refresh_previews)
        self.extra_quality_toggle.connect(
            "notify::active",
            self.refresh_previews
        )
        self.tolerance_input.connect("value-changed", self.refresh_previews)

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

        self.sources_list_box.set_locked(is_locked)

    # Return whether the passed widget is an unchecked GtkCheckButton
    def is_unchecked_checkbox(self, widget):
        return type(widget) is Gtk.CheckButton and not widget.get_active()

    def set_warning_state(self, is_error):
        self.export_action.set_enabled(not is_error)

    def refresh_can_export(self):
        sources = self.sources_list_box.get_all()

        if not sources:
            self.export_action.set_enabled(False)
            self.view_stack.set_visible_child_name('status_page')
            return

        for video in sources:
            if video.state in [SourceState.BROKEN, SourceState.INCOMPATIBLE]:
                self.set_warning_state(True)
                return

        self.set_warning_state(False)

    def refresh_previews(self, widget, *args):
        # Return if called from a check button being 'unchecked'
        if self.is_unchecked_checkbox(widget):
            return

        sources = self.sources_list_box.get_all()

        for video in sources:
            video.set_preview(self.get_target_size, self.get_fps_mode)

        self.refresh_can_export()

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
        self.sources_list_box.remove_all()
        self.refresh_can_export()

    def show_cancel_button(self, is_compressing):
        self.cancel_bar.set_visible(is_compressing)
        self.export_bar.set_visible(not is_compressing)

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

    def cancel_dialog(self, action, parameter):
        dialog = Adw.AlertDialog.new(
            _('Stop Compression?'),
            # TRANSLATORS: {} represents the filename of the video currently
            # being compressed. Please use “” instead of "", if applicable to
            # your language.
            _(
                'Progress made compressing “{}” will be permanently lost'
            ).format(self.currently_processed)
        )

        dialog.add_response('cancel', _('Cancel'))
        dialog.add_response('stop', _('Stop'))

        dialog.set_response_appearance(
            'stop',
            Adw.ResponseAppearance.DESTRUCTIVE
        )

        dialog.choose(self, None, self.on_cancel_response)

    def on_cancel_response(self, dialog, result):
        choice = dialog.choose_finish(result)

        if choice == 'stop':
            print('Compression stopped')
            self.cancelled = True

    def error_dialog(self, file_name, error_details):
        dialog = ErrorDialog(file_name, error_details)

        dialog.present(self)

    def show_error_from_toast(self, toast):
        self.error_dialog(toast.video.display_name, toast.video.error_details)

    def bulk_compress(self, destination):
        self.set_controls_lock(True)
        self.show_cancel_button(True)

        target_size = self.get_target_size()
        fps_mode = self.get_fps_mode()
        codec = self.get_video_codec()
        extra_quality = self.get_extra_quality()
        tolerance = self.get_tolerance()

        source_list = self.sources_list_box.get_all()

        for video in source_list:
            self.currently_processed = video.display_name

            # TODO: check multiple attempts on VP9... will it still display
            # 'analyzing' prompts on attempt 2+?
            # TODO: have VP9 reset to 0% on pass 2, not 50%.

            if codec == VideoCodec.VP9:
                # TRANSLATORS: please use U+2026 Horizontal ellipsis (…) instead of '...', if applicable to your language
                GLib.idle_add(video.set_progress_text, _('Analyzing…'))
                GLib.idle_add(video.enable_spinner, True)

            def update_progress(fraction):
                print(f'progress updated - {round(fraction * 100)}%')
                if fraction == 0.0 and codec == VideoCodec.VP9:
                    GLib.idle_add(video.pulse_progress)
                    print('pulsed')
                else:
                    if video.get_progress_text():
                        GLib.idle_add(video.set_progress_text, None)
                        GLib.idle_add(video.enable_spinner, False)
                    GLib.idle_add(video.set_progress_fraction, fraction)

            GLib.idle_add(video.set_state, SourceState.COMPRESSING)

            tmp_dir = get_tmp_dir()
            log_filename = f'constrict2pass-{self.get_id()}'

            log_path = str(tmp_dir / log_filename) if (
                tmp_dir
            ) else str(Path(destination) / log_filename)

            compress_error = compress(
                video.video_path,
                target_size,
                fps_mode,
                extra_quality,
                codec,
                tolerance,
                destination,
                update_progress,
                log_path,
                lambda: self.cancelled
            )

            if compress_error:
                GLib.idle_add(video.set_error, compress_error)

                # TRANSLATORS: {} represents the filename of the video with the
                # error.
                # Please use “” instead of "", if applicable to your language.
                toast = Adw.Toast.new(_(
                    'Error compressing “{}”'.format(video.display_name)
                ))
                toast.set_button_label(_('View Details'))
                toast.video = video

                toast.connect('button-clicked', self.show_error_from_toast)

                GLib.idle_add(self.toast_overlay.add_toast, toast)

                continue

            if self.cancelled:
                GLib.idle_add(video.set_state, SourceState.PENDING)
                break

            GLib.idle_add(video.set_state, SourceState.COMPLETE)

        GLib.idle_add(self.set_controls_lock, False)
        GLib.idle_add(self.show_cancel_button, False)

        toast = Adw.Toast.new(_('Compression Complete'))
        GLib.idle_add(self.toast_overlay.add_toast, toast)

        self.cancelled = False

    def remove_row(self, widget, action_name, parameter):
        self.sources_list_box.remove(widget)
        self.refresh_can_export()

    def stage_videos(self, video_list):
        # TODO: better error handling
        # ie. corrupt files etc.
        # TODO: merge staged video list with UI?

        existing_paths = list(map(
            lambda x: x.video_path,
            self.sources_list_box.get_all()
        ))
        print(f'existing: {existing_paths}')

        staged_rows = []

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

            staged_row = SourcesRow(
                video.get_path(),
                display_name,
                video.hash(),
                self.get_target_size,
                self.get_fps_mode,
                self.error_dialog,
                self.set_warning_state
            )

            staged_row.install_action('row.remove', None, self.remove_row)

            staged_rows.append(staged_row)

        self.sources_list_box.add_sources(staged_rows)

        if self.sources_list_box.any():
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

        existing_paths = list(map(
            lambda x: x.video_path,
            self.sources_list_box.get_all()
        ))
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
