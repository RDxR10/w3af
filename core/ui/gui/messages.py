'''
messages.py

Copyright 2007 Andres Riancho

This file is part of w3af, w3af.sourceforge.net .

w3af is free software; you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation version 2 of the License.

w3af is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with w3af; if not, write to the Free Software
Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301  USA
'''
import gtk
import gobject

import core.data.kb.knowledge_base as kb

from core.ui.gui import helpers, entries
from core.ui.gui.common.searchable import Searchable
from core.data.db.disk_list import DiskList


def getQueueDiverter(reset=False, instance=[]):
    '''Returns only one instance of the IteratedQueue.

    @author: Facundo Batista <facundobatista =at= taniquetil.com.ar>
    '''
    if reset:
        if instance:
            del instance[:]
        return
    if not instance:
        q = kb.kb.get("gtk_output", "queue")
        inst = helpers.IteratedQueue(q)
        instance.append(inst)
    return instance[0]


class _LineScroller(gtk.TextView):
    '''The text view of the Messages window.

    @author: Facundo Batista <facundobatista =at= taniquetil.com.ar>
    '''
    def __init__(self, scroll_bar, active_filter, possible):
        '''
        @param scroll_bar: Gtk Vertical Scrollbar object
        @param active_filter: the filter active at startup.
        @param possible: all filter keys
        '''
        gtk.TextView.__init__(self)
        self.set_editable(False)
        self.set_cursor_visible(False)
        self.set_wrap_mode(gtk.WRAP_WORD)
        self.textbuffer = self.get_buffer()
        self.show()
        self.messages = getQueueDiverter()
        self.all_messages = DiskList()
        self.possible = set(possible)
        self.active_filter = active_filter
        self.text_position = 0

        # scroll bar
        self.freeze_scrollbar = False
        scroll_bar.connect("value-changed", self.scroll_changed)

        # colors
        self.textbuffer.create_tag("red-fg", foreground="red")
        self.textbuffer.create_tag("blue-fg", foreground="blue")
        self.textbuffer.create_tag("brown-fg", foreground="brown")
        self.bg_colors = {
            "vulnerability": "red-fg",
            "information": "blue-fg",
            "error": "brown-fg",
        }

        gobject.timeout_add(500, self.add_message().next)

    def filter(self, filtinfo):
        '''Applies a different filter to the textview.

        @param filtinfo: the new filter
        '''
        self.active_filter = filtinfo
        textbuff = self.textbuffer
        textbuff.set_text("")
        for (mtype, text) in self.all_messages:
            if mtype in filtinfo:
                colortag = self.bg_colors[mtype]
                iterl = textbuff.get_end_iter()
                textbuff.insert_with_tags_by_name(iterl, text, colortag)
        self.scroll_to_end()

    def add_message(self):
        '''Adds a message to the textview.

        The message is read from the iterated queue.

        @returns: True to gobject to keep calling it, and False when all
                  it's done.
        '''
        textbuff = self.textbuffer
        for mess in self.messages.get():
            if mess is None:
                yield True
                continue
            text = "[%s] %s\n" % (mess.get_time(), mess.get_msg())
            mtype = mess.get_type()

            # only store it if it's of one of the possible filtered
            if mtype not in self.possible:
                continue

            # store it
            self.all_messages.append((mtype, text))
            antpos = self.text_position
            self.text_position += len(text)

            if mtype in self.active_filter:
                iterl = textbuff.get_end_iter()
                colortag = self.bg_colors[mtype]
                textbuff.insert_with_tags_by_name(iterl, text, colortag)
                self.scroll_to_end()

        yield False

    def scroll_to_end(self):
        if not self.freeze_scrollbar:
            self.scroll_to_mark(self.textbuffer.get_insert(), 0)

    def scroll_changed(self, vscrollbar):
        '''Handle scrollbar's "value-changed" signal.

        Figure out if the scroll should be frozen. If the adjustment's value
        is not in the last page's range => means it was moved up =>
        the scroll bar should be stopped.
        '''
        adj = vscrollbar.get_adjustment()
        self.freeze_scrollbar = \
            False if adj.value >= (adj.upper - adj.page_size) else True


class Messages(gtk.VBox, Searchable):
    '''The Messages window.

    It contains the checkboxes to filter and the messages theirselves.

    @author: Facundo Batista <facundobatista =at= taniquetil.com.ar>
    '''
    def __init__(self):
        gtk.VBox.__init__(self)

        # up row buttons
        upbox = gtk.HBox()
        self.filters = {}

        def make_but(label, signal, initial):
            but = gtk.CheckButton(label)
            but.set_active(initial)
            but.connect("clicked", self.type_filter, signal)
            self.filters[signal] = initial
            upbox.pack_start(but, False, False)
        make_but(_("Vulnerabilities"), "vulnerability", True)
        make_but(_("Information"), "information", True)
        make_but(_("Error"), "error", True)
        search = entries.SemiStockButton(
            _("Search"), gtk.STOCK_FIND, _("Search in the text"))
        upbox.pack_end(search, False, False)
        upbox.show_all()
        self.pack_start(upbox, expand=False, fill=False)

        # the scrolling lines
        sw_mess = gtk.ScrolledWindow()
        sw_mess.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
        newfilter = [k for k, v in self.filters.items() if v]
        self.sclines = _LineScroller(sw_mess.get_vscrollbar(),
                                     newfilter, self.filters.keys())
        sw_mess.add(self.sclines)
        sw_mess.show()
        self.pack_start(sw_mess, expand=True, fill=True)

        Searchable.__init__(self, self.sclines)
        search.connect("clicked", self.show_search)
        self.show()

    def type_filter(self, button, ptype):
        '''Applies the filter selected through the checkboxes.'''
        self.filters[ptype] = button.get_active()
        active_types = [k for k, v in self.filters.items() if v]

        # TODO: It might be a good idea to run this in a different thread?
        self.sclines.filter(active_types)
