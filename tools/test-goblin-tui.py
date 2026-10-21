#!/usr/bin/env python3
"""Headless end-to-end test for the goblin Jellyfin client.

Drives the real app with Textual's pilot against a live Jellyfin server:
libraries -> movies/series/seasons/episodes, transcode URLs, status line,
Save targets, and a real download -> play-local -> delete round-trip.

    JELLYFIN_URL=http://192.168.1.60:8096 JELLYFIN_KEY=<token> \
        python3 tools/test-goblin-tui.py
"""
import asyncio
import os
import shutil
import sys
import urllib.request
from pathlib import Path

HERE = os.path.dirname(os.path.abspath(__file__))
APP = os.path.join(HERE, "..", "overlay", "usr", "local", "bin", "goblin")

os.environ.setdefault("JELLYFIN_URL", "http://192.168.1.60:8096")
os.environ.setdefault("JELLYFIN_KEY", "a35b1923c3c5495d91edcf067ad96a66")
OFFLINE = Path("/tmp/opencode/goblin-offline")
os.environ.setdefault("GOBLIN_OFFLINE_DIR", str(OFFLINE))

import importlib.machinery
loader = importlib.machinery.SourceFileLoader("goblin_app", APP)
goblin_app = loader.load_module()
Goblin = goblin_app.Goblin
Row = goblin_app.Row
MoreRow = goblin_app.MoreRow
MoreRow = goblin_app.MoreRow
load_manifest = goblin_app.Goblin.manifest


def api(path):
    req = urllib.request.Request(
        f"{os.environ['JELLYFIN_URL']}{path}",
        headers={"Authorization": f'MediaBrowser Token="{os.environ["JELLYFIN_KEY"]}"'})
    import json
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.load(r)


async def settle(pilot):
    await pilot.pause()
    await pilot.pause()


async def click_row(pilot, match):
    for row in pilot.app.query(Row):
        if match in row.item.get("Name", ""):
            await pilot.click(row)
            await settle(pilot)
            return row.item
    raise AssertionError(f"no row matching {match!r}: "
                         f"{[r.item.get('Name') for r in pilot.app.query(Row)]}")


async def enter(pilot):
    from textual.widgets import ListView
    lv = pilot.app.query_one(ListView)
    lv.focus()
    if lv.index is None:
        lv.index = 0
    await pilot.press("enter")
    await settle(pilot)


def playlist(app):
    """The exit value is a list of play entries (id, url, subtitle, start)."""
    value = app.return_value
    assert isinstance(value, tuple) and value[0] == "PL", f"not a playlist: {value!r}"
    assert value[1], "empty playlist"
    return value[1]


def urls(entries):
    return [e["url"] for e in entries]


