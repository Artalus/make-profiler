import collections
import re

from more_itertools import peekable


class Tokens:
    target = 'target'
    command = 'command'
    expression = 'expression'

def count_sequenced(seq, x):
    """
    >>> count_sequenced('aaabc','a')
    3
    >>> count_sequenced('aaabc', 'b')
    0
    """
    cnt=0
    for s in seq:
        if s != x:
            break
        cnt += 1
    return cnt

def is_odd(x):
    """
    >>> is_odd(1)
    True
    >>> is_odd(2)
    False
    """
    return x & 1 == 1

def continued(strip_line):
    r"""
    >>> continued("abcd \\")
    True
    >>> continued("abcd \\\\")
    False
    >>> continued("abcd")
    False
    """
    cs = count_sequenced(reversed(strip_line), '\\')
    return cs > 0 and is_odd(cs)

def glue_multiline(fd, firstline):
    lines = []
    strip_line = firstline.strip()
    while continued(strip_line):
        lines.append(strip_line[:-1].strip())
        strip_line = next(fd).strip()
    lines.append(strip_line)
    return ' '.join(lines)

def tokenizer(fd):
    for line in fd:
        strip_line = line.strip()

        # skip empty lines
        if not strip_line:
            continue

        # skip comments, don't skip docstrings
        if strip_line[0] == '#' and line[:2] != '##':
            continue

        if line[0] == '\t':
            yield (Tokens.command, glue_multiline(fd, line))
        elif ':' in line and '=' not in line:
            yield (Tokens.target, glue_multiline(fd, line))
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
