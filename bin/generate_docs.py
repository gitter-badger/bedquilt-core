#! /usr/bin/env python

import string
import inspect
import pybedquilt
import os
import re
from pprint import pprint
import glob


TARGET_FILE_PATH = 'doc/api_docs.md'
SOURCE_FILE_PATH = 'src/sql/*.sql'
MAGIC_LINE = '---- ---- ---- ----'


FUNCTION_NAME_REGEX = 'FUNCTION (.+)\('
LANGUAGE_REGEX = 'LANGUAGE (\w+)'
RETURNS_REGEX = 'RETURNS (.+) AS'
PARAMS_REGEX = 'FUNCTION [a-z_]+\((.+)\)'


def main():
    final_contents = []

    contents = None
    with open(TARGET_FILE_PATH, 'r') as target:
        contents = target.readlines()
    for line in contents:
        if line.strip() != MAGIC_LINE.strip():
            final_contents.append(line)
        else:
            final_contents.append(MAGIC_LINE)
            final_contents.append('\n')
            break

    paths = sorted(glob.glob(SOURCE_FILE_PATH))
    for path in paths:
        with open(path, 'r') as source_file:
            source = source_file.read()

        source_blocks = blocks(source)
        function_blocks = []

        for block in source_blocks:
            if ('CREATE OR REPLACE FUNCTION' in block
                and '-- #' not in block):
                function_blocks.append(block)

        details = [parse(x) for x in function_blocks]

        final_string = "\n\n"
        for detail in details:
            if detail is not None and detail['name'] is not None:
                final_string = final_string + to_md(detail)

        for line in final_string.splitlines():
            final_contents.append(line)
            final_contents.append('\n')

    with open(TARGET_FILE_PATH, 'w') as target:
        target.writelines(final_contents)


# Helpers
def md_escape(st):
    if st is None:
        return None
    return st.replace('_', '\_')


def blocks(st):
    return re.split('\n{3,}', st)



def get_re(exp, st):
    result = None
    r = re.search(exp, st)
    if r:
        g = r.groups()
        if g:
            result = g[0]
    return result


def parse(st):

    function_name = get_re(FUNCTION_NAME_REGEX, st)
    language = get_re(LANGUAGE_REGEX, st)
    return_type = get_re(RETURNS_REGEX, st)
    params_string = get_re(PARAMS_REGEX, st)
    params = None
    if params_string:
        params = params_string.split(', ')
        params = [param.split(' ') for param in params]
        params = params_string
    doc_comment = get_doc_comment(st)
    if doc_comment.strip()[:9] == 'private -':
        return None

    return {
        'name': function_name,
        'language': language,
        'params': params,
        'returns': return_type,
        'doc_comment': doc_comment
    }


def get_doc_comment(st):
    result = ''
    lines = st.splitlines()
    comment_starts = ['/* ', ' * ', ' */']
    if lines:
        if lines[0].startswith('/* '):
            comment_lines = []
            for line in lines:
                if line[:3] in comment_starts:
                    comment_lines.append(line[3:])
                if line[:3] == comment_starts[-1]:
                    break
            result = "\n".join(comment_lines)
    return result


def to_md(doc):
    return (
"""

## {name}

- params: `{params}`
- returns: `{returns}`
- language: `{language}`

```markdown
{doc_comment}
```

""".format(**{
    'name': md_escape(doc['name']),
    'language': doc['language'],
    'params': doc['params'],
    'returns': doc['returns'],
    'doc_comment': doc['doc_comment']})
        )


# Run if main
if __name__ == '__main__':
    main()