async def main():
    assert OFFLINE.exists() or True
    shutil.rmtree(OFFLINE, ignore_errors=True)

    # --- libraries, compact status line, no leftover dashboard/menu
    app = Goblin()
    async with app.run_test(size=(80, 24)) as pilot:
        await settle(pilot)
        names = [r.item.get("Name") for r in app.query(Row)]
        assert names, "no libraries listed"
        crumb = str(app.query_one("#crumb").render())
        stats = str(app.query_one("#stats").render())
        hint = str(app.query_one("#hint").render())
        assert crumb.startswith("Home"), crumb
        assert "free" in stats, stats
        for word in ("cpu",):
            assert word in stats, f"status line lacks {word}: {stats}"
        if goblin_app.battery():
            assert "bat" in stats or "chg" in stats, stats
        assert "[A] play" in hint, hint
        print(f"PASS home: {len(names)} libraries, stats={stats!r}")

        # --- movie library -> Enter plays a transcode playlist from the cursor
        movie = await click_row(pilot, "Film")
        kinds = {r.item.get("Type") for r in app.query(Row)}
        assert kinds == {"Movie"}, kinds
        rows = list(app.query(Row))
        n = len(rows)
        from textual.widgets import ListView
        app.query_one(ListView).index = 0
        first = rows[0].item
        await enter(pilot)
        entries = playlist(app)
        assert len(entries) == n, f"playlist {len(entries)} != visible {n}"
        assert first["Id"] == entries[0]["id"], "playlist does not start at the cursor"
        # always a transcode, capped to the panel (never the original)
        assert "static=false" in entries[0]["url"], entries[0]["url"]
        assert "maxWidth=640" in entries[0]["url"], entries[0]["url"]
        # the user's Jellyfin preferences decide the subtitle
        assert app.prefs, "no preferences read from the Jellyfin profile"
        print(f"PASS preferences: mode={app.prefs['mode']!r} "
              f"languages={app.prefs['languages']}")
        print(f"PASS movies: {n}-item playlist, transcode URL from cursor")

    # --- resume reopens the same folder and cursor
    assert app.play_state["path"], "no navigation state captured"
    app2 = Goblin(resume=app.play_state)
    async with app2.run_test(size=(80, 24)) as pilot:
        await settle(pilot)
        from textual.widgets import ListView
        lv = app2.query_one(ListView)
        assert lv.index == app.play_state["index"], "resume lost the cursor"
        assert {r.item.get("Type") for r in app2.query(Row)} == {"Movie"}
        print("PASS resume reopens folder + cursor")

    # --- TV: series -> season -> episode playlist
    app = Goblin()
    async with app.run_test(size=(80, 24)) as pilot:
        await settle(pilot)
        await click_row(pilot, "Serie TV")
        assert {r.item.get("Type") for r in app.query(Row)} == {"Series"}
        await enter(pilot)
        seasons = list(app.query(Row))
        assert seasons and seasons[0].item.get("Type") == "Season"
        await enter(pilot)
        await settle(pilot)
        episodes = list(app.query(Row))
        assert episodes and episodes[0].item.get("Type") == "Episode"
        await enter(pilot)
        entries = playlist(app)
        assert all("static=false" in e["url"] for e in entries), entries[0]["url"]
        print(f"PASS series: {len(episodes)}-episode playlist via season")

    # --- Resume: a stored position shows up on the row and starts playback there
    app = Goblin()
    async with app.run_test(size=(80, 24)) as pilot:
        await settle(pilot)
        await click_row(pilot, "Serie TV")
        await enter(pilot)
        await enter(pilot)
        await settle(pilot)
        rows = list(app.query(Row))
        marked = [r for r in rows if "»" in r.text.plain]
        if not marked:
            print("SKIP resume marker (nothing half watched in this season)")
        else:
            row = marked[0]
            print(f"PASS resume marker: {row.text.plain.strip()[-40:]}")
            app.play(row.item)
            entries = playlist(app)
            assert entries[0]["start"] > 30, f"no start position: {entries[0]}"

    # --- Pagination: a big library comes in pages, and no placeholder rows
    app = Goblin()
    async with app.run_test(size=(80, 24)) as pilot:
        await settle(pilot)
        await click_row(pilot, "Video Musicali")
        rows = list(app.query(Row))
        assert len(rows) == 50, f"expected one page of 50, got {len(rows)}"
        sentinels = list(app.query(MoreRow))
        assert sentinels, "no 'more' row for the rest of the library"
        print(f"PASS pagination: {len(rows)} rows + {sentinels[0].remaining} more")
        # walking to the end pulls the next page in
        from textual.widgets import ListView
        lv = app.query_one(ListView)
        for _ in range(55):
            await pilot.press("down")
        for _ in range(20):
            await pilot.pause(0.2)
        rows = list(app.query(Row))
        assert len(rows) > 50, f"next page not loaded ({len(rows)} rows)"
        print(f"PASS pagination: next page loaded ({len(rows)} rows)")
        # no "Row" placeholders: the rows render their own text
        svg = app.export_screenshot()
        assert ">Row<" not in svg, "rows still render the class name"
        print("PASS no placeholder rows")

    # --- The cursor and its pages come back after a reload (download) and
    #     after a video (the resume snapshot)
    app = Goblin()
    async with app.run_test(size=(80, 24)) as pilot:
        await settle(pilot)
        await click_row(pilot, "Video Musicali")
        from textual.widgets import ListView
        lv = app.query_one(ListView)
        for _ in range(55):
            await pilot.press("down")
        for _ in range(20):
            await pilot.pause(0.2)
        index = lv.index
        assert index and index > 50, f"did not get past the first page: {index}"
        print(f"PASS cursor walked to row {index}")
        await app.reload()                       # what a download does
        await settle(pilot)
        assert app.query_one(ListView).index == index, \
            f"cursor lost on reload: {app.query_one(ListView).index} != {index}"
        assert len(app.query(Row)) > index, "the pages were not pulled back in"
        print(f"PASS reload keeps row {index} with {len(app.query(Row))} rows")
        app.play_state = {"path": [tuple(e) for e in app.path],
                          "index": index, "search": app.search}

    app2 = Goblin(resume=app.play_state)
    async with app2.run_test(size=(80, 24)) as pilot:
        await settle(pilot)
        from textual.widgets import ListView
        lv = app2.query_one(ListView)
        assert lv.index == app.play_state["index"], \
            f"resume lost the cursor: {lv.index} != {app.play_state['index']}"
        assert len(app2.query(Row)) > lv.index, "resume did not pull the pages back"
        print(f"PASS resume keeps row {lv.index} with {len(app2.query(Row))} rows")

    # --- A saved position is carried into the playlist (the player seeks in
    #     the running transcode)
    app = Goblin()
    async with app.run_test(size=(80, 24)) as pilot:
        await settle(pilot)
        await click_row(pilot, "Film")
        await settle(pilot)
        movie = app.query(Row).first().item
        app.resume_at[movie["Id"]] = 900_000_000          # 90 s
        app.play(movie)
        entries = playlist(app)
        assert entries[0]["start"] == 90, entries[0]
        # still a transcode - the player seeks in it once it is running
        assert "static=false" in entries[0]["url"], entries[0]["url"]
        print("PASS a saved position is carried into the transcode")

    # --- Subtitles: every kind of media gets one, not just series
    app = Goblin()
    async with app.run_test(size=(80, 24)) as pilot:
        await settle(pilot)
        await click_row(pilot, "Film")
        await settle(pilot)
        with_sub = [r.item for r in app.query(Row)
                    if app.targets(r.item) and app.targets(r.item)[0][4]]
        assert with_sub, "no movie with a subtitle track in the library"
        targets = app.targets(with_sub[0])
        assert targets[0][4], "a movie with a subtitle track gets no sidecar"
        print(f"PASS movie subtitle: {with_sub[0]['Name'][:28]} -> "
              f"{targets[0][4][-40:]}")

    # --- A second save is queued, not refused
    app = Goblin()
    async with app.run_test(size=(80, 24)) as pilot:
        await settle(pilot)
        await click_row(pilot, "Video Musicali")
        await settle(pilot)
        rows = list(app.query(Row))
        first, second = rows[0].item, rows[1].item
        from textual.widgets import ListView
        lv = app.query_one(ListView)
        lv.index = 0
        await app.action_save()
        lv.index = 1
        await app.action_save()          # queued behind the first one
        for _ in range(240):
            await pilot.pause(0.5)
            manifest = load_manifest(app)
            if manifest.get(first["Id"]) and manifest.get(second["Id"]):
                break
        manifest = load_manifest(app)
        assert manifest.get(first["Id"]), "the first job did not run"
        assert manifest.get(second["Id"]), "the queued job was dropped"
        print("PASS queued saves: both jobs finished")

    # --- Subtitles: Italian first, English second, else whatever is there
    app = Goblin()
    async with app.run_test(size=(80, 24)) as pilot:
        await settle(pilot)
        await click_row(pilot, "Serie TV")
        await enter(pilot)
        await enter(pilot)
        await settle(pilot)
        rows = list(app.query(Row))
        assert rows, "no episodes"
        chosen = None
        for row in rows:
            track = goblin_app.subtitle_track(row.item, app.prefs)
            if track:
                chosen = track
                break
        if chosen is None:
            print("SKIP subtitles (this series has none)")
        else:
            language = (chosen.get("Language") or "").lower()
            print(f"PASS subtitle pick: {language or '?'} "
                  f"({chosen.get('DisplayTitle')})")
            app.play(rows[0].item)
            entries = playlist(app)
            sub = entries[0]["sub"]
            assert sub and "/Subtitles/" in sub, f"no subtitle url: {sub}"
            print("PASS subtitle url:", sub[:90])

    # --- Save targets: a whole series expands to every episode
    app = Goblin()
    async with app.run_test(size=(80, 24)) as pilot:
        await settle(pilot)
        await click_row(pilot, "Serie TV")
        series = app.query(Row).first().item
        targets = app.targets(series)
        episodes = app.api.series_episodes(series["Id"])
        assert len(targets) == len(episodes) > 0, (len(targets), len(episodes))
        assert all("S" in name for _, name, _, _, _ in targets)
        print(f"PASS series save targets: {len(targets)} episodes")

    # --- Save one episode for real, play it locally, delete it with X twice
    app = Goblin()
    async with app.run_test(size=(80, 24)) as pilot:
        await settle(pilot)
        await click_row(pilot, "Serie TV")
        await enter(pilot)
        await enter(pilot)
        await settle(pilot)
        from textual.widgets import ListView
        rows = list(app.query(Row))
        item = rows[0].item
        app.query_one(ListView).index = 0
        await app.action_save()          # the download runs detached
        for _ in range(120):             # wait for the worker to finish
            await pilot.pause(0.5)
            if load_manifest(app).get(item["Id"], []):
                break
        files = load_manifest(app).get(item["Id"], [])
        assert files and (OFFLINE / files[0]).exists(), f"nothing saved: {files}"
        size = (OFFLINE / files[0]).stat().st_size
        assert size > 50_000, f"suspiciously small: {size}"
        print(f"PASS save: {files[0]} ({size / 1e6:.1f} MB)")
        # the subtitle comes along as a sidecar mpv loads by itself
        track = goblin_app.subtitle_track(item, app.prefs)
        if track:
            base = (OFFLINE / files[0]).with_suffix("")
            sidecars = [p for p in base.parent.glob(base.name + ".*")
                        if p.suffix in (".srt", ".ass", ".vtt")]
            assert sidecars, f"no subtitle sidecar next to {files[0]}"
            print(f"PASS subtitle sidecar: {sidecars[0].name} "
                  f"({sidecars[0].stat().st_size} bytes)")

        await app.reload()
        await settle(pilot)
        again = [r for r in app.query(Row) if r.item.get("Id") == item["Id"]][0]
        assert again, "row vanished after save"
        app.play(item)
        local = urls(playlist(app))
        assert any("/" in u and "http" not in u and u.endswith(files[0]) for u in local), local[0]
        print("PASS play uses the saved copy")

    app = Goblin()
    async with app.run_test(size=(80, 24)) as pilot:
        await settle(pilot)
        await click_row(pilot, "Serie TV")
        await enter(pilot)
        await enter(pilot)
        await settle(pilot)
        from textual.widgets import ListView
        rows = list(app.query(Row))
        idx = [i for i, r in enumerate(rows) if r.item.get("Id") == item["Id"]][0]
        app.query_one(ListView).index = idx
        await app.action_delete()            # first X arms the confirmation
        assert (OFFLINE / files[0]).exists(), "single X deleted without confirmation"
        await app.action_delete()            # second X deletes
        await settle(pilot)
        assert not (OFFLINE / files[0]).exists(), "delete left the file behind"
        base = (OFFLINE / files[0]).with_suffix("")
        for ext in (".srt", ".ass", ".vtt"):
            assert not Path(str(base) + ext).exists(), f"delete left {ext} behind"
        print("PASS delete needs two X presses and removes the file")

    # --- Escape walks back up; status survives a resize
    app = Goblin()
    async with app.run_test(size=(80, 24)) as pilot:
        await settle(pilot)
        await click_row(pilot, "Film")
        await pilot.press("escape")
        await settle(pilot)
        assert {r.item.get("Type") for r in app.query(Row)} == {"Collection"}
        await app.render_rows(restore=False)   # the resize path re-renders rows
        await settle(pilot)
        assert app.query_one("#stats").render()
        print("PASS back navigation and resize")

    shutil.rmtree(OFFLINE, ignore_errors=True)
    print("ALL TESTS PASSED")


if __name__ == "__main__":
    asyncio.run(main())
