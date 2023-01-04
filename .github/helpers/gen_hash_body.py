#!/usr/bin/env python3

import argparse
import hashlib
import os
import glob

md_head = '''\
| %s | Filename |
| -- | -------- |
'''
md_line = '| %s | %s |\n'
sum_line = '%s  %s\n'

def hash(artifact, algorithm):
    return (hashlib.new(algorithm, open(artifact, 'rb').read()).hexdigest(),
            os.path.basename(artifact))

def generater(artifacts, algorithm):
    artifacts = glob.glob(os.path.join(artifacts, '**/*.whl'), recursive=True)
    artifacts = [hash(artifact, algorithm)
                 for artifact in artifacts
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
