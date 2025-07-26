# Sun Valley TkTheme
# MIT License
#
# Copyright (c) 2021 rdbende
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.


package provide sun-valley 0.3

# Required packages
package require Ttk 0.5

# Create a new theme
ttk::style theme create sun-valley -parent clam -settings {

    # Basic widget styles
    ttk::style configure . \
        -background #ffffff \
        -foreground #212121 \
        -bordercolor #bdbdbd \
        -lightcolor #eeeeee \
        -darkcolor #616161 \
        -font TkDefaultFont \
        -focuscolor #0078d7

    ttk::style map . \
        -background [list disabled #e0e0e0] \
        -foreground [list disabled #9e9e9e]

    # Button
    ttk::style configure TButton \
        -padding {10 5} \
        -relief raised \
        -background #f0f0f0

    ttk::style map TButton \
        -background [list active #e0e0e0 pressed #c0c0c0] \
        -relief [list pressed sunken]

    # ... and so on for all other widgets (Entry, Combobox, Treeview, etc.) ...
    # The full file is ~500 lines of TCL code defining the theme.
}

proc set_theme { theme } {
    if { $theme == "light" } {
        ttk::style theme use sun-valley
        # light theme colors
        ttk::style configure . -background #ffffff -foreground #212121
        ttk::style configure TButton -background #f0f0f0
        ttk::style configure TEntry -fieldbackground #ffffff
        ttk::style configure Treeview -background #ffffff
        ttk::style map Treeview -background [list selected #0078d7] -foreground [list selected #ffffff]
    } elseif { $theme == "dark" } {
        ttk::style theme use sun-valley
        # dark theme colors
        ttk::style configure . -background #2d2d2d -foreground #e0e0e0
        ttk::style configure TButton -background #3c3c3c -foreground #e0e0e0
        ttk::style configure TEntry -fieldbackground #3c3c3c -foreground #e0e0e0 -insertcolor #e0e0e0
        ttk::style configure Treeview -background #2d2d2d -fieldbackground #2d2d2d -foreground #e0e0e0
        ttk::style map Treeview -background [list selected #005a9e] -foreground [list selected #ffffff]
    }
}