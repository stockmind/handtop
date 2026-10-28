#!/usr/bin/env python3
"""Render the Jellyfin client against a demo server, for the documentation.

The mock drives the *real* app - real widgets, real CSS, real layout - and
only replaces the Jellyfin server with a canned one, so the pictures cannot
drift away from the UI.

Usage:
    python3 tools/jellyfin-mock.py docs/img     # render the pictures
    python3 tools/jellyfin-mock.py --live        # run it in a terminal (on the
                                              # device, to photograph the
                                              # real screen)
"""
import asyncio
import importlib.machinery
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
# The client: from the repository, or the one installed on a device.
APP = Path(os.environ.get("JELLYFIN_APP",
                          HERE.parent / "overlay" / "usr" / "local" / "bin" / "jellyfin"))
if not APP.exists():
    APP = Path("/usr/local/bin/jellyfin")
g = importlib.machinery.SourceFileLoader("jellyfin_app", str(APP)).load_module()

# --------------------------------------------------------------- fake server

def media(width=1920, height=1080, minutes=42, year=2024, subs=("eng",)):
    streams = [{"Type": "Video", "Width": width, "Height": height, "Codec": "h264"},
               {"Type": "Audio", "Codec": "aac", "Language": "jpn"}]
    for index, language in enumerate(subs):
        streams.append({"Type": "Subtitle", "Index": index, "Codec": "subrip",
                        "Language": language, "IsDefault": index == 0,
                        "IsForced": False,
                        "DisplayTitle": f"{language.upper()} - SUBRIP"})
    return {"Width": width, "Height": height,
            "MediaSources": [{"Id": "src-" + str(abs(hash((width, height, subs))))[:12],
                               "MediaStreams": streams}]}


def item(name, kind, ident, **kwargs):
    data = {"Name": name, "Id": ident, "Type": kind, "ProductionYear": kwargs.pop("year", 2024),
            "RunTimeTicks": kwargs.pop("minutes", 42) * 600_000_000,
            "UserData": {"PlaybackPositionTicks": kwargs.pop("resume", 0)},
            "Container": "mkv"}
    for key in ("CollectionType", "IndexNumber", "ParentIndexNumber", "SeriesName"):
        if key in kwargs:
            data[key] = kwargs.pop(key)
    data.update(media(**kwargs))
    return data


LIBRARIES = [
    item("Lantern Bay", "Collection", "lib-lantern", CollectionType="tvshows", width=0, height=0),
    item("Paper Moons", "Collection", "lib-moons", CollectionType="movies", width=0, height=0),
    item("Harbour Lights", "Collection", "lib-harbour", CollectionType="musicvideos", width=0, height=0),
    item("Quiet Rooms", "Collection", "lib-quiet", CollectionType="music", width=0, height=0),
]

SERIES = [
    item("The Lantern Road", "Series", "ser-lantern", minutes=45, year=2023),
    item("Ashfall Chronicles", "Series", "ser-ashfall", minutes=52, year=2021),
    item("Harbour Lights", "Series", "ser-harbour", minutes=38, year=2025),
    item("The Quiet Machine", "Series", "ser-quiet", minutes=41, year=2019),
]

SEASONS = [item("Season 1", "Season", "sea-1", IndexNumber=1, width=0, height=0),
           item("Season 2", "Season", "sea-2", IndexNumber=2, width=0, height=0)]

EPISODES = [
    item("The Long Way Home", "Episode", "ep-1", IndexNumber=1, ParentIndexNumber=1, minutes=44),
    item("Salt and Smoke", "Episode", "ep-2", IndexNumber=2, ParentIndexNumber=1, minutes=41),
    item("Nine Lanterns", "Episode", "ep-3", IndexNumber=3, ParentIndexNumber=1, minutes=47,
         resume=1_650_000_000),
    item("A Quiet Harbour", "Episode", "ep-4", IndexNumber=4, ParentIndexNumber=1, minutes=39),
    item("The Paper Moon", "Episode", "ep-5", IndexNumber=5, ParentIndexNumber=1, minutes=43),
]

MOVIES = [
    item("Driftwood", "Movie", "mov-1", minutes=98, year=2025),
    item("The Ninth Wave", "Movie", "mov-2", minutes=112, year=2022),
    item("Paper Lanterns", "Movie", "mov-3", minutes=87, year=2024),
    item("Saltwater", "Movie", "mov-4", minutes=104, year=2021),
]

VIDEOS = [
    item("Aurora (Live Session)", "MusicVideo", "vid-1", minutes=4, width=1920, height=1080),
    item("Little Fires (Official Video)", "MusicVideo", "vid-2", minutes=3, width=1920, height=1080),
    item("Northbound", "MusicVideo", "vid-3", minutes=5, width=3840, height=2160),
]

