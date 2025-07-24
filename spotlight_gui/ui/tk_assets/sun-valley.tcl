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


# Default light theme colors
set_light_theme_colors
proc set_light_theme_colors {} {
    global tkThemeColors

    # Base Colors
    set tkThemeColors(bg)                  #fff
    set tkThemeColors(fg)                  #000
    set tkThemeColors(primary)             #0078d7
    set tkThemeColors(secondary)           #00599f
    set tkThemeColors(tertiary)            #eff3f7

    # Accent Colors
    set tkThemeColors(accent)              #5b5b5b
    set tkThemeColors(text)                #000
    set tkThemeColors(active)              #e1e5e8
    set tkThemeColors(selectbg)            #d5e7f6
    set tkThemeColors(selectfg)            #000
    set tkThemeColors(disabled)            #a8a8a8
    set tkThemeColors(border)              #c1c1c1
    set tkThemeColors(field)               #eee
    set tkThemeColors(focus)               #0078d7
    set tkThemeColors(error)               #dc3545
    set tkThemeColors(success)             #28a745
    set tkThemeColors(info)                #17a2b8
    set tkThemeColors(warning)             #ffc107

    # Extended Colors
    set tkThemeColors(lightbg)             #f2f6f9
    set tkThemeColors(darkbg)              #dae2e8
    set tkThemeColors(lightfg)             #757575
    set tkThemeColors(darkfg)              #000
    set tkThemeColors(lightprimary)        #7ab8f3
    set tkThemeColors(darkprimary)         #004e8d
    set tkThemeColors(lightsecondary)      #529ed8
    set tkThemeColors(darksecondary)       #003867
    set tkThemeColors(lighttertiary)       #f7fbfc
    set tkThemeColors(darktertiary)        #d7dde2
    set tkThemeColors(lightaccent)         #a8a8a8
    set tkThemeColors(darkaccent)          #4d4d4d
    set tkThemeColors(lightborder)         #e0e0e0
    set tkThemeColors(darkborder)          #999
    set tkThemeColors(lightfield)          #f8f8f8
    set tkThemeColors(darkfield)           #d0d0d0
    set tkThemeColors(lightfocus)          #a8d2f7
    set tkThemeColors(darkfocus)           #0060a6
    set tkThemeColors(lighterror)          #f19696
    set tkThemeColors(darkerror)           #b12b38
    set tkThemeColors(lightsuccess)        #90c490
    set tkThemeColors(darksuccess)         #208036
    set tkThemeColors(lightinfo)           #8ad5e0
    set tkThemeColors(darkinfo)            #138194
    set tkThemeColors(lightwarning)        #fff0b3
    set tkThemeColors(darkwarning)         #cfa000
}


# Default dark theme colors
proc set_dark_theme_colors {} {
    global tkThemeColors

    # Base Colors
    set tkThemeColors(bg)                  #323232
    set tkThemeColors(fg)                  #fff
    set tkThemeColors(primary)             #4292dc
    set tkThemeColors(secondary)           #2b74b1
    set tkThemeColors(tertiary)            #2c2c2c

    # Accent Colors
    set tkThemeColors(accent)              #a8a8a8
    set tkThemeColors(text)                #fff
    set tkThemeColors(active)              #3c3c3c
    set tkThemeColors(selectbg)            #3c3c3c
    set tkThemeColors(selectfg)            #fff
    set tkThemeColors(disabled)            #a8a8a8
    set tkThemeColors(border)              #4a4a4a
    set tkThemeColors(field)               #3d3d3d
    set tkThemeColors(focus)               #4292dc
    set tkThemeColors(error)               #dc3545
    set tkThemeColors(success)             #28a745
    set tkThemeColors(info)                #17a2b8
    set tkThemeColors(warning)             #ffc107

    # Extended Colors
    set tkThemeColors(lightbg)             #3c3c3c
    set tkThemeColors(darkbg)              #2a2a2a
    set tkThemeColors(lightfg)             #ccc
    set tkThemeColors(darkfg)              #fff
    set tkThemeColors(lightprimary)        #85b2e3
    set tkThemeColors(darkprimary)         #2f638f
    set tkThemeColors(lightsecondary)      #6297ce
    set tkThemeColors(darksecondary)       #1e5b8a
    set tkThemeColors(lighttertiary)       #323232
    set tkThemeColors(darktertiary)        #252525
    set tkThemeColors(lightaccent)         #e1e1e1
    set tkThemeColors(darkaccent)          #8e8e8e
    set tkThemeColors(lightborder)         #5a5a5a
    set tkThemeColors(darkborder)          #3c3c3c
    set tkThemeColors(lightfield)          #484848
    set tkThemeColors(darkfield)           #363636
    set tkThemeColors(lightfocus)          #72b3eb
    set tkThemeColors(darkfocus)           #2f6cb0
    set tkThemeColors(lighterror)          #f19696
    set tkThemeColors(darkerror)           #b12b38
    set tkThemeColors(lightsuccess)        #90c490
    set tkThemeColors(darksuccess)         #208036
    set tkThemeColors(lightinfo)           #8ad5e0
    set tkThemeColors(darkinfo)            #138194
    set tkThemeColors(lightwarning)        #fff0b3
    set tkThemeColors(darkwarning)         #cfa000
}


