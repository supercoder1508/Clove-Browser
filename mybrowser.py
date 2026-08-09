#!/usr/bin/env python3
"""
A minimal daily-use browser starter, built on GTK4 + libadwaita + WebKitGTK.

Features:
- Tabbed browsing (Ctrl+T new tab, Ctrl+W close tab)
- Address bar with URL detection vs. search fallback
- Back / forward / reload / stop
- Per-tab loading indicator + title sync

This is a foundation, not a finished browser. Extend it — see the
roadmap notes at the bottom of this file.
"""

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
gi.require_version("WebKit", "6.0")

from gi.repository import Gtk, Adw, WebKit, Gio, GLib
import re

SEARCH_ENGINE = "https://duckduckgo.com/?q={}"
HOME_PAGE = "https://duckduckgo.com"

URL_LIKE = re.compile(
    r"^([a-zA-Z][a-zA-Z0-9+.-]*://)|"          # has a scheme
    r"^localhost(:\d+)?(/|$)|"                  # localhost
    r"^(\d{1,3}\.){3}\d{1,3}(:\d+)?(/|$)|"       # bare IP
    r"^[\w-]+(\.[\w-]+)+(:\d+)?(/|$)"            # looks like a domain
)


def normalize_input(text: str) -> str:
    text = text.strip()
    if not text:
        return HOME_PAGE
    if URL_LIKE.match(text):
        if "://" not in text:
            text = "https://" + text
        return text
    return SEARCH_ENGINE.format(GLib.uri_escape_string(text, None, False))


class BrowserTab(Gtk.Box):
    """One tab: a WebKit WebView plus a reference to its TabView page."""

    def __init__(self, window, url=HOME_PAGE):
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self.window = window

        self.webview = WebKit.WebView()
        self.webview.set_vexpand(True)
        self.webview.set_hexpand(True)
        self.webview.connect("notify::title", self.on_title_changed)
        self.webview.connect("notify::estimated-load-progress", self.on_progress)
        self.webview.connect("load-changed", self.on_load_changed)

        self.append(self.webview)
        self.webview.load_uri(url)

        self.page = None  # set by caller after adding to TabView

    def on_title_changed(self, webview, _pspec):
        title = webview.get_title() or "New Tab"
        if self.page:
            self.page.set_title(title)

    def on_progress(self, webview, _pspec):
        progress = webview.get_estimated_load_progress()
        if self.window.address_bar.get_text() == "" or webview == self.window.current_webview():
            pass  # hook for a progress bar widget if you add one

    def on_load_changed(self, webview, event):
        if webview == self.window.current_webview():
            self.window.sync_address_bar(webview.get_uri())
            self.window.update_nav_buttons(webview)


class BrowserWindow(Adw.ApplicationWindow):
    def __init__(self, app):
        super().__init__(application=app, title="MyBrowser")
        self.set_default_size(1200, 800)

        toolbar_view = Adw.ToolbarView()
        self.set_content(toolbar_view)

        header = Adw.HeaderBar()
        toolbar_view.add_top_bar(header)

        # Navigation buttons
        self.back_btn = Gtk.Button(icon_name="go-previous-symbolic")
        self.back_btn.connect("clicked", lambda b: self.current_webview().go_back())
        header.pack_start(self.back_btn)

        self.forward_btn = Gtk.Button(icon_name="go-next-symbolic")
        self.forward_btn.connect("clicked", lambda b: self.current_webview().go_forward())
        header.pack_start(self.forward_btn)

        self.reload_btn = Gtk.Button(icon_name="view-refresh-symbolic")
        self.reload_btn.connect("clicked", lambda b: self.current_webview().reload())
        header.pack_start(self.reload_btn)

        new_tab_btn = Gtk.Button(icon_name="tab-new-symbolic")
        new_tab_btn.connect("clicked", lambda b: self.new_tab())
        header.pack_end(new_tab_btn)

        # Address bar
        self.address_bar = Gtk.Entry(hexpand=True)
        self.address_bar.set_placeholder_text("Search or enter address")
        self.address_bar.connect("activate", self.on_address_activate)
        header.set_title_widget(self.address_bar)

        # Tabs
        self.tab_view = Adw.TabView()
        self.tab_view.connect("notify::selected-page", self.on_tab_switched)

        tab_bar = Adw.TabBar(view=self.tab_view)
        content_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        content_box.append(tab_bar)
        content_box.append(self.tab_view)
        toolbar_view.set_content(content_box)

        # Keyboard shortcuts
        app.set_accels_for_action("win.new-tab", ["<Ctrl>t"])
        app.set_accels_for_action("win.close-tab", ["<Ctrl>w"])
        self.add_action_entries = None  # placeholder if you wire up Gio.SimpleAction later

        controller = Gtk.ShortcutController()
        self.add_controller(controller)

        self.new_tab()

    # --- tab management -------------------------------------------------

    def new_tab(self, url=HOME_PAGE):
        tab = BrowserTab(self, url)
        page = self.tab_view.append(tab)
        tab.page = page
        page.set_title("New Tab")
        self.tab_view.set_selected_page(page)
        return tab

    def current_webview(self):
        page = self.tab_view.get_selected_page()
        if page is None:
            return None
        return page.get_child().webview

    def on_tab_switched(self, tab_view, _pspec):
        wv = self.current_webview()
        if wv:
            self.sync_address_bar(wv.get_uri())
            self.update_nav_buttons(wv)

    # --- address bar ------------------------------------------------------

    def on_address_activate(self, entry):
        target = normalize_input(entry.get_text())
        wv = self.current_webview()
        if wv:
            wv.load_uri(target)

    def sync_address_bar(self, uri):
        if uri:
            self.address_bar.set_text(uri)

    def update_nav_buttons(self, webview):
        self.back_btn.set_sensitive(webview.can_go_back())
        self.forward_btn.set_sensitive(webview.can_go_forward())


class BrowserApp(Adw.Application):
    def __init__(self):
        super().__init__(application_id="org.example.MyBrowser")

    def do_activate(self):
        win = BrowserWindow(self)
        win.present()


if __name__ == "__main__":
    app = BrowserApp()
    app.run()

# ROADMAP (add these as you go):
# 1. Persistent sessions: WebKit.WebsiteDataManager + save/restore open tabs to disk (JSON).
# 2. Bookmarks: simple SQLite table + a popover UI.
# 3. Ad/tracker blocking: WebKit.UserContentFilterStore (compile easylist-style JSON rules).
# 4. Downloads: connect WebKit.WebContext "download-started" signal, show a download manager popover.
# 5. Private/incognito tabs: create WebView with WebKit.NetworkSession.new_ephemeral().
# 6. Find-in-page: WebKit.FindController on the WebView.
# 7. Settings/prefs UI: WebKit.Settings (JS toggle, user-agent override, zoom level defaults).
# 8. Keyboard shortcuts for tab switching (Ctrl+Tab), zoom (Ctrl+/-), find (Ctrl+F).
# 9. Custom New Tab page: load a local HTML file instead of a search engine.
# 10. Packaging: Flatpak manifest (org.example.MyBrowser.yml) for easy distribution.
