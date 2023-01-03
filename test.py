'''Test memory importer'''

def prepare():
    import os
    import zipfile
    import _memimporter
    with zipfile.ZipFile('testmod.zip', 'w') as zf:
        zf.writestr('testmod\\__init__.py', b'')
        zf.write(_memimporter.__file__,
                 'testmod\\' + os.path.basename(_memimporter.__file__))

def test():
    import zipextimporter
    zipextimporter.monkey_patch()
    sys.path.insert(0, 'testmod.zip')
    import testmod._memimporter

if __name__ == '__main__':
    import sys
    if 'prepare' in sys.argv:
        prepare()
    if 'test' in sys.argv:
        test()
