"""A headless Chromium driven through the DevTools protocol over a pipe, for the export of the composition engine.

No extra package: the browser reads commands on fd 3 and writes replies on fd 4, each message ending in NUL.
The browser comes from MYCUT_CHROMIUM, or from the Playwright cache the studio's tests already install, or from the
system. Requests outside the loopback go to a closed proxy, so a recording never reaches the network (ADR 0019).
"""
import fcntl
import glob
import json
import os
import re
import shutil
import subprocess
import tempfile
import threading
from pathlib import Path


class BrowserError(RuntimeError):
    pass


def binary():
    chosen = os.environ.get('MYCUT_CHROMIUM')
    if chosen:
        return chosen
    cache = Path(os.environ.get('PLAYWRIGHT_BROWSERS_PATH') or Path.home() / '.cache/ms-playwright')
    # The newest revision, and the headless shell before the full browser of the same revision.
    found = sorted(glob.glob(str(cache / 'chromium-*/chrome-linux64/chrome')) +
                   glob.glob(str(cache / 'chromium_headless_shell-*/chrome-headless-shell-linux64/chrome-headless-shell')),
                   key=lambda p: (int(re.search(r'-(\d+)/chrome', p).group(1)), 'headless_shell' in p))
    if found:
        return found[-1]
    for name in ('chromium', 'chromium-browser', 'google-chrome'):
        if shutil.which(name):
            return shutil.which(name)
    raise BrowserError('Chromium não encontrado. Instale com "npx playwright install chromium-headless-shell" '
                       'ou informe MYCUT_CHROMIUM.')


class Browser:
    def __init__(self):
        self.profile = tempfile.mkdtemp(prefix='mycut-chromium-')
        to_browser, self.commands = os.pipe()
        self.replies, from_browser = os.pipe()

        def pipes():
            # The browser expects its end of the protocol exactly on fds 3 and 4; copies above 10 never clash with them.
            read, write = fcntl.fcntl(to_browser, fcntl.F_DUPFD, 10), fcntl.fcntl(from_browser, fcntl.F_DUPFD, 10)
            os.dup2(read, 3)
            os.dup2(write, 4)

        args = [binary(), '--headless', '--remote-debugging-pipe', f'--user-data-dir={self.profile}', '--no-first-run',
                '--no-default-browser-check', '--hide-scrollbars', '--mute-audio', '--disable-extensions',
                '--autoplay-policy=no-user-gesture-required', '--disable-background-timer-throttling',
                '--disable-renderer-backgrounding', '--proxy-server=http://127.0.0.1:9', 'about:blank']
        if os.environ.get('MYCUT_CHROMIUM_NO_SANDBOX'):
            args.insert(1, '--no-sandbox')
        # Only fds 3 and 4 are inheritable in the child: Python opens every other one with close-on-exec.
        self.process = subprocess.Popen(args, close_fds=False, preexec_fn=pipes, stdin=subprocess.DEVNULL,
                                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        os.close(to_browser)
        os.close(from_browser)
        self.next_id = 0
        self.lock = threading.Lock()
        self.waiting = {}
        threading.Thread(target=self.read, daemon=True, name='cdp').start()

    def read(self):
        pending = b''
        while True:
            try:
                chunk = os.read(self.replies, 1 << 20)
            except OSError:
                chunk = b''
            if not chunk:
                break
            pending += chunk
            *messages, pending = pending.split(b'\0')
            for raw in messages:
                message = json.loads(raw)
                slot = self.waiting.pop(message.get('id'), None)
                if slot:
                    slot[1] = message
                    slot[0].set()
        for event, _ in list(self.waiting.values()):
            event.set()

    def send(self, method, params=None, session=None, timeout=300):
        with self.lock:
            self.next_id += 1
            ident = self.next_id
            slot = self.waiting[ident] = [threading.Event(), None]
            message = {'id': ident, 'method': method, 'params': params or {}}
            if session:
                message['sessionId'] = session
            os.write(self.commands, json.dumps(message).encode() + b'\0')
        if not slot[0].wait(timeout):
            raise BrowserError(f'O Chromium não respondeu a {method}.')
        reply = slot[1]
        if reply is None:
            raise BrowserError('O Chromium encerrou durante a exportação.')
        if 'error' in reply:
            raise BrowserError(f'{method}: {reply["error"].get("message")}')
        return reply['result']

    def page(self, url, width, height):
        target = self.send('Target.createTarget', {'url': 'about:blank'})['targetId']
        session = self.send('Target.attachToTarget', {'targetId': target, 'flatten': True})['sessionId']
        page = Page(self, session)
        page.send('Emulation.setDeviceMetricsOverride', {'width': width, 'height': height, 'deviceScaleFactor': 1,
                                                         'mobile': False})
        page.send('Page.navigate', {'url': url})
        page.evaluate('new Promise(ok => { const wait = () => window.motor ? ok(true) : setTimeout(wait, 20); wait(); })')
        return page

    def close(self):
        try:
            os.close(self.commands)
        except OSError:
            pass
        try:
            self.process.terminate()
            self.process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            self.process.kill()
            self.process.wait()
        os.close(self.replies)
        shutil.rmtree(self.profile, ignore_errors=True)


class Page:
    def __init__(self, browser, session):
        self.browser, self.session = browser, session

    def send(self, method, params=None, timeout=300):
        return self.browser.send(method, params, self.session, timeout)

    def evaluate(self, expression, timeout=300):
        result = self.send('Runtime.evaluate', {'expression': expression, 'awaitPromise': True, 'returnByValue': True},
                           timeout)
        if 'exceptionDetails' in result:
            details = result['exceptionDetails']
            raise BrowserError(details.get('exception', {}).get('description') or details.get('text'))
        return result['result'].get('value')

    def call(self, function, *args, timeout=300):
        return self.evaluate(f'({function})(...{json.dumps(args, ensure_ascii=False)})', timeout)

    def capture(self, quality=92):
        import base64
        data = self.send('Page.captureScreenshot', {'format': 'jpeg', 'quality': quality, 'optimizeForSpeed': True})['data']
        return base64.b64decode(data)
