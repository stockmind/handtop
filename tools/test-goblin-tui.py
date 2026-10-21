#!/usr/bin/env python3
"""Headless end-to-end test for the goblin TUI (overlay/usr/local/bin/goblin).

Drives the real app with Textual's pilot against a live Jellyfin server and
asserts the full navigation path works: libraries -> Film (movies) -> Movie
exit URL, Serie TV -> Season -> Episode exit URL, MusicVideo library ->
MusicVideo exit URL, plus Escape-back consistency.

Usage (from anywhere; needs textual in the interpreter):
    JELLYFIN_URL=http://192.168.1.60:8096 JELLYFIN_KEY=<token> \
        python3 tools/test-goblin-tui.py

Exits non-zero with the failing state on any break.
"""
import asyncio
import os
import sys
import urllib.request
from pathlib import Path

HERE = os.path.dirname(os.path.abspath(__file__))
APP_PATH = os.path.join(HERE, "..", "overlay", "usr", "local", "bin", "goblin")

os.environ.setdefault("JELLYFIN_URL", "http://192.168.1.60:8096")
os.environ.setdefault("JELLYFIN_KEY", "a35b1923c3c5495d91edcf067ad96a66")
# offline copies for the test go here, not into ~ (goblin reads env at import)
os.environ.setdefault("GOBLIN_OFFLINE_DIR", "/tmp/opencode/goblin-offline")

sys.path.insert(0, os.path.dirname(APP_PATH))
import importlib.util
spec = importlib.util.spec_from_loader("goblin_app", loader=None)
src = open(APP_PATH).read().replace('if __name__ == "__main__":', 'if False:')
goblin_app = compile(src, APP_PATH, "exec")
ns = {"__name__": "goblin_app"}
exec(goblin_app, ns)
GoblinApp = ns["GoblinApp"]
load_manifest_fn = ns["load_manifest"]


def api(path):
    url = f"{os.environ['JELLYFIN_URL']}{path}"
    req = urllib.request.Request(url, headers={
        "Authorization": f'MediaBrowser Token="{os.environ["JELLYFIN_KEY"]}"'})
    import json
    with urllib.request.urlopen(req, timeout=8) as r:
        return json.load(r)




async def click_by_name(pilot, want_name):
    # Click the ListItem: ListItem relays child clicks as _ChildClicked ->
    # ListView.Selected, which is what the app handles. Rows are Labels now.
    target = None
    for item in pilot.app.query("MediaItem"):
        if want_name in item.media_name:
            target = item
            break
    assert target is not None, f"no item matching {want_name!r}: " + repr(
        [m.media_name for m in pilot.app.query("MediaItem")])
    await pilot.click(target)
    await pilot.pause()
    await pilot.pause()
    return target


async def press_enter(pilot):
    """Enter must reach the ListView (search box may hold focus otherwise)."""
    from textual.widgets import ListView
    lv = pilot.app.query_one(ListView)
    lv.focus()
    if lv.index is None:      # a fresh list has no cursor until moved; put one on row 0
        lv.index = 0
    await pilot.press("enter")
    await pilot.pause()


def expect_pl(app, must_contain=None, shuffle=None):
    """Assert the exit value is a playlist tuple and return its urls."""
    rv = app.return_value
    assert isinstance(rv, tuple) and rv and rv[0] == "PL", f"not a playlist exit: {rv!r}"
    _, urls, shuf = rv
    assert urls, "empty playlist"
    if shuffle is not None:
        assert shuf is shuffle, f"shuffle flag {shuf}, expected {shuffle}"
    if must_contain is not None:
        assert any(must_contain in u for u in urls), f"{must_contain} not in {[u[:40] for u in urls]}"
    return urls


