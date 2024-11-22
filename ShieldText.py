import wx
import wx.stc as stc
import sys
import os
import webbrowser
import wx.adv
import re  # Importing the re module for regular expressions
from pathlib import Path
import time
import wx.html

from cryptography.fernet import Fernet
import base64
import hashlib

class TextPrintout(wx.Printout):
    def __init__(self, text):
        super(TextPrintout, self).__init__()
        self.text = text
        self.lines_per_page = 0
        self.total_pages = 1
        self.line_height = 0
        self.page_width = 0
        self.wrapped_lines = []

    def OnPreparePrinting(self):
        # Prepare for printing by calculating pages and wrapping text
        dc = self.GetDC()
        font = wx.Font(96, wx.FONTFAMILY_TELETYPE, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL)
        dc.SetFont(font)
        _, self.line_height = dc.GetTextExtent("A")
        self.page_width, page_height = dc.GetSize()
        page_height -= 100  # Deducting for top and bottom margin

        # Wrap lines to fit page width
        self.wrap_text(dc)

        # Calculate lines per page and total number of pages
        self.lines_per_page = page_height // self.line_height
        self.total_pages = max(1, (len(self.wrapped_lines) + self.lines_per_page - 1) // self.lines_per_page)

    def wrap_text(self, dc):
        """Word-wraps the text to fit within page width while preserving blank lines."""
        self.wrapped_lines.clear()
#         margin = 750  # Adjusted left margin
#         max_width = self.page_width - margin
        margin = 750  # Increased left margin
        max_width = self.page_width + margin
        for line in self.text.splitlines():
            if not line.strip():  # Preserve blank lines
                self.wrapped_lines.append("")  # Append an empty line directly
                continue

            current_line = ""
            for word in line.split():
                test_line = f"{current_line} {word}".strip()
                text_width, _ = dc.GetTextExtent(test_line)
                if text_width <= max_width:
                    current_line = test_line
                else:
                    self.wrapped_lines.append(current_line)
                    current_line = word
            if current_line:
                self.wrapped_lines.append(current_line)


    def OnPrintPage(self, page):
        if page > self.total_pages:
            return False

        dc = self.GetDC()
        dc.Clear()
        font = wx.Font(78, wx.FONTFAMILY_TELETYPE, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL)
        dc.SetFont(font)

        # Set initial y-position with margin
        x, y = 200, 10  # Increased x for larger left margin
        start_line = (page - 1) * self.lines_per_page
        end_line = start_line + self.lines_per_page

        for line in self.wrapped_lines[start_line:end_line]:
            # If the line is empty, explicitly draw a blank line
            if line.strip() == "":
                y += self.line_height
            else:
                dc.DrawText(line, x, y)
                y += self.line_height

        return True


    def HasPage(self, page):
        return page <= self.total_pages

    def GetPageInfo(self):
        return (1, self.total_pages, 1, self.total_pages)

def resource_path(relative_path):
#     """ Get absolute path to resource, works for dev and PyInstaller """
    base_path = getattr(sys, '_MEIPASS', os.path.abspath("."))
    return os.path.join(base_path, relative_path)


# HELP_URL = "https://x.com/MrRCDavis"  # Updated Help URL

UNTITLED = "Untitled"

class ShieldText(wx.Frame):
    def __init__(self, *args, path=None, **kwargs):
        super(ShieldText, self).__init__(*args, **kwargs, size=(700, 500))
        # Initialize with optional file path
        self.path = Path(path) if path else None
        # Initialize GUI elements
        self.textcontrol = stc.StyledTextCtrl(self)
        self.textcontrol.SetWrapMode(stc.STC_WRAP_WORD)
        self.statusbar = self.CreateStatusBar(
            6, wx.STB_SIZEGRIP | wx.RAISED_BORDER | wx.STB_ELLIPSIZE_END
        )
        self.statusbar.SetStatusWidths([240, 55, 90, 100, 125, 90])         
        version = "v. 1.1.0 (2024)"
        self.statusbar.SetStatusText("ShieldText", 0)
        self.statusbar.SetStatusText(version, 5)
        # File path and encryption key
        self.path = None
        self.is_modified = False  # Track if the document has been modified
        self.textcontrol.SetUndoCollection(True)  # Enable undo/redo
        self.textcontrol.BeginUndoAction()  # Begin the first undo group
        # Setup menu and toolbar
        self.create_menu()
        self.create_toolbar()

        # Frame settings
        self.SetSize((600, 400))
#         
        self.update_title()

        # Bind the close event to handle unsaved changes
        self.Bind(wx.EVT_CLOSE, self.on_close)
        self.always_on_top_state = False  # Initialize the attribute here
        self.find_data = wx.FindReplaceData()
        
        self.textcontrol.SetWrapMode(1)

        # creating line number
        self.textcontrol.SetMarginType(1, stc.STC_MARGIN_NUMBER)

        # set margin 10 pixels between line number and text
#         self.textcontrol.SetMargins(10, 0)
        self.show_hide_linenumber(self)

        # set margin width
        self.leftMarginWidth = 50        
        self.encryption_key = None  # Initialize encryption_key to avoid AttributeError

        # Set the application icon
        icon_path = resource_path("images/titlebar.ico")
        icon = wx.Icon(icon_path, wx.BITMAP_TYPE_ICO)
        self.SetIcon(icon)
        self.set_word_count(self)
        self.textcontrol.Bind(stc.EVT_STC_MODIFIED, self.set_word_count)
        
        self.textcontrol.Bind(stc.EVT_STC_MODIFIED, self.OnTextChanged)
        # Check if a file path was provided
        file_path = sys.argv[1] if len(sys.argv) > 1 else None
        if file_path:
            self.OnDoubleClick(file_path)
            
            
        # Set a default font size
        self.textcontrol.StyleSetFont(stc.STC_STYLE_DEFAULT, wx.Font(18, wx.FONTFAMILY_MODERN,
                                                                     wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL, False, "Times New Roman"))

 
    def create_menu(self):
        menubar = wx.MenuBar()

        file_menu = wx.Menu()
        # NEW
        new_item = wx.MenuItem(file_menu, wx.ID_NEW, "&New\tCtrl+N", "Creates a new document")
        img = wx.Image(resource_path("images/tnew.png"), wx.BITMAP_TYPE_ANY)
        file_menu.Append(new_item)
        new_item.SetBitmap(wx.Bitmap(img))
        
        # Open
        open_item = wx.MenuItem(file_menu, wx.ID_OPEN, "&Open\tCtrl+O", "Creates a new document")
        img = wx.Image(resource_path("images/topen.png"), wx.BITMAP_TYPE_ANY)
        file_menu.Append(open_item)
        open_item.SetBitmap(wx.Bitmap(img))        
        
        
        # Save
        save_item = wx.MenuItem(file_menu, wx.ID_SAVE, "&Save File Encrypted/Plain Text\tCtrl+S", "Saves a document")
        img = wx.Image(resource_path("images/tsave.png"), wx.BITMAP_TYPE_ANY)
        file_menu.Append(save_item)
        save_item.SetBitmap(wx.Bitmap(img))        
        
        
        
#         save_as_item = file_menu.Append(wx.ID_SAVEAS, 'Save File &As Encrypted/Plain Text\tCtrl+Shift+S')
        
        
        # Save as
        save_as_item = wx.MenuItem(file_menu, wx.ID_SAVEAS, "Save File &As Encrypted/Plain Text\tCtrl+Shift+S", "Saves the active document with a new name")
        img = wx.Image(resource_path("images/tsaveas.png"), wx.BITMAP_TYPE_ANY)
        file_menu.Append(save_as_item)
        save_as_item.SetBitmap(wx.Bitmap(img))        
        
        
        
        # Add options to save without encryption
#         save_plain_item = file_menu.Append(wx.ID_ANY, 'Save (No Encryption)')
#         save_as_plain_item = file_menu.Append(wx.ID_ANY, 'Save As (No Encryption)')
        # Print Preview
        self.menu_onpreview = wx.MenuItem(file_menu, wx.ID_PREVIEW, "Print Preview\tCtrl+Shift+1", "Print Preview")
        img = wx.Image(resource_path("images/printpreview.png"), wx.BITMAP_TYPE_ANY)
        self.menu_onpreview.SetBitmap(wx.Bitmap(img))
        file_menu.Append(self.menu_onpreview)

        # Print
        self.menu_onprint = wx.MenuItem(file_menu, wx.ID_PRINT, "Print\tCtrl+P", "Print Document")
        img = wx.Image(resource_path("images/print.png"), wx.BITMAP_TYPE_ANY)
        self.menu_onprint.SetBitmap(wx.Bitmap(img))
        file_menu.Append(self.menu_onprint)        
        file_menu.AppendSeparator()
        
        
        # EXIT
        exit_item = wx.MenuItem(file_menu, wx.ID_EXIT, "E&xit\tCtrl+Q", "Exit the Application")
        img = wx.Image(resource_path("images/texit.png"), wx.BITMAP_TYPE_ANY)
        exit_item.SetBitmap(wx.Bitmap(img))
        file_menu.Append(exit_item)        
        
        
        
        

        edit_menu = wx.Menu()
        # UNDO
        undo_item = wx.MenuItem(
            edit_menu, wx.ID_UNDO, "&Undo", "Undo change")
        img = wx.Image(resource_path("images/tundo.png"), wx.BITMAP_TYPE_ANY)
        undo_item.SetBitmap(wx.Bitmap(img))
        edit_menu.Append(undo_item)

        # REDO
        redo_item = wx.MenuItem(
            edit_menu, wx.ID_REDO, "&Redo", "Redo change")
        img = wx.Image(resource_path("images/tredo.png"), wx.BITMAP_TYPE_ANY)
        redo_item.SetBitmap(wx.Bitmap(img))
        edit_menu.Append(redo_item)

        # SELECT ALL
        select_all_item = wx.MenuItem(
            edit_menu, wx.ID_SELECTALL, "Select &All", "Select All")
        img = wx.Image(resource_path("images/tselectall.png"), wx.BITMAP_TYPE_ANY)
        select_all_item.SetBitmap(wx.Bitmap(img))
        edit_menu.Append(select_all_item)

        # COPY
        copy_item = wx.MenuItem(edit_menu, wx.ID_COPY, "&Copy", "Copy the selected text")
        img = wx.Image(resource_path("images/tcopy.png"), wx.BITMAP_TYPE_ANY)
        copy_item.SetBitmap(wx.Bitmap(img))
        edit_menu.Append(copy_item)

        # CUT
        cut_item = wx.MenuItem(edit_menu, wx.ID_CUT, "Cu&t", "Cut the selected text")
        img = wx.Image(resource_path("images/tcut.png"), wx.BITMAP_TYPE_ANY)
        cut_item.SetBitmap(wx.Bitmap(img))
        edit_menu.Append(cut_item)

        # PASTE
        paste_item = wx.MenuItem(edit_menu, wx.ID_PASTE, "&Paste", "Paste from the clipboard")
        img = wx.Image(resource_path("images/tpaste.png"), wx.BITMAP_TYPE_ANY)
        paste_item.SetBitmap(wx.Bitmap(img))
        edit_menu.Append(paste_item)
        
        
        # Change Password
        change_password_tool = wx.MenuItem(edit_menu, wx.ID_ANY, "Change Password", "Change Password Of The Encrypted File")
        img = wx.Image(resource_path("images/key.png"), wx.BITMAP_TYPE_ANY)
        change_password_tool.SetBitmap(wx.Bitmap(img))
        edit_menu.Append(change_password_tool)        
#         change_password_tool = edit_menu.Append(wx.ID_ANY, 'Change Password Of Encrypted File')
#         self.Bind(wx.EVT_MENU, self.on_change_password, self.change_password_tool)

        
        text_menu = wx.Menu()

        #        # uppercase
        self.menu_uppercase = wx.MenuItem(text_menu, wx.ID_ANY, "Uppercase", "Convert selected text to uppercase")
        img = wx.Image(resource_path("images/uppercase.png"), wx.BITMAP_TYPE_ANY)
        self.menu_uppercase.SetBitmap(wx.Bitmap(img))
        text_menu.Append(self.menu_uppercase)        
        
        #        # lowercase
        self.menu_lowercase = wx.MenuItem(text_menu, wx.ID_ANY, "Lowercase", "Convert selected text to lowercase")
        img = wx.Image(resource_path("images/lowercase.png"), wx.BITMAP_TYPE_ANY)
        self.menu_lowercase.SetBitmap(wx.Bitmap(img))
        text_menu.Append(self.menu_lowercase)        
        
        #        # Title case
        self.menu_titlecase = wx.MenuItem(text_menu, wx.ID_ANY, "Title Case", "Convert selected text to Title Case")
        img = wx.Image(resource_path("images/titlecase.png"), wx.BITMAP_TYPE_ANY)
        self.menu_titlecase.SetBitmap(wx.Bitmap(img))
        text_menu.Append(self.menu_titlecase)
        
                #        # Sentence Case
        self.menu_sentencecase = wx.MenuItem(text_menu, wx.ID_ANY, "Sentence Case", "Convert selected text to Sentence Case")
        img = wx.Image(resource_path("images/sentencecase.png"), wx.BITMAP_TYPE_ANY)
        self.menu_sentencecase.SetBitmap(wx.Bitmap(img))
        text_menu.Append(self.menu_sentencecase)
        
        
        #Invert Case
        self.invert_case_item = wx.MenuItem(text_menu, wx.ID_ANY, "Invert Case", "Invert selected text")
        img = wx.Image(resource_path("images/invertcase.png"), wx.BITMAP_TYPE_ANY)
        self.invert_case_item.SetBitmap(wx.Bitmap(img))
        text_menu.Append(self.invert_case_item)
        
        
        #        # Pascal Case
        self.pascal_case_item = wx.MenuItem(text_menu, wx.ID_ANY, "Pascal case", "Convert selected text to Pascal case")
        img = wx.Image(resource_path("images/pascalcase.png"), wx.BITMAP_TYPE_ANY)
        self.pascal_case_item.SetBitmap(wx.Bitmap(img))
        text_menu.Append(self.pascal_case_item)



        view_menu = wx.Menu()
        # Add "Always on Top" item with a checkable option
        self.always_on_top_item = view_menu.Append(wx.ID_ANY, 'Always on Top\tCtrl+T', 'Set the window to always be on top', kind=wx.ITEM_CHECK)

                # wordwrap Toggle
        self.wrapit = view_menu.Append(wx.ID_ANY, "Wrap text", "Wrap text", kind=wx.ITEM_CHECK)
        view_menu.Check(self.wrapit.GetId(), True)
        self.Bind(wx.EVT_MENU, self.wordwrap, self.wrapit)
        # Statusbar Show/Hide Toolbar Toggle
        self.shtl = view_menu.Append(wx.ID_ANY, "Show toolbar", "Show Toolbar", kind=wx.ITEM_CHECK)
        view_menu.Check(self.shtl.GetId(), True)
        self.Bind(wx.EVT_MENU, self.ToggleToolBar, self.shtl)
        # Statusbar Show/Hide Statusbar Toggle
        self.shst = view_menu.Append(wx.ID_ANY, "Show statusbar", "Show Statusbar", kind=wx.ITEM_CHECK)
        view_menu.Check(self.shst.GetId(), True)
        self.Bind(wx.EVT_MENU, self.ToggleStatusBar, self.shst)
 
#          Show/Hide Line Number
        self.linenumberi = view_menu.Append(wx.ID_ANY, "Show/Hide Line Number", "Show/Hide Line Number", wx.ITEM_CHECK)
        view_menu.Check(self.linenumberi.GetId(), False)



        search_menu = wx.Menu()
        # Find
        self.fbtn = wx.MenuItem(search_menu, wx.ID_FIND, "Find", "Find")
        img = wx.Image(resource_path("images/tfind.png"), wx.BITMAP_TYPE_ANY)
        self.fbtn.SetBitmap(wx.Bitmap(img))
        search_menu.Append(self.fbtn)
                
          # Replace
        self.frbtn = wx.MenuItem(search_menu, wx.ID_REPLACE, "Replace", "Replace")
        img = wx.Image(resource_path("images/tfindreplace.png"), wx.BITMAP_TYPE_ANY)
        self.frbtn.SetBitmap(wx.Bitmap(img))
        search_menu.Append(self.frbtn)
        
        search_menu.AppendSeparator()
        
                # search google
        self.google_item = wx.MenuItem(search_menu, wx.ID_ANY, "Search Selected Text With Google", "Search Selected Text With Google")
        img = wx.Image(resource_path("images/google.png"), wx.BITMAP_TYPE_ANY)
        self.google_item.SetBitmap(wx.Bitmap(img))
        search_menu.Append(self.google_item)
        
        
        
                # search bing
        self.bing_item = wx.MenuItem(search_menu, wx.ID_ANY, "Search Selected Text With Bing", "Search Selected Text With Bing")
        img = wx.Image(resource_path("images/bing.png"), wx.BITMAP_TYPE_ANY)
        self.bing_item.SetBitmap(wx.Bitmap(img))
        search_menu.Append(self.bing_item)

                # search duckduckgo
        self.duckduckgo_item = wx.MenuItem(search_menu, wx.ID_ANY, "Search Selected Text With Duckduckgo", "Search Selected Text With Duckduckgo")
        img = wx.Image(resource_path("images/duckduckgo.png"), wx.BITMAP_TYPE_ANY)
        self.duckduckgo_item.SetBitmap(wx.Bitmap(img))
        search_menu.Append(self.duckduckgo_item)
        
                        # search Wikipedia
        self.wikipedia_item = wx.MenuItem(search_menu, wx.ID_ANY, "Search Selected Text With Wikipedia", "Search Selected Text With Wikipedia")
        img = wx.Image(resource_path("images/wikipedia.png"), wx.BITMAP_TYPE_ANY)
        self.wikipedia_item.SetBitmap(wx.Bitmap(img))
        search_menu.Append(self.wikipedia_item)

                # search merriam webster
        self.merriam_webster_item = wx.MenuItem(search_menu, wx.ID_ANY, "Search Selected Text With Merriam Webster", "Search Selected Text With Merriam Webster")
        img = wx.Image(resource_path("images/merriamwebster.png"), wx.BITMAP_TYPE_ANY)
        self.merriam_webster_item.SetBitmap(wx.Bitmap(img))
        search_menu.Append(self.merriam_webster_item)
        
        insert_menu = wx.Menu()
        # Date Time
        self.menu_getdatetime = wx.MenuItem(insert_menu, wx.ID_ANY, "Date Time", "Date Time")
        img = wx.Image(resource_path("images/tdatetime.png"), wx.BITMAP_TYPE_ANY)
        self.menu_getdatetime.SetBitmap(wx.Bitmap(img))
        insert_menu.Append(self.menu_getdatetime)

        # Date
        self.menu_getdate = wx.MenuItem(insert_menu, wx.ID_ANY, "Date", "Date")
        img = wx.Image(resource_path("images/tdate.png"), wx.BITMAP_TYPE_ANY)
        self.menu_getdate.SetBitmap(wx.Bitmap(img))
        insert_menu.Append(self.menu_getdate)

        # Time
        self.menu_gettime = wx.MenuItem(insert_menu, wx.ID_ANY, "Time", "Time")
        img = wx.Image(resource_path("images/ttime.png"), wx.BITMAP_TYPE_ANY)
        self.menu_gettime.SetBitmap(wx.Bitmap(img))
        insert_menu.Append(self.menu_gettime)
        
       # enclose_menu_item
        img = wx.Image(resource_path("images/enclosed.png"), wx.BITMAP_TYPE_ANY).ConvertToBitmap()
        self.enclose_menu_item = wx.MenuItem(insert_menu, wx.ID_ANY, "Enclose Selected Text", "Enclose Selected Text")
        self.enclose_menu_item.SetBitmap(img)
        insert_menu.Append(self.enclose_menu_item)
        







        
        
        
        
        
        help_menu = wx.Menu()
        
        

        
        
#         help_item = help_menu.Append(wx.ID_ANY, "Help\tF1", "Show help information")
        
        self.help_item = wx.MenuItem(help_menu, wx.ID_ANY, "ShieldText Help", "ShieldText Help File",)
        img = wx.Image(resource_path("images/tquestion.png"), wx.BITMAP_TYPE_ANY)
        self.help_item.SetBitmap(wx.Bitmap(img))
        help_menu.Append(self.help_item)
        

        # ABOUT BOX
        self.menu_about = wx.MenuItem(help_menu, wx.ID_ABOUT, "&About", "About this software")
        img = wx.Image(resource_path("images/tabout.png"), wx.BITMAP_TYPE_ANY)
        self.menu_about.SetBitmap(wx.Bitmap(img))
        help_menu.Append(self.menu_about)
        
        
        
        
        # MY LINKS
        self.links_item = wx.MenuItem(help_menu, wx.ID_ANY, "Great Links", "Great Links: Friends Family and Some Great Resources.",)
        img = wx.Image(resource_path("images/links.png"), wx.BITMAP_TYPE_ANY)
        self.links_item.SetBitmap(wx.Bitmap(img))
        help_menu.Append(self.links_item)
        
        
#         # MY SITE
#         self.menu_mysite = wx.MenuItem(help_menu, wx.ID_HELP, "R.C.Davis on X", "R.C.Davis on X",)
#         img = wx.Image(resource_path("images/x.png"), wx.BITMAP_TYPE_ANY)
#         self.menu_mysite.SetBitmap(wx.Bitmap(img))
#         help_menu.Append(self.menu_mysite)
        
        
        
        
        
        settings_menu = wx.Menu()

        # Light theme menu item
        img = wx.Image(resource_path("images/lighttheme.png"), wx.BITMAP_TYPE_ANY).ConvertToBitmap()
        self.menu_onlightthemeitem = wx.MenuItem(settings_menu, wx.ID_ANY, "Light Theme", "Switch to light theme")
        self.menu_onlightthemeitem.SetBitmap(img)
        settings_menu.Append(self.menu_onlightthemeitem)

        # Dark theme menu item
        img = wx.Image(resource_path("images/darktheme.png"), wx.BITMAP_TYPE_ANY).ConvertToBitmap()
        self.menu_ondarkthemeitem = wx.MenuItem(settings_menu, wx.ID_ANY, "Dark Theme", "Switch to dark theme")
        self.menu_ondarkthemeitem.SetBitmap(img)
        settings_menu.Append(self.menu_ondarkthemeitem)


        menubar.Append(file_menu, '&File')
        menubar.Append(edit_menu, '&Edit')
        menubar.Append(text_menu, '&Text')
        
        menubar.Append(search_menu, "&Search")
        menubar.Append(insert_menu, '&Insert')
        
        menubar.Append(view_menu, '&View')

        menubar.Append(settings_menu, '&Settings')
        
        menubar.Append(help_menu, "&Help")

        self.SetMenuBar(menubar)

        self.Bind(wx.EVT_MENU, self.on_new, new_item)
        self.Bind(wx.EVT_MENU, self.on_open, open_item)
        self.Bind(wx.EVT_MENU, self.on_save, save_item)
        self.Bind(wx.EVT_MENU, self.on_save_as, save_as_item)
#         self.Bind(wx.EVT_MENU, self.on_save_plain, save_plain_item)
#         self.Bind(wx.EVT_MENU, self.on_save_as_plain, save_as_plain_item)
        self.Bind(wx.EVT_MENU, self.on_exit, exit_item)
        self.Bind(wx.EVT_MENU, self.on_copy, copy_item)
        self.Bind(wx.EVT_MENU, self.on_cut, cut_item)
        self.Bind(wx.EVT_MENU, self.on_paste, paste_item)
        self.Bind(wx.EVT_MENU, self.on_undo, undo_item)
        self.Bind(wx.EVT_MENU, self.on_redo, redo_item)
        self.Bind(wx.EVT_MENU, self.on_select_all, select_all_item)
        self.Bind(wx.EVT_MENU, self.OnAlwaysOnTop, self.always_on_top_item)
        self.Bind(wx.EVT_FIND, self.onsimplefind)
        self.Bind(wx.EVT_FIND_NEXT, self.onsimplefind)
        self.Bind(wx.EVT_FIND, self.on_find)
        self.Bind(wx.EVT_FIND_NEXT, self.on_find)
        self.Bind(wx.EVT_FIND_NEXT, self.on_find_next)
        self.Bind(wx.EVT_FIND_REPLACE, self.on_replace)
        self.Bind(wx.EVT_FIND_REPLACE_ALL, self.on_replace_all)
        self.Bind(wx.EVT_FIND_CLOSE, self.on_find_close)
        self.Bind(wx.EVT_MENU, self.onsimplefind, id=wx.ID_FIND)
        self.Bind(wx.EVT_MENU, self.search_selected_text_google, self.google_item)
        self.Bind(wx.EVT_MENU, self.search_selected_text_bing, self.bing_item)
        self.Bind(wx.EVT_MENU, self.search_selected_text_duckduckgo, self.duckduckgo_item)
        self.Bind(wx.EVT_MENU, self.search_selected_text_merriam_webster, self.merriam_webster_item)
        self.Bind(wx.EVT_MENU, self.search_selected_text_wikipedia, self.wikipedia_item)
        self.Bind(wx.EVT_MENU, self.on_find_replace, id=wx.ID_REPLACE)
#         self.Bind(wx.EVT_MENU, self.on_menu_help_mysite, self.menu_mysite)
        self.Bind(wx.EVT_MENU, self.on_menu_help_about, self.menu_about)
#         # Bind the light and dark theme menu items to their respective handlers
        self.Bind(wx.EVT_MENU, self.lighttheme, self.menu_onlightthemeitem)
        self.Bind(wx.EVT_MENU, self.darktheme, self.menu_ondarkthemeitem)
        self.Bind(wx.EVT_MENU, self.on_menu_uppercase, self.menu_uppercase)
        self.Bind(wx.EVT_MENU, self.on_menu_lowercase, self.menu_lowercase)
        self.Bind(wx.EVT_MENU, self.OnTitleCase, self.menu_titlecase)
        self.Bind(wx.EVT_MENU, self.on_convert_to_sentence_case, self.menu_sentencecase)
        self.Bind(wx.EVT_MENU, self.on_pascal_case, self.pascal_case_item)
        self.Bind(wx.EVT_MENU, self.invert_case, self.invert_case_item)
        self.Bind(wx.EVT_MENU, self.show_hide_linenumber, self.linenumberi)
        self.Bind(wx.EVT_MENU, self.getdatetime, self.menu_getdatetime)
        self.Bind(wx.EVT_MENU, self.getdate, self.menu_getdate)
        self.Bind(wx.EVT_MENU, self.gettime, self.menu_gettime)        
        self.Bind(wx.EVT_MENU, self.on_show_enclose_dialog, self.enclose_menu_item)
        self.Bind(wx.EVT_MENU, self.show_help, self.help_item)
        self.Bind(wx.EVT_MENU, self.OnLinks, self.links_item)
        self.Bind(wx.EVT_MENU, self.on_print, self.menu_onprint)
        self.Bind(wx.EVT_MENU, self.onpreview, self.menu_onpreview)
        self.Bind(wx.EVT_MENU, self.on_change_password, change_password_tool)
        self.textcontrol.Bind(wx.EVT_CHAR, self.on_char)
        
        
    def create_toolbar(self):
        self.toolbar = self.CreateToolBar()
        
        # Adding tools to the toolbar
        new_tool = self.toolbar.AddTool(wx.ID_NEW, 'New', wx.Bitmap(resource_path("images/tnew.png")), "Create a new file")
        open_tool = self.toolbar.AddTool(wx.ID_OPEN, 'Open', wx.Bitmap(resource_path("images/open.png")), "Open an existing file")
        save_tool = self.toolbar.AddTool(wx.ID_SAVE, 'Save', wx.Bitmap(resource_path("images/tsave.png")), "Save the current file")
        copy_tool = self.toolbar.AddTool(wx.ID_COPY, 'Copy', wx.Bitmap(resource_path("images/tcopy.png")), "Copy the selected content")
        cut_tool = self.toolbar.AddTool(wx.ID_CUT, 'Cut', wx.Bitmap(resource_path("images/tcut.png")), "Cut the selected content")
        paste_tool = self.toolbar.AddTool(wx.ID_PASTE, 'Paste', wx.Bitmap(resource_path("images/tpaste.png")), "Paste the copied content")
        undo_tool = self.toolbar.AddTool(wx.ID_UNDO, 'Undo', wx.Bitmap(resource_path("images/tundo.png")), "Undo the last action")
        redo_tool = self.toolbar.AddTool(wx.ID_REDO, 'Redo', wx.Bitmap(resource_path("images/tredo.png")), "Redo the last undone action")
        menu_Onzoomin = self.toolbar.AddTool(wx.ID_ZOOM_IN, "Zoom In", wx.Bitmap(resource_path("images/zoomin.png")), "Zoom in on the content")
        menu_Onzoomout = self.toolbar.AddTool(wx.ID_ZOOM_OUT, "Zoom Out", wx.Bitmap(resource_path("images/zoomout.png")), "Zoom out of the content")
        menu_Onresetzoom = self.toolbar.AddTool(wx.ID_ZOOM_100, "Reset Zoom", wx.Bitmap(resource_path("images/resetzoom.png")), "Reset zoom to default")
        menu_onprint = self.toolbar.AddTool(wx.ID_PRINT, "Print", wx.Bitmap(resource_path("images/print.png")), "Print the documentt")
        
#         self.toolbar.AddTool(wx.ID_PRINT, "Help", wx.Bitmap("tprint.png"), "Print the document")
#         self.toolbar.AddTool(wx.ID_PRINT, "Help", wx.Bitmap("tprint.png"), "Print the document")
        
        find_tool = self.toolbar.AddTool(wx.ID_FIND, "Find", wx.Bitmap(resource_path("images/tfind.png")), "Find text in the document")
        replace_tool = self.toolbar.AddTool(wx.ID_REPLACE, "Replace", wx.Bitmap(resource_path("images/tfindreplace.png")), "Replace text in the document")
        
        # Custom tool for changing the password
        change_password_tool = self.toolbar.AddTool(wx.ID_ANY, "Change Password", wx.Bitmap(resource_path("images/key.png")), "Change Password in the document")
        
        exit_tool = self.toolbar.AddTool(wx.ID_EXIT, 'Exit', wx.Bitmap(resource_path("images/texit.png")), "Exit the application")  # Added Exit Tool
        
        # Adding tooltips
        self.toolbar.SetToolShortHelp(new_tool.GetId(), 'Create a new file')
        self.toolbar.SetToolShortHelp(open_tool.GetId(), 'Open an existing file')
        self.toolbar.SetToolShortHelp(save_tool.GetId(), 'Save the current file')
        self.toolbar.SetToolShortHelp(copy_tool.GetId(), 'Copy selected text')
        self.toolbar.SetToolShortHelp(cut_tool.GetId(), 'Cut selected text')
        self.toolbar.SetToolShortHelp(paste_tool.GetId(), 'Paste text from clipboard')
        self.toolbar.SetToolShortHelp(undo_tool.GetId(), 'Undo the last action')
        self.toolbar.SetToolShortHelp(redo_tool.GetId(), 'Redo the last undone action')
        self.toolbar.SetToolShortHelp(find_tool.GetId(), 'Find text in the document')
        self.toolbar.SetToolShortHelp(replace_tool.GetId(), 'Replace text in the document')
        self.toolbar.SetToolShortHelp(change_password_tool.GetId(), 'Change password of the encrypted file')
        self.toolbar.SetToolShortHelp(exit_tool.GetId(), 'Exit the application')
        
        # Realize the toolbar
        self.toolbar.Realize()

        # Binding tools to respective methods
        self.Bind(wx.EVT_TOOL, self.on_new, new_tool)
        self.Bind(wx.EVT_TOOL, self.on_open, open_tool)
        self.Bind(wx.EVT_TOOL, self.on_save, save_tool)
        self.Bind(wx.EVT_TOOL, self.on_copy, copy_tool)
        self.Bind(wx.EVT_TOOL, self.on_cut, cut_tool)
        self.Bind(wx.EVT_TOOL, self.on_paste, paste_tool)
        self.Bind(wx.EVT_TOOL, self.on_undo, undo_tool)
        self.Bind(wx.EVT_TOOL, self.on_redo, redo_tool)
        self.Bind(wx.EVT_UPDATE_UI, self.on_menu_undo_update, undo_tool)
        self.Bind(wx.EVT_UPDATE_UI, self.on_menu_redo_update, redo_tool)
      
        
        
        
        self.Bind(wx.EVT_TOOL, self.on_exit, exit_tool)  # Bind Exit Tool
        
        # Bind custom "Change Password" tool
        self.Bind(wx.EVT_TOOL, self.on_change_password, change_password_tool)
        self.Bind(wx.EVT_TOOL, self.zoomin, menu_Onzoomin)
        self.Bind(wx.EVT_TOOL, self.zoomout, menu_Onzoomout)
        self.Bind(wx.EVT_TOOL, self.resetzoom, menu_Onresetzoom)

        # Bind text change event to track modifications
        self.textcontrol.Bind(stc.EVT_STC_CHANGE, self.on_text_change)

    def on_text_change(self, event):
        """Track changes in the text control."""
        self.is_modified = True
        event.Skip()  # Allow the event to propagate
        
        
        
        
        
        
        

    def on_new(self, event):
        """Create a new file by clearing the editor and resetting the file path."""
        if self.is_modified and not self.save_if_modified():
            return
        
        # Clear the editor and reset file path
        self.textcontrol.ClearAll()
        self.textcontrol.EmptyUndoBuffer()  # Clear undo history
        self.path = None
        self.is_modified = False
        self.SetStatusText("New file created")
        self.update_title()

    def on_open(self, event):
        """Open an encrypted file, prompt for a key if .rde, and decrypt the content."""
        if self.is_modified and not self.save_if_modified():
            return

        with wx.FileDialog(self, "Open Encrypted or Plain Text File", 
                           wildcard="Encrypted files (*.rde)|*.rde|Plain Text files (*.txt)|*.txt",
                           style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST) as file_dialog:
            if file_dialog.ShowModal() == wx.ID_CANCEL:
                return  # User canceled

            self.path = file_dialog.GetPath()
            self.encryption_key = None  # Reset key to re-prompt

            if self.path.lower().endswith('.rde'):
                # Prompt for the correct encryption key immediately
                while True:
                    dialog = PasswordDialog(self, "Decryption Key")
                    if dialog.ShowModal() == wx.ID_OK:
                        self.encryption_key = dialog.get_password()
                        dialog.Destroy()
                    else:
                        dialog.Destroy()
                        return  # User canceled the key entry

                    try:
                        # Open and attempt to decrypt the .rde file
                        with open(self.path, 'rb') as file:
                            encrypted_data = file.read()
                            decrypted_data = self.decrypt_data(encrypted_data, self.encryption_key)
                            self.textcontrol.SetText(decrypted_data.decode('utf-8'))
                        break  # Break the loop if decryption is successful
                    except Exception:
                        # If decryption fails, show an error dialog with Retry and Cancel options
                        error_dialog = wx.MessageDialog(
                            self, 
                            "Incorrect password. Would you like to try again?", 
                            "Decryption Failed", 
                            wx.OK | wx.CANCEL | wx.ICON_ERROR
                        )
                        result = error_dialog.ShowModal()
                        error_dialog.Destroy()
                        
                        if result != wx.ID_OK:
                            # If user chooses Cancel, exit the function
                            return
            elif self.path.lower().endswith('.txt'):
                # If it's a .txt file, open normally without decryption
                try:
                    with open(self.path, 'r', encoding='utf-8') as file:
                        plain_text_data = file.read()
                        self.textcontrol.SetText(plain_text_data)
                except Exception as e:
                    wx.LogError(f"Failed to open file: {e}")
                    return

            # Clear undo history and reset modified flag
            self.textcontrol.EmptyUndoBuffer()  # Clear undo history after loading new file
            self.is_modified = False
            self.textcontrol.SetSavePoint()  # Reset the save point
            self.update_title()
#             self.SetStatusText(f"Opened file: {self.path}")




    def on_save(self, event=None):
        """Save the text content, with encryption for non-txt files."""
        if not self.path:
            self.on_save_as(event)
            return

        if self.path.lower().endswith('.txt'):
            # Save without encryption for .txt files
            self.on_save_plain(event)
        else:
            # Use existing encryption key or prompt if not set
            if not self.encryption_key:
                dialog = PasswordDialog(self, "Enter Encryption Key")
                if dialog.ShowModal() == wx.ID_OK:
                    self.encryption_key = dialog.get_password()
                    dialog.Destroy()

                    if not self.encryption_key.strip():
                        wx.MessageBox("Password cannot be blank.", "Error", wx.OK | wx.ICON_ERROR)
                        return  # Do not proceed with saving
                else:
                    dialog.Destroy()
                    return  # User canceled the key entry

            try:
                text_data = self.textcontrol.GetText().encode('utf-8')
                encrypted_data = self.encrypt_data(text_data, self.encryption_key)

                with open(self.path, 'wb') as file:
                    file.write(encrypted_data)
                self.is_modified = False
                self.SetStatusText("File saved successfully!")
                self.update_title()

            except Exception as e:
                wx.LogError(f"Failed to save file: {e}")


    def on_save_as(self, event=None):
        """Prompt user for file path and save, with encryption for non-txt files."""
        with wx.FileDialog(self, "Save File As",
                           wildcard="Encrypted files (*.rde)|*.rde|Plain Text files (*.txt)|*.txt",
                           style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT) as file_dialog:

            if file_dialog.ShowModal() == wx.ID_CANCEL:
                return  # User canceled

            new_path = file_dialog.GetPath()

            # Prompt if file exists
            if os.path.exists(new_path):
                overwrite = wx.MessageBox(
                    "The file already exists. Do you want to overwrite it?",
                    "Confirm Overwrite",
                    wx.YES_NO | wx.ICON_WARNING
                )
                if overwrite != wx.YES:
                    return  # User chose not to overwrite

            self.path = new_path

            if self.path.lower().endswith('.txt'):
                self.on_save_plain(event)  # Save without encryption
            else:
                # Prompt the user for an encryption password using PasswordDialog
                dialog = PasswordDialog(self, "Enter Encryption Key")
                if dialog.ShowModal() == wx.ID_OK:
                    self.encryption_key = dialog.get_password()
                    dialog.Destroy()

                    if not self.encryption_key.strip():
                        wx.MessageBox("Password cannot be blank.", "Error", wx.OK | wx.ICON_ERROR)
                        return  # Do not proceed with saving

                    self.on_save(event)  # Save with encryption
                else:
                    dialog.Destroy()
                    wx.MessageBox("Save operation canceled", "Info", wx.OK | wx.ICON_INFORMATION)





    def on_save_plain(self, event=None):
        """Save the text content without encryption for .txt files only."""
        if self.path and not self.path.endswith('.txt'):
            wx.MessageBox("Only .txt files can be saved without encryption.", "Error", wx.OK | wx.ICON_ERROR)
            return

        if not self.path:
            self.on_save_as_plain(event)
            return

        try:
            text_data = self.textcontrol.GetText()
            with open(self.path, 'w', encoding='utf-8') as file:
                file.write(text_data)
            self.is_modified = False
            self.SetStatusText("File saved successfully without encryption!")
            self.update_title()

        except Exception as e:
            wx.LogError(f"Failed to save file: {e}")

    def on_save_as_plain(self, event=None):
        """Save the text content to a new .txt file without encryption."""
        with wx.FileDialog(self, "Save File As (No Encryption)", wildcard="*.txt",
                           style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT) as file_dialog:
            if file_dialog.ShowModal() == wx.ID_CANCEL:
                return  # User canceled

            self.path = file_dialog.GetPath()
            
            # Ensure the user selected a .txt file
            if not self.path.endswith('.txt'):
                wx.MessageBox("Only .txt files can be saved without encryption.", "Error", wx.OK | wx.ICON_ERROR)
                return

            # Proceed with saving as plain text
            self.on_save_plain(event)


    def on_change_password(self, event):
        """Change the encryption password of the currently opened encrypted file."""
        if not self.path or not self.path.endswith('.rde'):
            wx.MessageBox("No encrypted file is currently open.", "Error", wx.OK | wx.ICON_ERROR)
            return

        # Prompt for the new encryption key using PasswordDialog
        dialog = PasswordDialog(self, "Change Password")
        if dialog.ShowModal() == wx.ID_OK:
            new_key = dialog.get_password()
            dialog.Destroy()

            # Validate the new password
            if not new_key:  # Check if the password is empty
                wx.MessageBox("Password cannot be blank.", "Error", wx.OK | wx.ICON_ERROR)
                return
        else:
            dialog.Destroy()
            return  # User canceled the password change

        # Encrypt the current content with the new key and save
        try:
            text_data = self.textcontrol.GetText().encode('utf-8')
            encrypted_data = self.encrypt_data(text_data, new_key)

            with open(self.path, 'wb') as file:
                file.write(encrypted_data)
            
            # Update the encryption key and reset the modified flag
            self.encryption_key = new_key
            self.is_modified = False
            self.SetStatusText("Password changed and file re-encrypted successfully!")
        except Exception as e:
            wx.LogError(f"Failed to change password: {e}")



    def generate_key(self, password):
        """Generate a 32-byte Fernet key based on a password."""
        return base64.urlsafe_b64encode(hashlib.sha256(password.encode('utf-8')).digest()[:32])

    def encrypt_data(self, data, password):
        """Encrypt data with the given password."""
        key = self.generate_key(password)
        fernet = Fernet(key)
        return fernet.encrypt(data)

    def decrypt_data(self, data, password):
        """Decrypt data with the given password."""
        key = self.generate_key(password)
        fernet = Fernet(key)
        return fernet.decrypt(data)

    def save_changes_msg_dialog(self):
        path = self.path or UNTITLED
        dialog = wx.MessageDialog(
            self,
            f"Do you want to save changes to {path}?",
            "Unsaved Changes",
            wx.YES_NO | wx.CANCEL
        )
        dialog.SetYesNoLabels("Save", "Don't Save")
        return dialog.ShowModal()    

    def save_if_modified(self):
        """Prompt to save changes if there are unsaved modifications."""
        if self.is_modified:
            dialog = self.save_changes_msg_dialog()
            if dialog == wx.ID_CANCEL:
                return False
            elif dialog == wx.ID_YES:
                self.on_save()
                return not self.is_modified
        return True
##################################################################################################################################

    def OnDoubleClick(self, file_path):
        """Handle double-click event to open files based on their extension."""
        self.path = file_path
        self.encryption_key = None  # Reset key to re-prompt for encryption

        # Normalize extension to lowercase for case-insensitive comparison
        file_extension = self.path.split('.')[-1].lower()

        if file_extension == 'rde':
            # Prompt for the correct encryption key immediately
            while True:
                with PasswordDialog(self, "Decryption Key") as dialog:
                    if dialog.ShowModal() == wx.ID_OK:
                        self.encryption_key = dialog.get_password()
                    else:
                        return  # User canceled the key entry

                try:
                    # Open and attempt to decrypt the .rde file
                    with open(self.path, 'rb') as file:
                        encrypted_data = file.read()
                        decrypted_data = self.decrypt_data(encrypted_data, self.encryption_key)
                        self.textcontrol.SetText(decrypted_data.decode('utf-8'))
                    break  # Exit loop if decryption is successful
                except Exception:
                    # If decryption fails, show an error dialog with Retry and Cancel options
                    error_dialog = wx.MessageDialog(
                        self, 
                        "Incorrect password. Would you like to try again?", 
                        "Decryption Failed", 
                        wx.OK | wx.CANCEL | wx.ICON_ERROR
                    )
                    result = error_dialog.ShowModal()
                    error_dialog.Destroy()

                    if result != wx.ID_OK:
                        return  # User canceled retry

        elif file_extension == 'txt':
            # Open plain text file directly
            try:
                with open(self.path, 'r', encoding='utf-8') as file:
                    plain_text_data = file.read()
                    self.textcontrol.SetText(plain_text_data)
            except Exception as e:
                wx.LogError(f"Failed to open file: {e}")
                return
        else:
            wx.MessageBox("Unsupported file type.", "Error", wx.OK | wx.ICON_ERROR)
            return

        # Clear undo history and reset modified flag
        self.textcontrol.EmptyUndoBuffer()  # Clear undo history after loading new file
        self.is_modified = False
        self.textcontrol.SetSavePoint()  # Reset the save point
#         self.SetStatusText(f"Opened file: {self.path}")
        self.update_title()



#################################################################################################################################


    def on_exit(self, event):
        """Close the application by triggering the close event."""
        self.Close()  # This will trigger on_close and handle unsaved changes

    def on_copy(self, event):
        """Copy selected text to clipboard."""
        self.textcontrol.Copy()

    def on_cut(self, event):
        """Cut selected text to clipboard."""
        self.textcontrol.Cut()

    def on_paste(self, event):
        """Paste text from clipboard."""
        self.textcontrol.Paste()
        
        
    def on_char(self, event):
        char = chr(event.GetUnicodeKey())
        if char.isspace() or char in {".", ",", "!", "?", "\n"}:
            # End the current undo group after a word or punctuation
            self.textcontrol.EndUndoAction()
            self.textcontrol.BeginUndoAction()  # Start a new group
        event.Skip()  # Allow default handling
        
        

    def on_undo(self, event):
        """Undo the last action."""
        self.textcontrol.Undo()
        
    def on_menu_undo_update(self, event):
        event.Enable(self.textcontrol.CanUndo())
        
    def on_redo(self, event):
        """Redo the last undone action."""
        self.textcontrol.Redo()
        
    def on_menu_redo_update(self, event):
        event.Enable(self.textcontrol.CanRedo())        
        
        
        
        

    def on_select_all(self, event):
        """Select all text in the editor."""
        self.textcontrol.SelectAll()
        
        
    def zoomin(self, event):
        self.textcontrol.ZoomIn()

    def zoomout(self, event):
        self.textcontrol.ZoomOut()
        
    def resetzoom(self, event):
        """Reset the zoom level to the default (0)."""
        self.textcontrol.SetZoom(0)        
        
    def on_find_close(self, event):
        event.GetDialog().Destroy()
        
        
    def on_pascal_case(self, event):
            text = ''.join(word.capitalize() for word in self.textcontrol.GetSelectedText().split())
            self.textcontrol.ReplaceSelection(text)
    def on_menu_uppercase(self, event):
        self.textcontrol.UpperCase()

    def on_menu_lowercase(self, event):
        self.textcontrol.LowerCase()

    def OnTitleCase(self, event):
        text = self.textcontrol.GetSelectedText()
        if text:
            title_cased = text.title()
            self.textcontrol.ReplaceSelection(title_cased)

    def on_convert_to_sentence_case(self, event):
        start, end = self.textcontrol.GetSelection()
        selected_text = self.textcontrol.GetTextRange(start, end)
        if selected_text:
            try:
                sentences = re.split(r'(?<=[.!?]) +', selected_text)
                sentence_case_text = ' '.join(sentence.capitalize() for sentence in sentences)
                self.textcontrol.ReplaceSelection(sentence_case_text)
            except Exception as e:
                wx.MessageBox(f"An error occurred: {str(e)}", "Error", wx.OK | wx.ICON_ERROR)            
            
    def invert_case(self, event):
        # Get the selection start and end positions
        start, end = self.textcontrol.GetSelection()
        
        # If there's no selection, do nothing
        if start == end:
            return

        # Get the selected text
        selected_text = self.textcontrol.GetTextRange(start, end)
        
        # Invert the case of each character in the selected text
        inverted_text = ''.join(char.lower() if char.isupper() else char.upper() for char in selected_text)
        
        # Replace the selected text with the inverted text
        self.textcontrol.Replace(start, end, inverted_text)        
        
        
        
    def search_selected_text_google(self, event):
        self.search_selected_text("https://www.google.com/search?q=")

    def search_selected_text_bing(self, event):
        self.search_selected_text("https://www.bing.com/search?q=")

    def search_selected_text_duckduckgo(self, event):
        self.search_selected_text("https://duckduckgo.com/?q=")

    def search_selected_text_merriam_webster(self, event):
        self.search_selected_text("https://www.merriam-webster.com/dictionary/")
        
    def search_selected_text_wikipedia(self, event):
        self.search_selected_text("https://en.wikipedia.org/wiki/")
        
    def search_selected_text(self, search_engine):
        selected_text = self.textcontrol.GetSelectedText()
        if selected_text:
            webbrowser.open(search_engine + selected_text)
        else:
            wx.MessageBox("No text selected!", "Error", wx.OK | wx.ICON_ERROR)        
        
#     def update_title(self):
#         """
#         Updates the title bar of the application to show the application name
#         and current status.
#         """
#         current_year = time.strftime("%Y")
#         # Determine file name: default to "UNTITLED" if no path is set
#         if self.path:
#             name = self.path.name if hasattr(self.path, 'name') else self.path
#         else:
#             name = "UNTITLED"
#         
#         # Add modified indicator if the file has unsaved changes
#         modified_flag = " *" if getattr(self, 'is_modified', False) else ""
# 
#         # Set the window's title
#         self.SetTitle(f"{name}{modified_flag} - ShieldText ({current_year})")


    def update_title(self):
        current_year = time.strftime("%Y")
        modified_flag = " *" if getattr(self, 'is_modified', False) else ""

        if self.path:
            # Extract just the filename
            
            name = os.path.basename(self.path)
#             self.SetTitle(name)  # Update the title bar
            self.SetStatusText(f"Editing: {name}")  # Optional status bar update
            self.SetTitle(f"{name}{modified_flag} - ShieldText ({current_year})")

        else:
            name = "UNTITLED"            
#             self.SetTitle(name)  # Update the title bar
            self.SetStatusText(f"Editing: {name}")  # Optional status bar update        
            self.SetTitle(f"{name}{modified_flag} - ShieldText ({current_year})")





    
    
    
    
    
    
    

    def on_close(self, event):
        """Handle the window close event, prompting to save if modified."""
        if self.is_modified and not self.save_if_modified():
            event.Veto()  # Prevent closing if the user cancels
        else:
            self.Destroy()  # Proceed to close
            
    def OnAlwaysOnTop(self, event):
        """Toggle the 'always on top' state."""
        self.always_on_top_state = not self.always_on_top_state
        self.ToggleWindowStyle(wx.STAY_ON_TOP)
    def on_close_evt(self, event):
        if event.CanVeto():
            if not self.save_if_modified():
                event.Veto()
                return

        self.Destroy()
    def getdatetime(self, event):
        t = time.localtime(time.time())
        st = time.strftime("%A, %B %d, %Y\n%I:%M %p", t)
        self.textcontrol.AppendText(st + "\n")

    def getdate(self, event):
        t = time.localtime(time.time())
        st = time.strftime("%A, %B %d, %Y", t)
        self.textcontrol.AppendText(st + "\n")

    def gettime(self, event):
        t = time.localtime(time.time())
        st = time.strftime("%I:%M %p", t)
        self.textcontrol.AppendText(st + "\n")

    def darktheme(self, event):
        background_color = "#000000"
        text_color = "#FFFFFF"
        statusbar_color = "#B8B8B8"
        toolbar_color = "#B8B8B8"
        font_size = 18
        font_name = "Times New Roman"

        # Apply dark theme to status bar and toolbar
        self.statusbar.SetBackgroundColour(statusbar_color)
        self.toolbar.SetBackgroundColour(toolbar_color)
        self.statusbar.Refresh()
        self.toolbar.Refresh()

        # Apply dark theme to text control
        self.textcontrol.StyleSetBackground(stc.STC_STYLE_DEFAULT, background_color)
        self.textcontrol.StyleSetForeground(0, text_color)
        self.textcontrol.StyleSetFont(stc.STC_STYLE_DEFAULT, wx.Font(font_size, wx.FONTFAMILY_MODERN,
                                                                     wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL, False, font_name))
        self.textcontrol.StyleSetBackground(0, wx.Colour(background_color))
        self.textcontrol.SetCaretForeground("white")  # Change cursor color to yellow
        
        self.textcontrol.Refresh()

    def lighttheme(self, event):
        background_color = "#FFFFFF"
        text_color = "#000000"
        statusbar_color = "#FFFFFF"
        toolbar_color = "#FFFFFF"
        font_size = 18
        font_name = "Times New Roman"

        # Apply light theme to status bar and toolbar
        self.statusbar.SetBackgroundColour(statusbar_color)
        self.toolbar.SetBackgroundColour(toolbar_color)
        self.statusbar.Refresh()
        self.toolbar.Refresh()

        # Apply light theme to text control
        self.textcontrol.StyleSetBackground(stc.STC_STYLE_DEFAULT, background_color)
        self.textcontrol.StyleSetForeground(0, text_color)
        self.textcontrol.StyleSetFont(stc.STC_STYLE_DEFAULT, wx.Font(font_size, wx.FONTFAMILY_MODERN,
                                                                     wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL, False, font_name))
        self.textcontrol.StyleSetBackground(0, wx.Colour(background_color))
        self.textcontrol.SetCaretForeground("black")  # Change cursor color to yellow

        self.textcontrol.Refresh()


            
#############################Enclosure options#####################################
    def on_show_enclose_dialog(self, event):
        """Show the EncloseDialog to select an enclosure."""
        dialog = EncloseDialog(self)
        if dialog.ShowModal() == wx.ID_OK:
            prefix, suffix = dialog.get_enclosure()
            if prefix and suffix:
                self.enclose_text(prefix, suffix)
        dialog.Destroy()

    def enclose_text(self, prefix, suffix):
        """Enclose selected text with the provided prefix and suffix."""
        start = self.textcontrol.GetSelectionStart()
        end = self.textcontrol.GetSelectionEnd()
        
        # If there's text selected, enclose it
        if start != end:
            selected_text = self.textcontrol.GetSelectedText()
            enclosed_text = f"{prefix}{selected_text}{suffix}"
            self.textcontrol.ReplaceSelection(enclosed_text)
            
            # Update selection to enclose the new text
            self.textcontrol.SetSelection(start, start + len(enclosed_text))

#############################Enclosure options#####################################            
            
            
            
            
            
        
        
    def onsimplefind(self, event):
        # Create and show FindReplaceDialog
        find_dlg = wx.FindReplaceDialog(self, self.find_data, "Find")
        find_dlg.Bind(wx.EVT_FIND, self.on_find)
        find_dlg.Bind(wx.EVT_FIND_CLOSE, lambda e: find_dlg.Destroy())
        find_dlg.Show()

        
        
        
        
        
        
        
        
        
        
        
        
    def on_find_replace(self, event):
        # Create and show FindReplaceDialog
        self.find_dialog = wx.FindReplaceDialog(self, self.find_data, "Find & Replace", wx.FR_REPLACEDIALOG)
        self.find_dialog.Show(True)
        
        
        
        
        
    def on_find(self, event):
        # Perform the find operation and store all positions
        find_str = self.find_data.GetFindString()
        flags = self.find_data.GetFlags()

        # Reset the found positions list and current index
        self.found_positions = []
        self.current_find_index = -1

        # Set the search flags based on the match case flag
        if flags & wx.FR_MATCHCASE:
            self.textcontrol.SetSearchFlags(stc.STC_FIND_MATCHCASE)
        else:
            self.textcontrol.SetSearchFlags(0)
        # Additional search flags
        if flags & wx.FR_WHOLEWORD:
            self.textcontrol.SetSearchFlags(self.textcontrol.GetSearchFlags() | stc.STC_FIND_WHOLEWORD)        
        # Set the search range to cover the entire document
        self.textcontrol.SetTargetStart(0)
        self.textcontrol.SetTargetEnd(self.textcontrol.GetTextLength())

        # Find all occurrences and store their positions
        while self.textcontrol.SearchInTarget(find_str) != -1:
            position = self.textcontrol.GetTargetStart()
            self.found_positions.append(position)
            # Move the search start position to after the current match to continue searching
            self.textcontrol.SetTargetStart(self.textcontrol.GetTargetEnd())
            self.textcontrol.SetTargetEnd(self.textcontrol.GetTextLength())

        # If no matches were found, show a message box
        if not self.found_positions:
            wx.MessageBox("No matches found", "Find Result")
        else:
            # Move to the first found occurrence
            self.current_find_index = 0
            self.highlight_current_match()

    def on_find_next(self, event):
        # Move to the next match in the list, if any
        if self.found_positions:
            self.current_find_index = (self.current_find_index + 1) % len(self.found_positions)
            self.highlight_current_match()
        else:
            wx.MessageBox("No matches found", "Find Result")

    def highlight_current_match(self):
        # Highlight the current match based on the current_find_index
        position = self.found_positions[self.current_find_index]
        find_str = self.find_data.GetFindString()
        self.textcontrol.GotoPos(position)
        self.textcontrol.SetSelection(position, position + len(find_str))

    def on_replace(self, event):
        # Perform the replace operation
        find_str = self.find_data.GetFindString()
        replace_str = self.find_data.GetReplaceString()
        flags = self.find_data.GetFlags()
        
        position = self.textcontrol.SearchNext(flags, find_str)
        if position == -1:
            wx.MessageBox("No matches found", "Replace Result")
        else:
            self.textcontrol.GotoPos(position)
            self.textcontrol.SetSelection(position, position + len(find_str))
            self.textcontrol.ReplaceSelection(replace_str)
            
    def on_replace_all(self, event):
        # Perform the replace all operation
        find_str = self.find_data.GetFindString()
        replace_str = self.find_data.GetReplaceString()
        
        # Set the target to the whole document
        self.textcontrol.SetTargetStart(0)
        self.textcontrol.SetTargetEnd(self.textcontrol.GetTextLength())
        
        # Find and replace all occurrences of the string
        while self.textcontrol.SearchInTarget(find_str) != -1:
            self.textcontrol.ReplaceTarget(replace_str)
            # Move the target start position to avoid replacing the same text repeatedly
            self.textcontrol.SetTargetStart(self.textcontrol.GetTargetEnd())
            self.textcontrol.SetTargetEnd(self.textcontrol.GetTextLength())
            
    def on_menu_help_about(self, event):
        self.AboutBox(event)
    def show_help(self, event):
        # Open the help frame when the help menu item is clicked
        help_frame = HelpFrame(None, title="ShieldText Help File")        
#     def on_menu_help_mysite(self, event):
#         self.open_sirboring()            
#     def open_sirboring(self):
#         webbrowser.open(HELP_URL, 2)            

    def AboutBox(self, event):

        description = """ShieldText is an encrypted text editor for
the Windows operating system."""
        # Features include powerful built-in editor,
        # advanced search capabilities, powerful batch renaming, file comparison,
        # extensive archive handling and more.

        licence = """ShieldText is free software; you can redistribute
it and/or modify it under the terms of the GNU General Public License as
published by the Free Software Foundation; either version 2 of the License,
or (at your option) any later version.

ShieldText is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
See the GNU General Public License for more details. You should have
received a copy of the GNU General Public License along with ShieldText"""

        info = wx.adv.AboutDialogInfo()
        info.SetIcon(wx.Icon(resource_path("images/about.png"), wx.BITMAP_TYPE_PNG))


        info.SetName("ShieldText")
        info.SetVersion("1.1")
        info.SetDescription(description)

        info.SetCopyright("(C) 2024 R.C. Davis")
        info.SetWebSite("https://www.sirboring.com")
        info.SetLicence(licence)
        info.AddDeveloper("R.C. Davis")
        #         info.AddDocWriter('R.C. Davis')
        info.AddArtist("Kendra (Schnapdazzle)")
        #         info.AddTranslator('R.C. Davis')

        wx.adv.AboutBox(info)
        
        
        
        
    def OnLinks(self, event):
        dialog = CustomAboutDialog(None)
        dialog.ShowModal()
        dialog.Destroy()        
        
        
        
        
# Statusbar counter begin
    def set_word_count(self, event):
        text = self.textcontrol.GetValue()
        word_count = len(text.split())
        char_count = len(text)
        line_count = len(text.splitlines())

        self.statusbar.SetStatusText(f"Words: {word_count}", 3)
        self.statusbar.SetStatusText(f"Characters: {char_count}", 4)
        self.statusbar.SetStatusText(f"Lines: {line_count}", 2)
# Statusbar counter end

    def OnTextChanged(self, event):
        self.modify = True
        self.statusbar.SetStatusText(' Modified', 1)
        event.Skip()                    
        


        
        # show and hide line number
        self.linenumberEnable = True




    def show_hide_linenumber(self, e):
        if self.linenumberi.IsChecked():
            self.textcontrol.SetMarginWidth(1, self.leftMarginWidth)
            self.textcontrol.SetMargins(10, 0)
            self.linenumberEnable = True
        else:
            self.textcontrol.SetMarginWidth(1, 0)
            self.textcontrol.SetMargins(0, 0)
            self.linenumberEnable = False
            
    def ToggleToolBar(self, e):
        if self.shtl.IsChecked():
            self.toolbar.Show()
            self.Update()
            self.Layout()
            self.Refresh()
            self.SendSizeEvent()
        else:
            self.toolbar.Hide()
            self.Update()
            self.Layout()
            self.Refresh()
            self.SendSizeEvent()

    def ToggleStatusBar(self, e):
        if self.shst.IsChecked():
            self.statusbar.Show()
            self.Update()
            self.Layout()
            self.Refresh()
            self.SendSizeEvent()
        else:
            self.statusbar.Hide()
            self.Update()
            self.Layout()
            self.Refresh()
            self.SendSizeEvent()
    def wordwrap(self, e):
        if self.wrapit.IsChecked():
            self.textcontrol.SetWrapMode(1)
            self.Update()
            self.Layout()
            self.Refresh()
            self.SendSizeEvent()
        else:
            self.textcontrol.SetWrapMode(0)
            self.Update()
            self.Layout()
            self.Refresh()
            self.SendSizeEvent()
            
    def on_print(self, event):
        print_dialog_data = wx.PrintDialogData()
        print_dialog_data.EnablePageNumbers(True)
        printer = wx.Printer(print_dialog_data)
        printout = TextPrintout(self.textcontrol.GetText())
        if not printer.Print(self, printout, True):
            wx.MessageBox("Print failed!", "Error", wx.OK | wx.ICON_ERROR)
        printout.Destroy()

    def onpreview(self, event):
        print_dialog_data = wx.PrintDialogData()
        printout = TextPrintout(self.textcontrol.GetText())
        preview = wx.PrintPreview(printout, TextPrintout(self.textcontrol.GetText()), print_dialog_data)
        if not preview.IsOk():
            wx.MessageBox("Failed to create print preview!", "Error", wx.OK | wx.ICON_ERROR)
            return

        preview_frame = wx.PreviewFrame(preview, self, "Print Preview")
        preview_frame.Initialize()
        preview_frame.Show()            
            
#################################################Show Password########################################            
class PasswordDialog(wx.Dialog):
    def __init__(self, parent, title="Enter Password"):
        super().__init__(parent, title=title, size=(500, 250))
        font = wx.Font(12, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD)        
        self.large_font = wx.Font(20, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD)
        
        self.panel = wx.Panel(self)
        self.password = ""
        
        # Create components with increased font size
        self.password_label = wx.StaticText(self.panel, label="Password:")
        self.password_label.SetFont(font)  # Set font for label
        self.password_ctrl = wx.TextCtrl(self.panel, style=wx.TE_PASSWORD, size=(250, 40))
        self.password_ctrl.SetFont(self.large_font)
        self.show_password_check = wx.CheckBox(self.panel, label="Show Password", size=(150, 40))
        self.show_password_check.SetFont(font)  # Set font for checkbox
        self.ok_button = wx.Button(self.panel, wx.ID_OK, label="OK", size=(100, 40))
        self.ok_button.SetFont(font)  # Set font for OK button
        self.cancel_button = wx.Button(self.panel, wx.ID_CANCEL, label="Cancel", size=(100, 40))
        self.cancel_button.SetFont(font)  # Set font for Cancel button
        
        # Layout
        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add(self.password_label, 0, wx.ALL, 5)
        sizer.Add(self.password_ctrl, 0, wx.EXPAND | wx.ALL, 5)
        sizer.Add(self.show_password_check, 0, wx.ALL, 5)
        
        button_sizer = wx.BoxSizer(wx.HORIZONTAL)
        button_sizer.Add(self.ok_button, 0, wx.ALL, 5)
        button_sizer.Add(self.cancel_button, 0, wx.ALL, 5)
        
        sizer.Add(button_sizer, 0, wx.ALIGN_CENTER)
        self.panel.SetSizer(sizer)

        # Bind events
        self.show_password_check.Bind(wx.EVT_CHECKBOX, self.on_toggle_password)
        self.Bind(wx.EVT_BUTTON, self.on_ok, self.ok_button)
        self.Bind(wx.EVT_BUTTON, self.on_cancel, self.cancel_button)
        
    def on_toggle_password(self, event):
        # Store current password input
        password_text = self.password_ctrl.GetValue()

        # Remove the old TextCtrl
        self.password_ctrl.Destroy()

        # Determine new style based on checkbox state
        style = wx.TE_LEFT if self.show_password_check.GetValue() else wx.TE_PASSWORD

        # Recreate the TextCtrl with the new style and set the existing text
        self.password_ctrl = wx.TextCtrl(self.panel, style=style)
        self.password_ctrl.SetFont(self.large_font)
        
        self.password_ctrl.SetValue(password_text)

        # Add the new TextCtrl to the sizer and update layout
        self.panel.GetSizer().Insert(1, self.password_ctrl, 0, wx.EXPAND | wx.ALL, 5)
        self.panel.Layout()

    def on_ok(self, event):
        self.password = self.password_ctrl.GetValue()
        self.EndModal(wx.ID_OK)

    def on_cancel(self, event):
        self.EndModal(wx.ID_CANCEL)

    def get_password(self):
        return self.password



# Update the on_open method to use PasswordDialog            
#################################################Show Password########################################




class EncloseDialog(wx.Dialog):
    def __init__(self, parent):
        super(EncloseDialog, self).__init__(parent, title="Choose Enclosure Type", size=(250, 150))

        # Enclosure options
        self.enclosures = [
            ("()", "Parentheses", "(", ")"),
            ("''", "Single Quotes", "'", "'"),
            ('""', "Double Quotes", '"', '"'),
            ("{}", "Braces", "{", "}"),
            ("``", "Backticks", "`", "`"),
            (".", "Periods", ".", "."),
            ("~~", "Tildes", "~", "~"),
            ("--", "Dashes", "-", "-"),
            ("__", "Underscores", "_", "_"),
            ("[]", "Brackets", "[", "]")
        ]

        # Dropdown list for enclosure options with a placeholder item
        choices = ["Enclose Options"] + [label for _, label, _, _ in self.enclosures]
        self.dropdown = wx.ComboBox(self, choices=choices, style=wx.CB_READONLY)
        self.dropdown.SetSelection(0)  # Set "Enclose Options" as the default selection

        # OK and Cancel buttons
        ok_button = wx.Button(self, wx.ID_OK, label="Enclose")
        cancel_button = wx.Button(self, wx.ID_CANCEL, label="Cancel")
        
        # Increase font size for buttons and dropdown
        font = wx.Font(16, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD)
        ok_button.SetFont(font)
        cancel_button.SetFont(font)
        self.dropdown.SetFont(font)

        ok_button.Bind(wx.EVT_BUTTON, self.on_ok)

        # Layout
        button_sizer = wx.BoxSizer(wx.HORIZONTAL)
        button_sizer.Add(ok_button, 0, wx.RIGHT, 5)
        button_sizer.Add(cancel_button, 0, wx.LEFT, 5)

        dialog_sizer = wx.BoxSizer(wx.VERTICAL)
        dialog_sizer.Add(self.dropdown, 0, wx.EXPAND | wx.ALL, 10)
        dialog_sizer.Add(button_sizer, 0, wx.ALIGN_CENTER | wx.ALL, 10)
        self.SetSizer(dialog_sizer)

        self.selected_prefix = None
        self.selected_suffix = None

    def on_ok(self, event):
        selection = self.dropdown.GetValue()
        for prefix, label, suffix, _ in self.enclosures:
            if label == selection:
                self.selected_prefix = prefix
                self.selected_suffix = suffix
                break
        self.EndModal(wx.ID_OK)


    def on_ok(self, event):
        """Handle OK button click and get selected prefix and suffix."""
        selection = self.dropdown.GetSelection()

        # Only set prefix and suffix if a valid option is selected
        if selection > 0:
            _, _, prefix, suffix = self.enclosures[selection - 1]  # Adjust index by -1
            self.selected_prefix = prefix
            self.selected_suffix = suffix
            self.EndModal(wx.ID_OK)
        else:
            wx.MessageBox("Please select an enclosure option.", "Info", wx.OK | wx.ICON_INFORMATION)

    def get_enclosure(self):
        """Return selected prefix and suffix."""
        return self.selected_prefix, self.selected_suffix

    def on_insert_filename(self, event):
        """Insert the current filename at the cursor position in the editor."""
        if self.filename:
            filename_only = os.path.basename(self.filename)
            self.editor.AddText(filename_only)  # Insert filename at current cursor position
#             self.editor.AddText(filename_only + '\n')  # Insert filename at current cursor position
        else:
            wx.MessageBox("No file is open", "Info", wx.OK | wx.ICON_INFORMATION)            





class HelpFrame(wx.Frame):
    def __init__(self, parent, title):
        super(HelpFrame, self).__init__(parent, title=title, size=(600, 400))
        
        # Create a panel for the help content
        panel = wx.Panel(self)
        sizer = wx.BoxSizer(wx.VERTICAL)
        # Set the titlebar icon
        self.SetIcon(wx.Icon('C:/Users/rc197/OneDrive/Desktop/HopeText/images/titlebar.ico', wx.BITMAP_TYPE_ICO))        
        # Create a HTML window
        self.html_window = wx.html.HtmlWindow(panel)
        self.html_window.SetPage(self.get_help_content())
        
        # Add the HTML window to the sizer
        sizer.Add(self.html_window, 1, wx.EXPAND | wx.ALL, 10)
        
        panel.SetSizer(sizer)
        self.Show()

    def get_help_content(self):
        # HTML content for the help file
        return """
        <html>

    <head>

        <title>Help - ShieldText</title>
        </head>
<body bgcolor="#FFFFFF" text="#000000">
        
        
        
            <h1>ShieldText Application Help</h1>
<h2>Overview</h2>
<h4>

<p>This help file provides guidance on how to use ShieldText effectively. It covers the main functionalities, including creating, opening, saving, and encrypting files.</p>
</h4>
<hr>

<h2>Creating a New File</h2>
<h4>

<p>To create a new file:</p>

<ol>
<li>Click on the "New" option in the menu.</li>
<li>If there are unsaved changes, you will be prompted to save them.</li>
<li>The editor will clear, and a new file will be created.</li>
</ol>
</h4>
<hr>

<h2>Opening a File</h2>
<h4>To open a file:
<ol>
<li>Click on the "Open" option in the menu.</li>
<li>Select either an encrypted file (<code>.rde</code>) or a plain text file (<code>.txt</code>).</li>
<li>If you select an encrypted file, you will be prompted to enter the decryption key.</li>
</h4>
<hr>

</ol>
<h2>Saving a File</h2>
<h4>

<p>To save a file:</p>

<ol>

<li>Click on the "Save" option in the menu.</li>
<li>If the file is new, you will be prompted to choose a file name and location.</li>
<li>For encrypted files, you will need to enter the encryption key.</li>
</ol>
</h4>
<hr>

<h2>Changing the Encryption Password</h2>
<h4>
<p>To change the encryption password:</p>
<ol>
<li>Ensure that an encrypted file is currently open.</li>
<li>Click on the "Change Password" option in the menu.</li>
<li>Follow the prompts to enter the new password.</li>
</ol>
</h4>
<hr>

<h2>Error Handling</h2>
<h4>
<p>If you encounter any errors while opening or saving files, the system will display an error message with details. Ensure that you have the correct permissions and that the file is not being used by another application.</p>
</h4>
<hr>
            <h2>Features</h2>
            <h4>
            <ul>
<li>ShieldText Supports creating, opening, saving, and encrypting files. Distinguishes between .txt files (plain text)<br> and .rde files (encrypted).</li>
<li>Encryption/Decryption: Uses the Fernet module for encryption. Password-based key derivation with SHA-256 and Base64 ensures secure encryption.</li>
<li>User Prompts: Utilizes dialogs for password input and confirmation.</li>
<li>Robust Error Handling: Catches decryption errors and prompts users for retries.</li>
<li>Other Features: There are some other mostly standard text editing features and some features I hope are useful.</li>

</ul>
<ol>            
</h4>
<h4>------&nbsp;&nbsp;&nbsp;<i><b>R.C.Davis</b></i></h4>

            </ol>


        </body>
        </html>
        """

class CustomAboutDialog(wx.Dialog):
    def __init__(self, parent):
        super().__init__(parent, title="ShieldText Link Collection", size=(400, 450))
        panel = wx.Panel(self)
        vbox = wx.BoxSizer(wx.VERTICAL)

        description = wx.StaticText(panel, label="Great Links: Friends, Family and Some Great Resources.")
        vbox.Add(description, flag=wx.ALL | wx.ALIGN_CENTER_HORIZONTAL, border=10)
        
        # Adding hyperlinks
        self.add_hyperlink(panel, vbox, "BrantaMedia.com", "http://www.brantamedia.com")
        self.add_hyperlink(panel, vbox, "BrantaMedia.com on Youtube", "https://www.youtube.com/@brantamediadotcom")
        self.add_hyperlink(panel, vbox, "BrantaMedia.com on X", "https://x.com/brantamediacom")
        self.add_hyperlink(panel, vbox, "R.C. Davis on X", "https://x.com/MrRCDavis")
        self.add_hyperlink(panel, vbox, "BrantaMedia.com on Rumble", "https://rumble.com/user/BrantaMediaDotCom")
        self.add_hyperlink(panel, vbox, "Wxpython", "https://www.wxpython.org")
        self.add_hyperlink(panel, vbox, "Thonny", "https://thonny.org")
        self.add_hyperlink(panel, vbox, "Geany", "https://www.geany.org")
        self.add_hyperlink(panel, vbox, "Python.org", "https://www.python.org")

        licence = wx.StaticText(panel, label="")
        vbox.Add(licence, flag=wx.ALL | wx.ALIGN_CENTER_HORIZONTAL, border=10)

        # Adding OK button
        ok_button = wx.Button(panel, label="OK")
        ok_button.Bind(wx.EVT_BUTTON, self.on_ok)
        vbox.Add(ok_button, flag=wx.ALL | wx.ALIGN_CENTER_HORIZONTAL, border=10)

        panel.SetSizer(vbox)

    def add_hyperlink(self, panel, sizer, label, url):
        link = wx.StaticText(panel, label=label)
        link.SetForegroundColour("blue")
        link.SetCursor(wx.Cursor(wx.CURSOR_HAND))
        link.Bind(wx.EVT_LEFT_DOWN, lambda event: webbrowser.open(url))
        sizer.Add(link, flag=wx.ALL | wx.ALIGN_CENTER_HORIZONTAL, border=5)

    def on_ok(self, event):
        self.Destroy()  # Close the dialog when OK is pressed
        


                
        
        
if __name__ == '__main__':
    app = wx.App()
    editor = ShieldText(None)
#     icon = wx.Icon("C:/Users/rc197/OneDrive/Desktop/HopeText/images/titlebar.ico", wx.BITMAP_TYPE_ICO)
#     editor.SetIcon(icon) 
    editor.Show()
    app.MainLoop()

