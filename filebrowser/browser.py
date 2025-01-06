import os
import subprocess
import shutil

from textual.reactive import var, reactive
from textual.fuzzy import Matcher

from rich.style import Style
from rich.text import Text

from .directory import Directory


MATCH_STYLE = Style(color='#8aadf4', bold=True)


class Browser(Directory):

    matcher = None
    selected = var(0)
    selected_value = var(None)
    created = None

    def on_mount(self):
        self.watch(self.screen.query_one('#search'), 'value', self.set_filter)

    def set_filter(self, filter):
        if filter:
            self.matcher = Matcher(filter, match_style=MATCH_STYLE)
        else:
            self.matcher = None

        self.set_values()
        self.refresh(recompose=True)

    def set_values(self):
        super().set_values()

        if self.matcher:
            self.values = sorted(
                filter(self.matcher.match, self.values),
                key=self.matcher.match,
                reverse=True,
            )

        if self.created:
            self.selected = self.values.index(self.created)
            self.created = None
        else:
            self.selected = 0

        self.watch_selected(self.selected)

    def watch_selected(self, selected):
        if self.values:
            self.selected_value = self.values[selected]
        else:
            self.selected_value = None

    def render_value(self, value):
        if self.matcher:
            return self.matcher.highlight(value)
        else:
            return Text(value)

    def action_nav_up(self):
        self.selected = (self.selected - 1) % len(self.values)

    def action_nav_down(self):
        self.selected = (self.selected + 1) % len(self.values)

    @property
    def selected_path(self):
        match self.selected_value:
            case None:
                return None
            case '..':
                return self.path.parent
            case value:
                return self.path / value

    def action_select(self):
        if not (path := self.selected_path):
            return

        if path.is_dir():
            self.path = path
            self.screen.query_one('Input').value = ''

        elif path.is_file():
            editor = (
                os.environ.get('EDITOR') or
                os.environ.get('VISUAL') or
                'vi'
            )

            with self.app.suspend():
                subprocess.run([editor, str(path)])

            self.app.refresh()
            self.screen.query_one('Preview').refresh(recompose=True)

    def action_toggle_hidden(self):
        self.show_hidden = not self.show_hidden

    def action_create(self):
        @self.app.prompt('create file or directory')
        def create_name(name):
            is_dir = name.endswith('/')
            path = self.path / name

            if is_dir:
                path.mkdir(exist_ok=True, parents=True)
                path = self.path
            else:
                path.parent.mkdir(exist_ok=True, parents=True)
                path.touch()

                self.created = path.name
                if path.parent == self.path:
                    self.set_values()
                    self.refresh(recompose=True)
                else:
                    self.path = path.parent

    def action_rename(self):
        if self.selected_value in (None, '..'):
            return
        path = self.selected_path

        @self.app.prompt(f'rename {path.name}', default=path.name)
        def rename(name):
            name = name.rstrip('/')
            is_dir = path.is_dir()

            path.rename(name)

            if is_dir:
                name += '/'

            child = self.children[self.selected]
            child.value = name
            child.text = self.render_value(name)
            child.refresh()

            self.values[self.selected] = name
            self.selected_value = name

    def action_delete(self):
        if self.selected_value in (None, '..'):
            return
        path = self.selected_path

        if path.is_dir():
            shutil.rmtree(path)
        else:
            path.unlink()

        self.values.pop(self.selected)
        if not self.values:
            self.selected_value = None
        elif self.selected == len(self.values):
            self.selected -= 1
        else:
            self.selected_value = self.values[self.selected]

        self.refresh(recompose=True)

    class Child(Directory.Child):

        selected = reactive(False)

        def on_mount(self):
            self.watch(self.parent, 'selected_value', self.check_selected)

        def check_selected(self, selected_value):
            self.selected = selected_value == self.value

        def watch_selected(self, selected):
            if selected:
                self.add_class('selected')
            else:
                self.remove_class('selected')

        def render(self):
            text = super().render()
            if self.selected:
                return Text('> ').append_text(text)
            else:
                return Text('  ').append_text(text)
