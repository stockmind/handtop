#!/usr/bin/env python3
"""Regression tests for the readaloud player.

    python3 -m unittest discover -s tests -v

Pure-python tests always run. The browser test runs only where chromium exists
(it is the one that catches JS wiring regressions, so keep it in the loop on a
machine that has it, e.g. the handheld).
"""
import importlib.machinery
import importlib.util
import json
import pathlib
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest import mock
import urllib.request
import zipfile

ROOT = pathlib.Path(__file__).resolve().parents[1]
CANDIDATES = [ROOT / 'overlay/usr/local/bin/readaloud',
              ROOT / 'readaloud.py',
              ROOT.parent / 'readaloud/readaloud.py']
SRC = next((p for p in CANDIDATES if p.exists()), None)
if SRC is None:
    sys.exit('cannot find the readaloud script next to %s' % ROOT)

loader = importlib.machinery.SourceFileLoader('readaloud', str(SRC))
spec = importlib.util.spec_from_loader('readaloud', loader)
ra = importlib.util.module_from_spec(spec)
loader.exec_module(ra)

OPF = """<?xml version="1.0"?>
<package xmlns="http://www.idpf.org/2007/opf" version="3.0" unique-identifier="id">
 <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
  <dc:title>Test Book: The Sequel</dc:title>
  <dc:creator>A. Author</dc:creator>
  <dc:creator>A. Author</dc:creator>
  <dc:creator>B. Translator</dc:creator>
  <meta property="belongs-to-collection">Test Saga</meta>
 </metadata>
 <manifest>
  <item id="nav" href="OEBPS/nav.xhtml" media-type="application/xhtml+xml" properties="nav"/>
  <item id="ch1" href="OEBPS/ch1.xhtml" media-type="application/xhtml+xml"
        media-overlay="ch1-overlay" properties="scripted"/>
  <item id="ch1-overlay" href="OEBPS/ch1.smil" media-type="application/smil+xml"/>
  <item id="cover" href="OEBPS/cover.png" media-type="image/png" properties="cover-image"/>
 </manifest>
 <spine><itemref idref="ch1"/></spine>
</package>"""

NAV = """<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops">
<body><nav epub:type="toc"><ol><li><a href="ch1.xhtml">Chapter One</a></li></ol></nav></body></html>"""

XHTML = """<html xmlns="http://www.w3.org/1999/xhtml"><head><title>Chapter One</title></head>
<body><p id="s1">Hello brave new world.</p><p id="s2">Second sentence here.</p></body></html>"""

SMIL = """<smil xmlns="http://www.w3.org/ns/SMIL" version="3.0"><body>
<seq>
 <par><text src="../OEBPS/ch1.xhtml#s1"/><audio src="../Audio/a.mp4" clipBegin="0s" clipEnd="2.5s"/></par>
 <par><text src="../OEBPS/ch1.xhtml#s2"/><audio src="../Audio/a.mp4" clipBegin="2.5s" clipEnd="4s"/></par>
</seq></body></smil>"""


def make_epub(folder, narrated=True, name='Test Book.epub'):
    path = pathlib.Path(folder) / name
    opf = OPF if narrated else OPF.replace(' media-overlay="ch1-overlay"', '')
    with zipfile.ZipFile(path, 'w') as z:
        z.writestr('mimetype', 'application/epub+zip', compress_type=zipfile.ZIP_STORED)
        z.writestr('META-INF/container.xml',
                   '<?xml version="1.0"?><container xmlns="urn:oasis:names:tc:opendocument:xmlns:container" '
                   'version="1.0"><rootfiles><rootfile full-path="content.opf" '
                   'media-type="application/oebps-package+xml"/></rootfiles></container>')
        z.writestr('content.opf', opf)
        z.writestr('OEBPS/nav.xhtml', NAV)
        z.writestr('OEBPS/ch1.xhtml', XHTML)
        z.writestr('OEBPS/cover.png', b'\x89PNG\r\n\x1a\n' + b'0' * 32)
        if narrated:
            z.writestr('OEBPS/ch1.smil', SMIL)
            z.writestr('Audio/a.mp4', b'\x00' * 4096)
    return path


class ParseTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp)
        self.cache = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.cache)
        ra.CACHE_DIR = self.cache
        ra._CACHE.clear()
        ra._INFO.clear()

    def test_clock(self):
        self.assertAlmostEqual(ra.parse_clock('1.5s'), 1.5)
        self.assertAlmostEqual(ra.parse_clock('100ms'), 0.1)
        self.assertAlmostEqual(ra.parse_clock('00:01:02.500'), 62.5)
        self.assertAlmostEqual(ra.parse_clock(''), 0.0)

    def test_resolve(self):
        self.assertEqual(ra.resolve('../OEBPS/ch1.xhtml', 'OEBPS/ch1.smil'), 'OEBPS/ch1.xhtml')
        self.assertEqual(ra.resolve('a/../b.webp', 'x/y.opf'), 'x/b.webp')

    def test_narrated_book(self):
        book = make_epub(self.tmp)
        data = ra.load_book(book)
        self.assertTrue(data['narration'])
        self.assertEqual(data['title'], 'Test Book')
        self.assertEqual(data['subtitle'], 'The Sequel')
        self.assertEqual(data['author'], 'A. Author +1')      # deduped, counted
        self.assertEqual(len(data['sections']), 1)
        sec = data['sections'][0]
        self.assertEqual(sec['label'], 'Chapter One')         # from the nav, not <title>
        self.assertEqual([p['frag'] for p in sec['pars']], ['s1', 's2'])
        self.assertAlmostEqual(sec['pars'][1]['begin'], 2.5)

    def test_plain_epub_falls_back_to_spine(self):
        book = make_epub(self.tmp, narrated=False, name='Plain.epub')
        data = ra.load_book(book)
        self.assertFalse(data['narration'])
        self.assertEqual([s['href'] for s in data['sections']], ['OEBPS/ch1.xhtml'])
        self.assertEqual(data['sections'][0]['pars'], [])

    def test_word_sidecar(self):
        book = make_epub(self.tmp)
        side = book.with_suffix('').with_suffix('')
        (pathlib.Path(str(side) + '.words.json')).write_text(
            json.dumps({'OEBPS/ch1.xhtml#s1': [0.0, 0.4, 0.9, 1.4]}))
        data = ra.load_book(book)
        self.assertEqual(data['sections'][0]['pars'][0]['times'], [0.0, 0.4, 0.9, 1.4])

    def test_section_labels_fall_back(self):
        book = make_epub(self.tmp, narrated=False, name='Nolabel.epub')
        with zipfile.ZipFile(book, 'a') as z:
            z.writestr('OEBPS/nav.xhtml', '<html><body><nav><ol></ol></nav></body></html>')
        ra._CACHE.clear()
        ra._INFO.clear()
        data = ra.load_book(book)
        self.assertEqual(data['sections'][0]['label'], '')


class ServerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp)
        self.cache = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.cache)
        ra.CACHE_DIR = self.cache
        ra._CACHE.clear()
        ra._INFO.clear()
        # keep a real ~/.config/readaloud/config.json out of the tests
        patcher = mock.patch.object(ra, 'st_config', lambda: {})
        patcher.start()
        self.addCleanup(patcher.stop)
        make_epub(self.tmp)
        self.srv = ra.ThreadingHTTPServer(('127.0.0.1', 0), ra.Handler)
        self.srv.root = self.tmp
        self.port = self.srv.server_address[1]
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()
        self.addCleanup(self.srv.server_close)
        self.addCleanup(self.srv.shutdown)

    def get(self, path, headers=None):
        req = urllib.request.Request('http://127.0.0.1:%d%s' % (self.port, path),
                                     headers=headers or {})
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status, r.read(), dict(r.headers)

    def test_library_lists_metadata(self):
        _, body, _ = self.get('/api/books')
        books = json.loads(body)
        self.assertEqual(len(books), 1)
        self.assertEqual(books[0]['title'], 'Test Book')
        self.assertTrue(books[0]['readaloud'])
        self.assertTrue(books[0]['cover'])

    def test_book_json_is_gzipped_and_cached(self):
        _, body, hdrs = self.get('/api/book/Test%20Book.epub', {'Accept-Encoding': 'gzip'})
        self.assertEqual(hdrs.get('Content-Encoding'), 'gzip')
        self.assertIn(b'narration', __import__('gzip').decompress(body))

    def test_cover_bytes(self):
        status, body, hdrs = self.get('/cover/Test%20Book.epub')
        self.assertEqual(status, 200)
        self.assertTrue(body.startswith(b'\x89PNG'))
        self.assertTrue(hdrs['Content-Type'].startswith('image/'))

    def test_range_request(self):
        status, body, hdrs = self.get('/book/Test%20Book.epub/Audio/a.mp4',
                                       {'Range': 'bytes=10-19'})
        self.assertEqual(status, 206)
        self.assertEqual(len(body), 10)
        self.assertEqual(hdrs['Content-Range'], 'bytes 10-19/4096')

    def test_storyteller_unconfigured(self):
        _, body, _ = self.get('/api/storyteller')
        data = json.loads(body)
        self.assertFalse(data['configured'])
        self.assertEqual(data['books'], [])

    def test_download_refused_without_config(self):
        req = urllib.request.Request('http://127.0.0.1:%d/api/download' % self.port,
                                     data=b'{"uuid":"x"}', method='POST')
        try:
            urllib.request.urlopen(req, timeout=10)
            self.fail('should refuse')
        except urllib.error.HTTPError as e:
            self.assertEqual(e.code, 400)

    def test_unknown_path(self):
        try:
            self.get('/nope')
            self.fail('should 404')
        except urllib.error.HTTPError as e:
            self.assertEqual(e.code, 404)


CHROMIUM = shutil.which('chromium') or shutil.which('chromium-browser')


@unittest.skipUnless(CHROMIUM, 'chromium not installed')
class BrowserTests(unittest.TestCase):
    """Loads the real player headless: catches JS wiring regressions."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp)
        self.cache = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.cache)
        ra.CACHE_DIR = self.cache
        ra._CACHE.clear()
        ra._INFO.clear()
        make_epub(self.tmp)
        self.srv = ra.ThreadingHTTPServer(('127.0.0.1', 0), ra.Handler)
        self.srv.root = self.tmp
        self.port = self.srv.server_address[1]
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()
        self.addCleanup(self.srv.server_close)
        self.addCleanup(self.srv.shutdown)

    def load(self, query):
        url = 'http://127.0.0.1:%d/%s' % (self.port, query)
        out = subprocess.run(
            [CHROMIUM, '--headless=new', '--disable-gpu', '--no-sandbox',
             '--user-data-dir=%s/profile' % self.tmp, '--virtual-time-budget=6000',
             '--enable-logging=stderr', '--v=0', '--dump-dom', url],
            capture_output=True, text=True, timeout=90)
        return out.stdout + out.stderr

    def test_player_loads_without_js_errors(self):
        log = self.load('play?book=Test%20Book.epub&check=1')
        self.assertNotIn('Uncaught', log)
        self.assertIn('<title>CHECK OK toc</title>', log)   # parTimes + picker click

    def test_library_renders(self):
        log = self.load('')
        self.assertNotIn('Uncaught', log)
        self.assertIn('Test Book', log)

    def ui_results(self, log):
        import re
        m = re.search(r'<title>UITESTS (\d+)/(\d+)(.*?)</title>', log, re.S)
        self.assertIsNotNone(m, 'UI tests did not finish')
        return int(m.group(1)), int(m.group(2)), m.group(3)

    def test_player_ui_clicks_and_pad(self):
        log = self.load('play?book=Test%20Book.epub&check=ui')
        self.assertNotIn('Uncaught', log)
        passed, total, rest = self.ui_results(log)
        self.assertEqual(passed, total, rest)
        self.assertGreaterEqual(total, 10)

    def test_library_ui_clicks_and_pad(self):
        log = self.load('?check=ui')
        self.assertNotIn('Uncaught', log)
        passed, total, rest = self.ui_results(log)
        self.assertEqual(passed, total, rest)
        self.assertGreaterEqual(total, 5)


if __name__ == '__main__':
    unittest.main()
