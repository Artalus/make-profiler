import collections
import re

from more_itertools import peekable


class Tokens:
    target = 'target'
    command = 'command'
    expression = 'expression'

def glue_multiline(it, line):
    lines = []
    strip_line = line.strip()
    while strip_line[-1] == '\\':
        lines.append(strip_line.rstrip('\\').strip())
        line_num, line = next(it)
        strip_line = line.strip()
    lines.append(strip_line.rstrip('\\').strip())
    return ' '.join(lines)

def tokenizer(fd):
    it = enumerate(fd)
    for line_num, line in it:
        strip_line = line.strip()

        # skip empty lines
        if not strip_line:
            continue

        # skip comments, don't skip docstrings
        if strip_line[0] == '#' and line[:2] != '##':
            continue

        if line[0] == '\t':
            yield (Tokens.command, glue_multiline(it, line))
        elif ':' in line and '=' not in line:
            yield (Tokens.target, glue_multiline(it, line))
        else:
            yield (Tokens.expression, line.strip(' ;\t\n'))


def parse(fd):
    ast = []
    it = peekable(tokenizer(fd))

    def parse_target(token):
        line = token[1]
        target, deps, order_deps, docstring = re.match(
            r'(.+): \s? ([^|#]+)? \s? [|]? \s? ([^##]+)? \s?  \s? ([#][#].+)?',
            line,
            re.X
        ).groups()
        body = parse_body()
        ast.append((
            token[0],
            {
                'target': target.strip(),
                'deps': [
                    sorted(deps.strip().split()) if deps else [],
                    sorted(order_deps.strip().split()) if order_deps else []
                ],
                'docs': docstring.strip().strip('#').strip() if docstring else target,
                'body': body
            })
        )

    def next_belongs_to_target():
        token, _ = it.peek()
        return token == Tokens.command

    def parse_body():
        body = []
        try:
            while next_belongs_to_target():
                body.append(next(it))
        except StopIteration:
            pass
        return body

    for token in it:
        if token[0] == Tokens.target:
            parse_target(token)
        else:
            # expression
            ast.append(token)

    return ast


def get_dependencies_influences(ast):
    dependencies = {}
    influences = collections.defaultdict(set)
    order_only = set()
    indirect_influences = collections.defaultdict(set)

    for item_t, item in ast:
        if item_t != Tokens.target:
            continue
        target = item['target']
        deps, order_deps = item['deps']

        if target in ('.PHONY',):
            continue

        dependencies[target] = [deps, order_deps]

        # influences
        influences[target]
        for k in deps:
            influences[k].add(target)
        for k in order_deps:
            influences[k]
        order_only.update(order_deps)

    def recurse_indirect_influences(original_target, recurse_target):
        indirect_influences[original_target].update(influences[recurse_target])
        for t in influences[recurse_target]:
            recurse_indirect_influences(original_target, t)

    for original_target, targets in influences.items():
        for t in targets:
            recurse_indirect_influences(original_target, t)

    return dependencies, influences, order_only, indirect_influences

if __name__ == '__main__':
    import unittest as ut
    import io

    class ParserTests(ut.TestCase):
        Makefile_easy = \
r'''app.exe: file.o
	gcc -o app.exe file.o
appd.exe: filed.o
	GCC = gcc -g
	$(GCC) -o appd.exe filed.o
	echo "built debug"'''
        Makefile_medium = Makefile_easy + \
r'''

ifdef debug
build: appd.exe
else
build: app.exe
endif'''
        Makefile_hard = \
r'''all: build

export X=1
export Y=2

Z=3

app.exe: file.o
	gcc -o \
    app.exe \
    file.o
appd.exe: file.o
	gcc -o app.exe file.o

file.o: file.cpp
	gcc -c file.cpp -o file.o

ifdef debug
ifeq ($(debug),1)
build: appd.exe
else
build: app.exe
endif
else
build: appd.exe app.exe
endif

clean:
	rm *.o
	rm *.exe
#.PHONY : build'''

        def test_glue(self):
            ss = enumerate(io.StringIO( \
r'''	gcc \
	-o app.exe \
	-c file.cpp'''))
            _,s = next(ss)
            self.assertEqual(glue_multiline(ss, s), 'gcc -o app.exe -c file.cpp')

            ss = enumerate(io.StringIO( \
r'''	gcc a.cpp; echo \\
	echo b \\\\
	echo c \\\
	echo d'''))
            _,s = next(ss)
            self.assertEqual(glue_multiline(ss, s), r'gcc a.cpp; echo \\')
            _,s = next(ss)
            self.assertEqual(glue_multiline(ss, s), r'echo b \\\\')
            _,s = next(ss)
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
            self.use(self.Makefile_easy)

            self.assertNext(Tokens.target,  'app.exe: file.o')
            self.assertNext(Tokens.command, 'gcc -o app.exe file.o')
            self.assertNext(Tokens.target,  'appd.exe: filed.o')
            self.assertNext(Tokens.command, 'GCC = gcc -g')
            self.assertNext(Tokens.command, '$(GCC) -o appd.exe filed.o')
            self.assertNext(Tokens.command, 'echo "built debug"')

        def test_tokenizer_medium(self):
            self.use(self.Makefile_medium)
            self.skip(6)
            self.assertNext(Tokens.expression, 'ifdef debug')
            self.assertNext(Tokens.target, 'build: appd.exe')
            self.assertNext(Tokens.expression, 'else')
            self.assertNext(Tokens.target, 'build: app.exe')
            self.assertNext(Tokens.expression, 'endif')

        def test_tokenizer_hard(self):
            self.use(self.Makefile_hard)
            self.skip(2)

            self.assertNext(Tokens.expression, 'export Y=2')
            self.assertNext(Tokens.expression, 'Z=3')
            self.assertNext(Tokens.target, 'app.exe: file.o')
            self.assertNext(Tokens.command, 'gcc -o app.exe file.o')

        def test_parse_easy(self):
            tok = io.StringIO(self.Makefile_easy)
            (_, app), (_, appd) = parse(tok)

            self.assertEqual(app['target'], 'app.exe')
            self.assertEqual(appd['target'], 'appd.exe')

            self.assertEqual(app['deps'], [['file.o'], []])
            self.assertEqual(appd['deps'], [['filed.o'], []])

            self.assertEqual(app['body'], [('command', 'gcc -o app.exe file.o')])
            self.assertEqual(appd['body'], [('command', 'GCC = gcc -g'),
                ('command', '$(GCC) -o appd.exe filed.o'),
                ('command', 'echo "built debug"')])

    ut.main()
