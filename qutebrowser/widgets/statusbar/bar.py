# Copyright 2014 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
#
# This file is part of qutebrowser.
#
# qutebrowser is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# qutebrowser is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with qutebrowser.  If not, see <http://www.gnu.org/licenses/>.

"""The main statusbar widget."""

import logging
from collections import deque

from PyQt5.QtCore import pyqtSignal, pyqtSlot, pyqtProperty, Qt, QTimer
from PyQt5.QtWidgets import QWidget, QHBoxLayout, QStackedLayout, QSizePolicy

import qutebrowser.keyinput.modeman as modeman
import qutebrowser.config.config as config
from qutebrowser.widgets.statusbar._command import Command
from qutebrowser.widgets.statusbar._progress import Progress
from qutebrowser.widgets.statusbar._text import Text
from qutebrowser.widgets.statusbar._keystring import KeyString
from qutebrowser.widgets.statusbar._percentage import Percentage
from qutebrowser.widgets.statusbar._url import Url
from qutebrowser.config.style import set_register_stylesheet, get_stylesheet


class StatusBar(QWidget):

    """The statusbar at the bottom of the mainwindow.

    Class attributes:
        STYLESHEET: The stylesheet template.

    Attributes:
        cmd: The Command widget in the statusbar.
        txt: The Text widget in the statusbar.
        keystring: The KeyString widget in the statusbar.
        percentage: The Percentage widget in the statusbar.
        url: The Url widget in the statusbar.
        prog: The Progress widget in the statusbar.
        _hbox: The main QHBoxLayout.
        _stack: The QStackedLayout with cmd/txt widgets.
        _text_queue: A deque of (error, text) tuples to be displayed.
                     error: True if message is an error, False otherwise
        _text_pop_timer: A QTimer displaying the error messages.

    Class attributes:
        _error: If there currently is an error, accessed through the error
                property.

                For some reason we need to have this as class attribute so
                pyqtProperty works correctly.

    Signals:
        resized: Emitted when the statusbar has resized, so the completion
                 widget can adjust its size to it.
                 arg: The new size.
        moved: Emitted when the statusbar has moved, so the completion widget
               can move the the right position.
               arg: The new position.
    """

    resized = pyqtSignal('QRect')
    moved = pyqtSignal('QPoint')
    _error = False

    STYLESHEET = """
        QWidget#StatusBar[error="false"] {{
            {color[statusbar.bg]}
        }}

        QWidget#StatusBar[error="true"] {{
            {color[statusbar.bg.error]}
        }}

        QWidget {{
            {color[statusbar.fg]}
            {font[statusbar]}
        }}
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName(self.__class__.__name__)
        self.setAttribute(Qt.WA_StyledBackground)
        set_register_stylesheet(self)

        self.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Fixed)

        self._option = None

        self._hbox = QHBoxLayout(self)
        self._hbox.setContentsMargins(0, 0, 0, 0)
        self._hbox.setSpacing(5)

        self._stack = QStackedLayout()
        self._stack.setContentsMargins(0, 0, 0, 0)

        self.cmd = Command(self)
        self._stack.addWidget(self.cmd)

        self.txt = Text(self)
        self._stack.addWidget(self.txt)
        self._text_queue = deque()
        self._text_pop_timer = QTimer()
        self._text_pop_timer.setInterval(
            config.get('general', 'message-timeout'))
        self._text_pop_timer.timeout.connect(self._pop_text)

        self.cmd.show_cmd.connect(self._show_cmd_widget)
        self.cmd.hide_cmd.connect(self._hide_cmd_widget)
        self._hide_cmd_widget()

        self._hbox.addLayout(self._stack)

        self.keystring = KeyString(self)
        self._hbox.addWidget(self.keystring)

        self.url = Url(self)
        self._hbox.addWidget(self.url)

        self.percentage = Percentage(self)
        self._hbox.addWidget(self.percentage)

        self.prog = Progress(self)
        self._hbox.addWidget(self.prog)

    @pyqtProperty(bool)
    def error(self):
        """Getter for self.error, so it can be used as Qt property."""
        # pylint: disable=method-hidden
        return self._error

    @error.setter
    def error(self, val):
        """Setter for self.error, so it can be used as Qt property.

        Re-set the stylesheet after setting the value, so everything gets
        updated by Qt properly.
        """
        self._error = val
        self.setStyleSheet(get_stylesheet(self.STYLESHEET))

    def _pop_text(self):
        """Display a text in the statusbar and pop it from _text_queue."""
        try:
            error, text = self._text_queue.popleft()
        except IndexError:
            self.error = False
            self.txt.temptext = ''
            self._text_pop_timer.stop()
            return
        logging.debug("Displaying {} message: {}".format(
            'error' if error else 'text', text))
        logging.debug("Remaining: {}".format(self._text_queue))
        self.error = error
        self.txt.temptext = text

    def _show_cmd_widget(self):
        """Show command widget instead of temporary text."""
        self._text_pop_timer.stop()
        self._stack.setCurrentWidget(self.cmd)

    def _hide_cmd_widget(self):
        """Show temporary text instead of command widget."""
        if self._text_queue and not self._text_pop_timer.isActive():
            self._pop_text()
            self._text_pop_timer.start()
        self._stack.setCurrentWidget(self.txt)

    @pyqtSlot(str)
    def disp_error(self, text):
        """Display an error in the statusbar."""
        self._text_queue.append((True, text))
        self._text_pop_timer.start()

    @pyqtSlot(str)
    def disp_temp_text(self, text):
        """Add a temporary text to the queue."""
        self._text_queue.append((False, text))
        self._text_pop_timer.start()

    @pyqtSlot(str)
    def set_text(self, val):
        """Set a normal (persistent) text in the status bar."""
        self.txt.normaltext = val

    @pyqtSlot(str)
    def on_mode_entered(self, mode):
        """Mark certain modes in the commandline."""
        if mode in modeman.instance().passthrough:
            self.txt.normaltext = "-- {} MODE --".format(mode.upper())

    @pyqtSlot(str)
    def on_mode_left(self, mode):
        """Clear marked mode."""
        if mode in modeman.instance().passthrough:
            self.txt.normaltext = ""

    @pyqtSlot(str)
    def on_statusbar_message(self, val):
        """Called when javascript tries to set a statusbar message.

        For some reason, this is emitted a lot with an empty string during page
        load, so we currently ignore these and thus don't support clearing the
        message, which is a bit unfortunate...
        """
        if val:
            self.txt.temptext = val

    @pyqtSlot(str, str)
    def on_config_changed(self, section, option):
        """Update message timeout when config changed."""
        if section == 'general' and option == 'message-timeout':
            self._text_pop_timer.setInterval(
                config.get('general', 'message-timeout'))

    def resizeEvent(self, e):
        """Extend resizeEvent of QWidget to emit a resized signal afterwards.

        Args:
            e: The QResizeEvent.

        Emit:
            resized: Always emitted.
        """
        super().resizeEvent(e)
        self.resized.emit(self.geometry())

    def moveEvent(self, e):
        """Extend moveEvent of QWidget to emit a moved signal afterwards.

        Args:
            e: The QMoveEvent.

        Emit:
            moved: Always emitted.
        """
        super().moveEvent(e)
        self.moved.emit(e.pos())