async def main():
    app = GoblinApp(mode="play")
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        await pilot.pause()

        # --- libraries listed
        names = [m.media_name for m in pilot.app.query("MediaItem")]
        assert len(names) >= 3, f"expected >=3 libraries, got {names}"
        crumb = pilot.app.query_one("#breadcrumb").render()
        assert "saved" in str(crumb) and "free" in str(crumb), f"Home lacks space line: {crumb!r}"
        print("PASS libraries:", [n.strip()[:24] for n in names])

        # --- Movies library -> Enter on first Movie exits with ordered playlist from cursor
        await click_by_name(pilot, "Film")
        kinds = [m.item_type for m in pilot.app.query("MediaItem")]
        assert kinds and set(kinds) == {"Movie"}, f"Film library listed {set(kinds)}"
        first = pilot.app.query("MediaItem").first()
        movie_id = first.item_id
        n_movies = len(list(pilot.app.query("MediaItem")))
        await press_enter(pilot)
        assert app._exit is True, "app did not exit on Movie select"
        urls = expect_pl(app, must_contain=f"/Videos/{movie_id}/stream", shuffle=False)
        assert len(urls) == n_movies, f"playlist {len(urls)} != visible {n_movies}"
        assert movie_id in urls[0], "ordered playlist does not start at the cursor"
        print(f"PASS movie ordered playlist ({len(urls)} files), starts at cursor")

    # --- Resume: relaunching with play_state must reopen the same folder/cursor
    assert app.play_state and app.play_state["stack"], "no nav state captured on play"
    app2 = GoblinApp(mode="play", resume=app.play_state)
    async with app2.run_test(size=(80, 24)) as pilot:
        await pilot.pause(); await pilot.pause()
        kinds = {m.item_type for m in app2.query("MediaItem")}
        assert kinds == {"Movie"}, f"resume landed on {kinds}, expected Movie"
        from textual.widgets import ListView as _LVr
        lv2 = app2.query_one(_LVr)
        assert lv2.index == app.play_state["index"], \
            f"resume cursor {lv2.index} != saved {app.play_state['index']}"
        crumb = str(app2.query_one("#breadcrumb").render())
        assert "Film" in crumb, f"resume breadcrumb wrong: {crumb[:60]}"
        print("PASS resume reopens the played folder with cursor restored")

    # --- TV path (fresh app each leg because selecting exits)
    app = GoblinApp(mode="play")
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause(); await pilot.pause()
        await click_by_name(pilot, "Serie TV")
        ser = pilot.app.query("MediaItem").first()
        assert ser.item_type == "Series", ser.item_type
        await press_enter(pilot); await pilot.pause()
        sea = pilot.app.query("MediaItem").first()
        assert sea.item_type == "Season", sea.item_type
        await press_enter(pilot); await pilot.pause()
        ep = pilot.app.query("MediaItem").first()
        assert ep.item_type == "Episode", ep.item_type
        await press_enter(pilot)
        assert app._exit is True, "episode select did not exit"
        urls = expect_pl(app, shuffle=False)
        print("PASS episode ordered playlist:", len(urls), "episodes")

    # --- Music library (flat track list -> playlist); skipped if server has none
    app = GoblinApp(mode="play")
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause(); await pilot.pause()
        names = [m.media_name for m in pilot.app.query("MediaItem")]
        if "Music" not in names:
            print("SKIP music library (not on this server)")
        else:
            target = [m for m in pilot.app.query("MediaItem") if m.media_name == "Music"][0]
            from textual.widgets import ListView as _LVm
            pilot.app.query_one(_LVm).index = list(pilot.app.query("MediaItem")).index(target)
            await press_enter(pilot); await pilot.pause()
            kinds = {m.item_type for m in pilot.app.query("MediaItem")}
            assert kinds == {"Audio"}, f"Music library listed {kinds}"
            await press_enter(pilot)
            urls = expect_pl(app, shuffle=False)
            assert all("/Videos/" in u for u in urls), "audio stream url wrong shape"
            print(f"PASS music: {len(urls)} tracks, Enter streams them")

    # --- Music video path + search filter + shuffle
    app = GoblinApp(mode="play")
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause(); await pilot.pause()
        await click_by_name(pilot, "Video Musicali")
        mv = pilot.app.query("MediaItem").first()
        assert mv.item_type == "MusicVideo", mv.item_type
        total = len(list(pilot.app.query("MediaItem")))
        # filter by text: server-side SearchTerm, so even item 400 of 533 is found
        from textual.widgets import Input as _In
        box = pilot.app.query_one("#search-box", _In)
        box.focus(); box.value = "youngblood"
        vis = []
        for _ in range(25):             # 0.35 s debounce + round-trip; slow devices need slack
            await pilot.pause(0.2)
            vis = [m for m in pilot.app.query("MediaItem") if m.display]
            if vis and all("youngblood" in m.media_name.lower() for m in vis):
                break
        assert vis and all("youngblood" in m.media_name.lower() for m in vis), \
            f"filter left {[m.media_name[:20] for m in vis]}"
        await press_enter(pilot)
        assert app._exit is True, "music-video select did not exit"
        urls = expect_pl(app, shuffle=False)
        assert len(urls) == len(vis) < total, f"filtered playlist {len(urls)} vs visible {len(vis)} of {total}"
        print(f"PASS filtered playlist: {len(urls)} of {total} match 'youngblood'")
    # shuffle flag
    app = GoblinApp(mode="play")
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause(); await pilot.pause()
        await click_by_name(pilot, "Video Musicali")
        await pilot.app.action_shuffle_play()
        urls = expect_pl(app, shuffle=True)
        print(f"PASS shuffle playlist ({len(urls)} files)")

    # --- Load-more sentinel in the overflowing library (533 music videos)
    app = GoblinApp(mode="play")
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause(); await pilot.pause()
        await click_by_name(pilot, "Video Musicali")
        lm = pilot.app.query("LoadMoreItem")
        assert len(lm) == 1, f"sentinel missing in 533-item library ({len(lm)})"
        n_before = len(list(pilot.app.query("MediaItem")))
        await pilot.app._load_more()
        await pilot.pause()
        n_after = len(list(pilot.app.query("MediaItem")))
        assert n_after > n_before, f"load-more appended nothing ({n_before}->{n_after})"
        assert len(pilot.app.query("LoadMoreItem")) == 1, "sentinel gone after page 2"
        print(f"PASS load-more: {n_before} -> {n_after} items, sentinel updated")
        # keyboard scrolling: arrows must move the cursor AND keep it visible
        from textual.widgets import ListView as _LVs
        lv = pilot.app.query_one(_LVs)
        for _ in range(30):
            await pilot.press("down")
        await pilot.pause()
        assert lv.index >= 29, f"arrows did not move the cursor (index={lv.index})"
        assert lv.scroll_y > 0, "ListView did not scroll; rows below the screen are unreachable"
        print(f"PASS keyboard scroll: index={lv.index}, scroll_y={lv.scroll_y}")

    # --- Escape-back integrity: Home -> lib -> escape must land on libraries, not re-descend
    app = GoblinApp(mode="play")
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause(); await pilot.pause()
        await click_by_name(pilot, "Film")
        await pilot.pause(); await pilot.pause()
        await pilot.press("escape"); await pilot.pause(); await pilot.pause()
        labels = [m.media_name for m in pilot.app.query("MediaItem")]
        kinds = [m.item_type for m in pilot.app.query("MediaItem")]
        assert set(kinds) == {"Collection"}, f"escape from library left {set(kinds)}: {labels[:4]}"
        print("PASS escape returns to libraries")

    # --- Download + remove round-trip (small music video, direct copy)
    import shutil as _sh
    off = Path(os.environ.get("GOBLIN_OFFLINE_DIR", str(Path.home() / "Offline")))
    if off.exists():
        _sh.rmtree(off)
    app = GoblinApp(mode="play")
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause(); await pilot.pause()
        await click_by_name(pilot, "Video Musicali")
        items = list(pilot.app.query("MediaItem"))
        # smallest file: FileSize is absent on multi-source items, so ask HEAD
        import urllib.request as _uq
        def _size(m):
            try:
                r = _uq.Request(f"{app.jellyfin_url}/Items/{m.item_id}/Download",
                                headers={"Authorization": f'MediaBrowser Token="{app.api_key}"',
                                         "Range": "bytes=0-0"})
                with _uq.urlopen(r, timeout=8) as resp:
                    return int(resp.headers.get("Content-Range", "/0").rsplit("/", 1)[1])
            except Exception:
                return m.file_size or 9e15
        mv = min(items, key=_size)              # ~58 MB music video -> fast test
        from textual.widgets import ListView as _LV
        pilot.app.query_one(_LV).index = items.index(mv)    # cursor, not activation
        await pilot.app.action_download_item()               # the s-button action
        await pilot.pause()
        stored = load_manifest_fn().get(mv.item_id, [])
        assert stored and (off / stored[0]).exists(), f"download left no file: {stored}"
        size = (off / stored[0]).stat().st_size
        assert size > 100_000, f"suspiciously small download: {size} bytes"
        print(f"PASS download: {stored[0]} ({size/1e6:.1f} MB)")
        # re-list must show the ✓ marker
        again = [m for m in pilot.app.query("MediaItem") if m.item_id == mv.item_id][0]
        assert again.offline is True, "offline flag not set after download"
        # play now resolves to the local file (item may be off-screen at 24 rows,
        # so drive _play_from directly instead of a pixel click)
        from textual.widgets import ListView as _LV2
        await pilot.app._play_from(again)
        urls = expect_pl(app)
        assert any(u.endswith(stored[0]) and "192.168" not in u for u in urls), \
            f"play did not use local copy: {urls[0][:60]}"
        print("PASS play uses local copy:", urls[0][:60], "...")
    # remove (fresh app, same manifest)
    app = GoblinApp(mode="play")
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause(); await pilot.pause()
        await click_by_name(pilot, "Video Musicali")
        target = [m for m in pilot.app.query("MediaItem") if m.item_id == mv.item_id][0]
        assert target.offline is True, "offline marker missing on fresh start"
        pilot.app.query_one(_LV).index = list(pilot.app.query("MediaItem")).index(target)
        pilot.app.action_remove_item()
        await pilot.pause()
        assert not (off / stored[0]).exists(), "remove left the file behind"
        assert mv.item_id not in load_manifest_fn(), "remove left the manifest entry"
        print("PASS remove deletes local copy, server untouched")
    _sh.rmtree(off, ignore_errors=True)

    print("ALL TESTS PASSED")


if __name__ == "__main__":
    os.environ.setdefault("JELLYFIN_URL", "http://192.168.1.60:8096")
    os.environ.setdefault("JELLYFIN_KEY", "a35b1923c3c5495d91edcf067ad96a66")
    asyncio.run(main())
