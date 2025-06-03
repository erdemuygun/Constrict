from gi.repository import Adw, Gtk
from constrict.enums import QueuedVideoState

@Gtk.Template(resource_path='/com/github/wartybix/Constrict/sources_list_box.ui')
class SourcesListBox(Gtk.ListBox):
    __gtype_name__ = "SourcesListBox"

    add_videos_button = Gtk.Template.Child()

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.locked = False

    def remove(self, child):
        super().remove(child)
        self.update_rows()

    def remove_all(self):
        super().remove_all()
        self.append(self.add_videos_button)

    def set_locked(self, locked):
        self.locked = locked

        self.update_rows()

    def get_length(self):
        return self.add_videos_button.get_index()

    def any(self):
        return self.get_length() > 0

    def add_sources(self, video_source_rows):
        dest_index = self.get_length()

        for row in video_source_rows:
            self.insert(row, dest_index)
            dest_index += 1

        self.update_rows()

    def get_all(self):
        length = self.get_length()
        sources = []

        for i in range(length):
            row = self.get_row_at_index(i)
            sources.append(row)

        return sources

    def move(self, source_row, dest_row):
        dest_index = dest_row.get_index()

        self.remove(source_row)
        self.insert(source_row, dest_index)

        self.update_rows()

    def update_row(self, row, index=None, length=None):
        index = index or row.get_index()
        length = length or self.get_length()

        row.action_set_enabled(
            'row.move-up',
            index > 0 and not self.locked
        )
        row.action_set_enabled(
            'row.move-down',
            index < (length - 1) and not self.locked
        )
        row.action_set_enabled(
            'row.remove',
            not self.locked
        )

    def update_rows(self):
        rows = self.get_all()

        for i in range(len(rows)):
            row = rows[i]
            self.update_row(row, i, len(rows))
