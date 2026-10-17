#!/usr/bin/env python3
"""goblin-play — hierarchical Jellyfin media browser with gamepad support.

Navigate: Libraries → Shows/Movies → Seasons → Episodes
Controls: D-pad to browse, A/Enter to select, B/Esc to go back
"""
import json
import os
import subprocess
import sys
import urllib.error
import urllib.request

from textual.app import App, ComposeResult
from textual.containers import Container, Vertical
from textual.widgets import Button, Footer, Header, Input, Label, ListView, ListItem, Static


class MediaItem(ListItem):
    """A single item in the list (library, show, season, or episode)."""
    def __init__(self, name: str, item_id: str, item_type: str, **kwargs):
        super().__init__(**kwargs)
        self.name = name
        self.item_id = item_id
        self.item_type = item_type  # Collection, Series, Season, Episode, Movie
    
    def compose(self):
        # Choose icon based on type
        icons = {
            "Collection": "📁",
            "Series": "📺",
            "Season": "🗓️",
            "Episode": "▶️",
            "Movie": "🎬",
        }
        icon = icons.get(self.item_type, "📄")
        yield Button(f"{icon} {self.name}", id=self.item_id, variant="default")


class GoblinPlay(App):
    """Hierarchical Jellyfin browser with neon styling and gamepad support."""

    CSS = """
    Screen {
        background: #1e1e2e;
        color: #cdd6f4;
    }
    Header {
        background: #181825;
        color: #89b4fa;
    }
    Footer {
        background: #181825;
        color: #a6adc8;
    }
    #breadcrumb {
        height: 1;
        padding: 0 1;
        color: #89dceb;
        text-style: bold;
    }
    #search-box {
        height: 3;
        padding: 0 1;
    }
    #media-list {
        height: 1fr;
        padding: 0 1;
        overflow-y: auto;
    }
    ListView {
        height: auto;
    }
    ListItem {
        height: 3;
        padding: 0;
    }
    Button {
        width: 100%;
        height: 100%;
        background: #313244;
        color: #cdd6f4;
        border: solid #585b70;
        text-align: left;
    }
    Button:hover {
        background: #45475a;
        border: solid #89b4fa;
    }
    Button:focus {
        background: #45475a;
        border: solid #89dceb;
    }
    Input {
        background: #2a2a3e;
        color: #cdd6f4;
        border: solid #585b70;
    }
    Input:focus {
        border: solid #89dceb;
    }
    """

    BINDINGS = [
        ("up", "cursor_up", "Up"),
        ("down", "cursor_down", "Down"),
        ("enter", "select_item", "Select"),
        ("escape", "go_back", "Back"),
        ("q", "quit", "Quit"),
        ("r", "refresh", "Refresh"),
    ]

    def __init__(self, jellyfin_url: str, api_key: str):
        super().__init__()
        self.jellyfin_url = jellyfin_url.rstrip("/")
        self.api_key = api_key
        
        # Navigation stack: [(parent_id, parent_name), ...]
        self.nav_stack = []
        self.current_parent_id = None
        self.current_view = "libraries"  # libraries, items, episodes
    
    def api_get(self, endpoint, params=None):
        """Make authenticated API request to Jellyfin."""
        url = f"{self.jellyfin_url}{endpoint}"
        if params:
            url += "?" + "&".join(params)
        
        req = urllib.request.Request(url, headers={
            "Authorization": f'MediaBrowser Token="{self.api_key}"'
        })
        try:
            with urllib.request.urlopen(req, timeout=8) as r:
                return json.load(r)
        except (urllib.error.URLError, ValueError, TimeoutError, OSError) as e:
            self.notify(f"API error: {e}", severity="error")
            return None
    
    def fetch_libraries(self):
        """Get top-level library folders."""
        data = self.api_get("/Library/VirtualFolders")
        if data and isinstance(data, list):
            return [{"Name": d.get("Name", "?"), "Id": d.get("Id", ""), "Type": "Collection"} 
                    for d in data if d.get("Id")]
        return []
    
    def fetch_items(self, parent_id=None, item_types=None):
        """Get items in a folder/library."""
        params = ["Recursive=false", "format=json", "Limit=200"]
        if parent_id:
            params.append(f"ParentId={parent_id}")
        if item_types:
            params.append(f"IncludeItemTypes={','.join(item_types)}")
        
        data = self.api_get("/Items", params)
        if data and "Items" in data:
            return data["Items"]
        return []
    
    def get_breadcrumb(self):
        """Build breadcrumb from nav stack."""
        parts = ["🏠 Home"]
        for _, name in self.nav_stack[-3:]:  # Show last 3 levels
            parts.append(name)
        return " › ".join(parts)
    
    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Vertical():
            yield Label("", id="breadcrumb")
            yield Input(placeholder="Search...", id="search-box")
            with Container(id="media-list"):
                yield ListView(id="items-view")
        yield Footer()
    
    async def on_mount(self) -> None:
        """Load initial view (libraries)."""
        await self.show_libraries()
    
    async def show_libraries(self):
        """Show top-level libraries."""
        self.current_view = "libraries"
        self.current_parent_id = None
        self.nav_stack = []
        
        self.query_one("#breadcrumb", Label).update("🏠 Home")
        self.notify("Loading libraries...")
        
        libs = self.fetch_libraries()
        list_view = self.query_one("#items-view", ListView)
        await list_view.clear()
        
        for lib in libs:
            await list_view.append(MediaItem(lib["Name"], lib["Id"], "Collection"))
        
        if not libs:
            self.notify("No libraries found", severity="warning")
    
    async def show_items(self, parent_id, parent_name, item_types=None):
        """Show items within a library/folder."""
        self.current_view = "items"
        self.current_parent_id = parent_id
        
        self.query_one("#breadcrumb", Label).update(self.get_breadcrumb())
        self.notify(f"Loading {parent_name}...")
        
        items = self.fetch_items(parent_id, item_types)
        list_view = self.query_one("#items-view", ListView)
        await list_view.clear()
        
        for item in items[:100]:  # Limit for performance
            name = item.get("Name", "?")
            item_id = item.get("Id", "")
            item_type = item.get("Type", "Folder")
            
            if item_id:
                await list_view.append(MediaItem(name, item_id, item_type))
        
        if not items:
            self.notify("No items found", severity="warning")
    
    async def show_seasons(self, series_id, series_name):
        """Show seasons for a series."""
        self.nav_stack.append((series_id, series_name))
        self.current_view = "seasons"
        self.current_parent_id = series_id
        
        self.query_one("#breadcrumb", Label).update(self.get_breadcrumb())
        self.notify(f"Loading {series_name} seasons...")
        
        seasons = self.fetch_items(series_id, ["Season"])
        list_view = self.query_one("#items-view", ListView)
        await list_view.clear()
        
        for season in seasons:
            name = season.get("Name", "?")
            item_id = season.get("Id", "")
            if item_id:
                await list_view.append(MediaItem(name, item_id, "Season"))
    
    async def show_episodes(self, season_id, season_name):
        """Show episodes for a season."""
        self.nav_stack.append((season_id, season_name))
        self.current_view = "episodes"
        self.current_parent_id = season_id
        
        self.query_one("#breadcrumb", Label).update(self.get_breadcrumb())
        self.notify(f"Loading {season_name} episodes...")
        
        episodes = self.fetch_items(season_id, ["Episode"])
        list_view = self.query_one("#items-view", ListView)
        await list_view.clear()
        
        for ep in episodes:
            name = ep.get("Name", "?")
            item_id = ep.get("Id", "")
            if item_id:
                await list_view.append(MediaItem(name, item_id, "Episode"))
    
    def on_input_changed(self, event: Input.Changed) -> None:
        """Filter items as user types."""
        search = event.value.lower()
        list_view = self.query_one("#items-view", ListView)
        for child in list_view.children:
            if isinstance(child, MediaItem):
                child.display = search in child.name.lower()
    
    async def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle item selection (A button / Enter)."""
        btn = event.button
        item_id = btn.id
        
        # Find the MediaItem parent to get type
        media_item = btn.parent
        while media_item and not isinstance(media_item, MediaItem):
            media_item = media_item.parent
        
        if not media_item:
            return
        
        item_type = media_item.item_type
        item_name = media_item.name
        
        # Navigate based on item type
        if item_type == "Collection":
            # It's a library - show movies/shows in it
            await self.show_items(item_id, item_name, ["Movie", "Series"])
            self.nav_stack.append((item_id, item_name))
        
        elif item_type == "Series":
            # Show seasons
            await self.show_seasons(item_id, item_name)
        
        elif item_type == "Season":
            # Show episodes
            await self.show_episodes(item_id, item_name)
        
        elif item_type in ("Episode", "Movie"):
            # Play it!
            stream_url = f"{self.jellyfin_url}/Videos/{item_id}/stream"
            stream_url += f"?api_key={self.api_key}&MaxStreamingBitrate=40000000"
            self.exit(stream_url)
    
    def action_go_back(self):
        """B button: go back one level."""
        if self.current_view == "episodes":
            # Go back to seasons
            if len(self.nav_stack) >= 2:
                season_id, _ = self.nav_stack.pop()
                series_id, series_name = self.nav_stack[-1]
                asyncio.run_coroutine_threadsafe(
                    self.show_seasons(series_id, series_name),
                    self._loop
                )
        elif self.current_view == "seasons":
            # Go back to items (shows/movies list)
            if len(self.nav_stack) >= 1:
                series_id, _ = self.nav_stack.pop()
                if self.nav_stack:
                    lib_id, lib_name = self.nav_stack[-1]
                    asyncio.run_coroutine_threadsafe(
                        self.show_items(lib_id, lib_name, ["Movie", "Series"]),
                        self._loop
                    )
                else:
                    asyncio.run_coroutine_threadsafe(
                        self.show_libraries(),
                        self._loop
                    )
        elif self.current_view == "items":
            # Go back to libraries
            if self.nav_stack:
                self.nav_stack.pop()
            asyncio.run_coroutine_threadsafe(
                self.show_libraries(),
                self._loop
            )
        else:
            # At root, quit
            self.exit()
    
    def action_refresh(self):
        """R button: refresh current view."""
        # Reload current view
        if self.current_view == "libraries":
            asyncio.run_coroutine_threadsafe(self.show_libraries(), self._loop)
        elif self.current_view == "items" and self.current_parent_id:
            _, name = self.nav_stack[-1] if self.nav_stack else (None, "items")
            asyncio.run_coroutine_threadsafe(
                self.show_items(self.current_parent_id, name, ["Movie", "Series"]),
                self._loop
            )


if __name__ == "__main__":
    import asyncio
    
    JELLYFIN_URL = os.environ.get("JELLYFIN_URL", "")
    JELLYFIN_KEY = os.environ.get("JELLYFIN_KEY", "")
    
    if not JELLYFIN_URL:
        print("JELLYFIN_URL not set; configure via /etc/default/goblin-dash")
        sys.exit(1)
    
    app = GoblinPlay(JELLYFIN_URL, JELLYFIN_KEY)
    result = app.run()
    
    if result:
        # Launch mpv with the selected stream
        cmd = ["mpv", "--force-window=yes", "--idle=no", result]
        subprocess.run(cmd)