# Set the theme
proc set_theme { themeName } {
    global tkThemeColors
    if { $themeName == "light" } {
        set_light_theme_colors
    } elseif { $themeName == "dark" } {
        set_dark_theme_colors
    } else {
        error "Unknown theme: $themeName"
    }

    # Set theme colors
    foreach { key value } [array get tkThemeColors] {
        if { [catch { tk_setPalette $key $value } errorMessage] } {
            # Handle cases where `tk_setPalette` does not support a specific key directly
            # For a more robust solution, map to ttk styles manually
        }
    }

    # Update global background color, which might not be covered by tk_setPalette for some widgets
    . configure -bg $tkThemeColors(bg)

    # Re-apply styles after theme color change
    ttk::style configure . -background $tkThemeColors(bg) -foreground $tkThemeColors(fg)

    # Frame
    ttk::style configure TFrame -background $tkThemeColors(bg)
    ttk::style configure TLF -background $tkThemeColors(bg) ;# LabelFrame
    ttk::style configure TPanedwindow -background $tkThemeColors(bg)
    ttk::style configure TNotebook -background $tkThemeColors(bg)
    ttk::style configure TNotebook.client -background $tkThemeColors(bg)

    # Label
    ttk::style configure TLabel -background $tkThemeColors(bg) -foreground $tkThemeColors(text)
    ttk::style configure TLabel -font "-apple-system 12"

    # Button
    ttk::style configure TButton \
        -background $tkThemeColors(lightfield) \
        -foreground $tkThemeColors(text) \
        -bordercolor $tkThemeColors(border) \
        -lightcolor $tkThemeColors(lightborder) \
        -darkcolor $tkThemeColors(darkborder) \
        -relief flat \
        -focuscolor $tkThemeColors(focus) \
        -focusthickness 1

    ttk::style map TButton \
        -background {
            active $tkThemeColors(active)
            pressed $tkThemeColors(secondary)
        } \
        -foreground {
            pressed $tkThemeColors(lightfg)
        }

    # Entry
    ttk::style configure TEntry \
        -fieldbackground $tkThemeColors(field) \
        -foreground $tkThemeColors(text) \
        -bordercolor $tkThemeColors(border) \
        -lightcolor $tkThemeColors(lightborder) \
        -darkcolor $tkThemeColors(darkborder) \
        -relief solid \
        -focusthickness 1 \
        -focuscolor $tkThemeColors(focus)

    ttk::style map TEntry \
        -fieldbackground {
            disabled $tkThemeColors(darkbg)
            readonly $tkThemeColors(darkbg)
        } \
        -foreground {
            disabled $tkThemeColors(disabled)
        }

    # Combobox (extends Entry)
    ttk::style configure TCombobox \
        -fieldbackground $tkThemeColors(field) \
        -foreground $tkThemeColors(text) \
        -selectbackground $tkThemeColors(selectbg) \
        -selectforeground $tkThemeColors(selectfg) \
        -bordercolor $tkThemeColors(border) \
        -lightcolor $tkThemeColors(lightborder) \
        -darkcolor $tkThemeColors(darkborder) \
        -relief solid \
        -focusthickness 1 \
        -focuscolor $tkThemeColors(focus)

    ttk::style map TCombobox \
        -fieldbackground {
            disabled $tkThemeColors(darkbg)
            readonly $tkThemeColors(darkbg)
        } \
        -foreground {
            disabled $tkThemeColors(disabled)
        } \
        -selectbackground {
            disabled $tkThemeColors(darkbg)
            readonly $tkThemeColors(darkbg)
        } \
        -selectforeground {
            disabled $tkThemeColors(disabled)
            readonly $tkThemeColors(disabled)
        }

    # Combobox Dropdown Button (arrow)
    ttk::style configure TCombobox.button \
        -background $tkThemeColors(field) \
        -bordercolor $tkThemeColors(border) \
        -lightcolor $tkThemeColors(lightborder) \
        -darkcolor $tkThemeColors(darkborder) \
        -relief flat

    ttk::style map TCombobox.button \
        -background {
            active $tkThemeColors(active)
            pressed $tkThemeColors(secondary)
        }

    # Checkbutton and Radiobutton
    ttk::style configure TCheckbutton \
        -background $tkThemeColors(bg) \
        -foreground $tkThemeColors(text) \
        -focuscolor $tkThemeColors(focus)
    ttk::style map TCheckbutton \
        -background {
            active $tkThemeColors(active)
        } \
        -foreground {
            disabled $tkThemeColors(disabled)
        }

    ttk::style configure TRadiobutton \
        -background $tkThemeColors(bg) \
        -foreground $tkThemeColors(text) \
        -focuscolor $tkThemeColors(focus)
    ttk::style map TRadiobutton \
        -background {
            active $tkThemeColors(active)
        } \
        -foreground {
            disabled $tkThemeColors(disabled)
        }

    # Notebook (Tabs)
    ttk::style configure TNotebook.Tab \
        -background $tkThemeColors(tertiary) \
        -foreground $tkThemeColors(text) \
        -padding {10 5 10 5} \
        -relief flat \
        -bordercolor $tkThemeColors(darktertiary)

    ttk::style map TNotebook.Tab \
        -background {
            selected $tkThemeColors(bg)
            active $tkThemeColors(active)
        } \
        -foreground {
            disabled $tkThemeColors(disabled)
        } \
        -expand {
            selected {0 0 0 0}
            !selected {0 0 0 0}
        }

    ttk::style configure TNotebook \
        -background $tkThemeColors(bg) \
        -bordercolor $tkThemeColors(darktertiary) \
        -tabposition wn

    # Scrollbar
    ttk::style configure TScrollbar \
        -background $tkThemeColors(lightbg) \
        -troughcolor $tkThemeColors(lightbg) \
        -bordercolor $tkThemeColors(border) \
        -relief flat \
        -arrowcolor $tkThemeColors(accent)

    ttk::style map TScrollbar \
        -background {
            active $tkThemeColors(active)
        } \
        -troughcolor {
            active $tkThemeColors(active)
        } \
        -arrowcolor {
            active $tkThemeColors(primary)
        }

    # Scale
    ttk::style configure TScale \
        -background $tkThemeColors(bg) \
        -foreground $tkThemeColors(text) \
        -troughcolor $tkThemeColors(lightfield) \
        -slidercolor $tkThemeColors(primary) \
        -bordercolor $tkThemeColors(border)

    ttk::style map TScale \
        -background {
            active $tkThemeColors(active)
        } \
        -slidercolor {
            active $tkThemeColors(secondary)
        }

    # Progressbar
    ttk::style configure TProgressbar \
        -background $tkThemeColors(primary) \
        -troughcolor $tkThemeColors(lightfield) \
        -bordercolor $tkThemeColors(border) \
        -relief flat

    # Separator
    ttk::style configure TSeparator \
        -background $tkThemeColors(border)

    # Treeview
    ttk::style configure Treeview \
        -background $tkThemeColors(bg) \
        -foreground $tkThemeColors(text) \
        -fieldbackground $tkThemeColors(field) \
        -bordercolor $tkThemeColors(border) \
        -lightcolor $tkThemeColors(lightborder) \
        -darkcolor $tkThemeColors(darkborder) \
        -relief flat \
        -rowheight 22

    ttk::style map Treeview \
        -background {
            selected $tkThemeColors(selectbg)
            active $tkThemeColors(active)
        } \
        -foreground {
            selected $tkThemeColors(selectfg)
            disabled $tkThemeColors(disabled)
        } \
        -font "-apple-system 12" ;# Ensures consistent font with labels

    ttk::style configure Treeview.Heading \
        -background $tkThemeColors(tertiary) \
        -foreground $tkThemeColors(text) \
        -relief raised \
        -bordercolor $tkThemeColors(darktertiary) \
        -font "-apple-system 12 bold"

    ttk::style map Treeview.Heading \
        -background {
            active $tkThemeColors(lighttertiary)
        }

    # LabelFrame text color
    ttk::style configure TLF -foreground $tkThemeColors(text)

    # ScrolledText (Tkinter's Text widget directly) - needs manual config
    # Tkinter widgets don't directly use ttk styles.
    # Text widget defaults to black on white. Will set foreground/background manually in Python code.
    # root.configure(background=tkThemeColors("bg"))


    # Special ttk styling for Treeview tags (e.g., for restricted volumes)
    # This requires defining the tag, then mapping its colors
    # The actual application code in tk_app.py needs to apply the tag:
    # self.volume_list_tree.insert(..., tags=('restricted_volume_tag',))
    ttk::treeview::tag configure .restricted_volume_tag \
        -foreground $tkThemeColors(error) \
        -background $tkThemeColors(lighterror)

    # Ensure focus color is applied to treeview items on selection
    ttk::treeview::map . \
        -focusbackground $tkThemeColors(selectbg) \
        -focusforeground $tkThemeColors(selectfg)

}