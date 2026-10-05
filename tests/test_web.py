import unittest,tempfile,threading
from http.server import HTTPServer
from urllib.request import urlopen,Request
from urllib.error import HTTPError
from unittest.mock import patch
from platform_intelligence.web import handler,render,LocalHTTPServer
from platform_intelligence.engine import Engine
from platform_intelligence.contracts import Source

class WebTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(); self.server=HTTPServer(('127.0.0.1',0),handler(self.temp.name,0,'testtoken'))
        self.port=self.server.server_address[1]; self.server.RequestHandlerClass=handler(self.temp.name,self.port,'testtoken')
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
    def tearDown(self): self.server.shutdown();self.server.server_close();self.thread.join();self.temp.cleanup()
    def test_page_nontechnical(self):
        with urlopen(f'http://127.0.0.1:{self.port}/') as r:
            text=r.read().decode();self.assertIn('平台健康',text);self.assertIn('今日 Action',text)
            self.assertNotIn('schema',text.lower());self.assertNotIn('json',text.lower())
            self.assertIn('检查 X 官方变化并生成简报',text);self.assertIn('/static/brief.js',text)
            self.assertIn('海内外自媒体平台情报',text)
            for platform in ('Facebook','Reddit','哔哩哔哩','Instagram'):self.assertIn(platform,text)
            self.assertIn("script-src 'self'",r.headers['Content-Security-Policy'])
            self.assertIn("connect-src 'none'",r.headers['Content-Security-Policy'])
            self.assertIn("frame-ancestors 'none'",r.headers['Content-Security-Policy'])

    def test_brief_view_escapes_content_and_exposes_copy_button(self):
        brief={'text':'<script>alert(1)</script>','actions':[],'changes':[],
               'checked_count':0,'change_count':0,'source_update_count':0,'unavailable_count':0}
        engine=Engine(self.temp.name)
        try:page=render(engine, 'testtoken', brief)
        finally:engine.store.close()
        self.assertIn('&lt;script&gt;alert(1)&lt;/script&gt;',page)
        self.assertNotIn('<script>alert(1)</script>',page)
        self.assertIn('复制简报',page)
        self.assertIn('readonly',page)

    def test_local_copy_script(self):
        with urlopen(f'http://127.0.0.1:{self.port}/static/brief.js') as r:
            script=r.read().decode()
            self.assertIn('navigator.clipboard.writeText',script)
            self.assertEqual(r.headers.get_content_type(),'text/javascript')

    def test_platform_brief_never_shows_x_actions(self):
        with urlopen(f'http://127.0.0.1:{self.port}/?platform=Facebook&brief=1') as r:
            page=r.read().decode()
            self.assertIn('Facebook · 当前平台',page)
            self.assertIn('Facebook 规则与算法简报',page)
            self.assertIn('brief-content',page)
            self.assertIn('action="/check"',page)
            self.assertNotIn('【X 平台规则',page)

    def test_unknown_platform_rejected(self):
        with self.assertRaises(HTTPError) as ctx:urlopen(f'http://127.0.0.1:{self.port}/?platform=Unknown')
        self.assertEqual(ctx.exception.code,400);ctx.exception.close()

    def test_check_selected_platform_cannot_fall_back_to_x(self):
        source=Source('youtube-policy','YouTube','POLICY','https://support.google.com/youtube/answer/9288567?hl=en','YouTube 社区准则')
        class FixtureMonitor:
            platform='YouTube'
            def sources(self):return [source]
            def fetch(self,_source):return b'Official YouTube fixture body','text/plain'
        request=Request(f'http://127.0.0.1:{self.port}/check',data=b'token=testtoken&platform=YouTube')
        with patch('platform_intelligence.web.get_adapter',return_value=FixtureMonitor()) as adapter:
            with urlopen(request) as r:
                page=r.read().decode();self.assertIn('platform=YouTube&brief=1',r.geturl())
                self.assertIn('【YouTube 平台规则',page);self.assertNotIn('【X 平台规则',page)
                self.assertIn('当前没有可公开引用的有效审核结论',page)
            adapter.assert_called_once_with('YouTube')
        engine=Engine(self.temp.name)
        try:self.assertEqual(engine.state()['runs'][-1]['platform'],'YouTube')
        finally:engine.store.close()

    def test_check_forces_monitor_and_opens_pending_change_brief(self):
        source=Source('fixture-algorithm','X','ALGORITHM','https://docs.x.com/algorithm','算法原文')
        engine=Engine(self.temp.name);engine.register(source);engine.capture(source.id,b'old official text');engine.store.close()
        class FixtureMonitor:
            platform='X'
            def sources(self):return [source]
            def fetch(self,_source):return b'new official text','text/plain'
        request=Request(f'http://127.0.0.1:{self.port}/check',data=b'token=testtoken')
        with patch('platform_intelligence.web.XAdapter',FixtureMonitor):
            with urlopen(request) as r:
                page=r.read().decode()
                self.assertTrue(r.geturl().endswith('/?brief=1'))
                self.assertIn('X 规则与算法简报',page)
                self.assertIn('正文变化待审核',page)
                self.assertIn('语义尚未审核',page)
                self.assertNotIn('新规则：new official text',page)
    def test_post_requires_token(self):
        with self.assertRaises(HTTPError) as ctx:
            urlopen(Request(f'http://127.0.0.1:{self.port}/check',data=b'token=wrong'))
        self.assertEqual(ctx.exception.code,403)
        ctx.exception.close()
    def test_host_fail_closed(self):
        with self.assertRaises(HTTPError) as ctx:
            urlopen(Request(f'http://127.0.0.1:{self.port}/',headers={'Host':'evil.test'}))
        self.assertEqual(ctx.exception.code,403)
        ctx.exception.close()
    def test_path_traversal(self):
        with self.assertRaises(HTTPError) as ctx: urlopen(f'http://127.0.0.1:{self.port}/evidence/../../secrets')
        self.assertEqual(ctx.exception.code,409)
        ctx.exception.close()
    def test_html_evidence_escaped(self):
        e=Engine(self.temp.name);h=e.store.blob(b'<script>alert(1)</script>');e.store.close()
        with urlopen(f'http://127.0.0.1:{self.port}/evidence/{h}') as r:
            text=r.read().decode();self.assertIn('&lt;script&gt;',text);self.assertNotIn('<script>',text)
    def test_no_duplicate_server(self):
        server=LocalHTTPServer(('127.0.0.1',0),handler(self.temp.name,0,'token'))
        try:
            with self.assertRaises(OSError):LocalHTTPServer(server.server_address,handler(self.temp.name,0,'token'))
        finally:server.server_close()

if __name__=='__main__':unittest.main()
