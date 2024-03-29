#!/usr/bin/env python3

import argparse
import hashlib
import os
import re
import glob
import shutil

md_head = '''\
| %s | Filename |
| -- | -------- |
'''
md_line = '| %s | %s |\n'
sum_line = '%s  %s\n'

def sort_keys(key):
    m = re.search(f'-cp3(\d{{1,2}})-[^\{os.sep}]+(\d\d)\.whl$', key)
    if m is None:
        return 0, 0
    ver, bit = m.groups()
    return int(ver), int(bit)

def hash(artifact, algorithm):
    sum = hashlib.new(algorithm, open(artifact, 'rb').read()).hexdigest().upper()
    filename = os.path.basename(artifact)
    if not artifact.startswith(('dist/', 'dist\\')):
        shutil.move(artifact, f'dist/{filename}')
    return sum, filename

def generater(artifacts, algorithm):
    artifacts = glob.glob(os.path.join(artifacts, '**/*.whl'), recursive=True) + \
                glob.glob('dist/*.tar.gz')
    artifacts = [hash(artifact, algorithm)
                 for artifact in sorted(artifacts, key=sort_keys, reverse=True)
                 if os.path.isfile(artifact)]

    with open('body.md', 'w') as bf:
        bf.write(md_head % algorithm.upper())
        for artifact in artifacts:
            bf.write(md_line % artifact)

    with open(algorithm + '.sum', 'w') as sf:
        for artifact in artifacts:
            sf.write(sum_line % artifact)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Generate hash and release body.')
    parser.add_argument('artifacts', nargs='?', default='', help='Artifacts path.')
    parser.add_argument('algorithm', nargs='?', default='sha256', help='Hash algorithm.')
    args = parser.parse_args()
    generater(args.artifacts, args.algorithm)
