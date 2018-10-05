import unittest as ut
import io
from make_profiler.parser import *
import makefile_provider as mf

class ParserTests(ut.TestCase):

    def test_glue(self):
        ss = io.StringIO( \
r'''	gcc \
-o app.exe \
-c file.cpp''')
        s = next(ss)
        self.assertEqual(glue_multiline(ss, s), 'gcc -o app.exe -c file.cpp')

        ss = io.StringIO( \
r'''	gcc a.cpp; echo \\
echo b \\\\
echo c \\\
echo d''')
        s = next(ss)
        self.assertEqual(glue_multiline(ss, s), r'gcc a.cpp; echo \\')
        s = next(ss)
        self.assertEqual(glue_multiline(ss, s), r'echo b \\\\')
        s = next(ss)
        self.assertEqual(glue_multiline(ss, s), r'echo c \\ echo d')

    def test_comments(self):
        ss = io.StringIO(\
        r'''abc def # \
        zzz''')
        s = next(ss)
        # TODO: \ should be ignored since it is in comment
        self.assertNotEqual(glue_multiline(ss, s), 'abc def # \\')
        s = next(ss,'')
        self.assertNotEqual(glue_multiline(ss, s), 'zzz')

        ss = io.StringIO(\
        r'''abc def '#' \
        zzz''')
        s = next(ss)
        self.assertEqual(glue_multiline(ss, s), "abc def '#' zzz")

    tok = io.StringIO()
    def use(self, makestring):
        self.tok = tokenizer(io.StringIO(makestring))

    def skip(self, lines):
        for _ in range(lines):
            next(self.tok)

    def assertNext(self, type_, line):
        tp, ln = next(self.tok)
        self.assertEqual(tp, type_)
        self.assertEqual(ln, line)

    def test_tokenizer_easy(self):
        self.use(mf.easy())

        self.assertNext(Tokens.target,  'app.exe: file.o')
        self.assertNext(Tokens.command, 'gcc -o app.exe file.o')
        self.assertNext(Tokens.target,  'appd.exe: filed.o')
        self.assertNext(Tokens.command, 'GCC = gcc -g')
        self.assertNext(Tokens.command, '$(GCC) -o appd.exe filed.o')
        self.assertNext(Tokens.command, 'echo "built debug"')

    def test_tokenizer_medium(self):
        self.use(mf.medium())
        self.skip(6)
        self.assertNext(Tokens.expression, 'ifdef debug')
        self.assertNext(Tokens.target, 'build: appd.exe')
        self.assertNext(Tokens.expression, 'else')
        self.assertNext(Tokens.target, 'build: app.exe')
        self.assertNext(Tokens.expression, 'endif')

    def test_tokenizer_hard(self):
        self.use(mf.hard())
        self.skip(2)

        self.assertNext(Tokens.expression, 'export Y=2')
        self.assertNext(Tokens.expression, 'Z=3')
        self.assertNext(Tokens.target, 'app.exe: file.o')
        self.assertNext(Tokens.command, 'gcc -o app.exe file.o')

    def test_parse_easy(self):
        tok = io.StringIO(mf.easy())
        app, appd = parse(tok)
        _,app = app
        _,appd = appd

        self.assertEqual(app['target'], 'app.exe')
        self.assertEqual(appd['target'], 'appd.exe')

        self.assertEqual(app['deps'], [['file.o'], []])
        self.assertEqual(appd['deps'], [['filed.o'], []])

        self.assertEqual(app['body'], [('command', 'gcc -o app.exe file.o')])
        self.assertEqual(appd['body'], [('command', 'GCC = gcc -g'),
            ('command', '$(GCC) -o appd.exe filed.o'),
            ('command', 'echo "built debug"')])