FOLDERS = {
    "lib-lantern": SERIES,
    "lib-moons": MOVIES,
    "lib-harbour": VIDEOS,
    "lib-quiet": [],
    "ser-lantern": SEASONS,
    "ser-ashfall": SEASONS,
    "ser-harbour": SEASONS,
    "ser-quiet": SEASONS,
    "sea-1": EPISODES,
    "sea-2": EPISODES,
}


class FakeServer(g.Jellyfin):
    """A Jellyfin server that only knows the fake library above."""

    def __init__(self):
        super().__init__("http://mock.local:8096", "mock-key")
        self.error = ""

    def get(self, endpoint, params=None):
        if endpoint.startswith("/Library/VirtualFolders"):
            return LIBRARIES
        if endpoint.startswith("/Items"):
            parent = ""
            for param in params or []:
                if param.startswith("ParentId="):
                    parent = param.split("=", 1)[1]
            items = FOLDERS.get(parent, [])
            types = ""
            for param in params or []:
                if param.startswith("IncludeItemTypes="):
                    types = param.split("=", 1)[1].split(",")
            if types:
                items = [i for i in items if i["Type"] in types]
            return {"Items": items, "TotalRecordCount": len(items)}
        if endpoint.startswith("/Users/") and endpoint.endswith("/Items/Resume"):
            return {"Items": []}
        if endpoint.startswith("/Users/"):
            return {"Configuration": {"SubtitleLanguagePreference": "eng",
                                      "SubtitleMode": "Always"}}
        if endpoint.startswith("/MediaSegments/"):
            return {"Items": []}
        return None

    def user_id(self):
        return "user-1"

    def subtitle_url(self, item, prefs=None):
        track = g.subtitle_track(item, prefs)
        if track is None:
            return None
        return (f"http://mock.local/Videos/{item['Id']}/Subtitles/{track['Index']}"
                f"/Stream.srt?api_key=mock-key")

    def segments(self, item_id):
        return []

    def resume_positions(self):
        return {i["Id"]: i["UserData"]["PlaybackPositionTicks"]
                for i in EPISODES + SERIES if i["UserData"]["PlaybackPositionTicks"]}


# --------------------------------------------------------------- fake device

g.battery = lambda: (82, "Discharging")
g.temperature = lambda: 36.0
g.free_bytes = lambda: 43 * 1_000_000_000
g.cpu_snapshot = lambda: (0, 0)
g.cpu_busy = lambda prev, cur: 0.07


async def shot(app, pilot, name, out):
    await pilot.pause()
    await pilot.pause()
    svg = app.export_screenshot()
    # The device runs Noto Sans Mono; use it here too, so the PNG has the
    # same glyphs (the markers) as the handheld.
    svg = svg.replace("Fira Code, monospace", "Noto Sans Mono, monospace")
    (out / f"{name}.svg").write_text(svg)
    try:
        import cairosvg
        cairosvg.svg2png(bytestring=svg.encode(), write_to=str(out / f"{name}.png"),
                         output_width=1280, background_color="#16181d")
    except Exception as exc:                       # cairosvg is optional
        print(f"  (no PNG: {exc})")
    print(f"  {name}.svg")


async def live():
    """Run the mock in a real terminal, so a device can be photographed."""
    app = g.JellyfinApp()
    app.api = FakeServer()

    async def walk():
        await asyncio.sleep(2)
        await app.open(LIBRARIES[0])
        await asyncio.sleep(2)
        await app.open(SERIES[0])
        await asyncio.sleep(2)
        await app.open(SEASONS[0])

    app.call_later(walk)
    await app.run_async()


async def main():
    if "--live" in sys.argv:
        await live()
        return
    out = Path(sys.argv[1] if len(sys.argv) > 1 else "docs/img")
    out.mkdir(parents=True, exist_ok=True)
    app = g.JellyfinApp()
    app.api = FakeServer()
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        await shot(app, pilot, "jellyfin-home", out)

        await app.open(LIBRARIES[0])               # the series library
        await pilot.pause()
        await shot(app, pilot, "jellyfin-series", out)

        await app.open(SERIES[0])                  # into a series
        await pilot.pause()
        await shot(app, pilot, "jellyfin-seasons", out)

        await app.open(SEASONS[0])                 # into the season
        await pilot.pause()
        await shot(app, pilot, "jellyfin-episodes", out)

        await app.open(MOVIES[0])                  # a movie row
        await pilot.pause()
        await shot(app, pilot, "jellyfin-movies", out)


if __name__ == "__main__":
    asyncio.run(main())
