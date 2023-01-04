'''Test memory importer'''

def prepare():
    import zipfile
    import _memimporter
    with zipfile.ZipFile('testpkg.zip', 'w') as zf:
        zf.writestr('testpkg\\__init__.py', b'')
        zf.write(_memimporter.__file__, 'testpkg\\_memimporter\\__init__.pyd')
        zf.writestr('testpkg\\_memimporter\\submod.py', b'loaded = True')

def test_zipextimporter():
    import importlib
    import zipextimporter
    zipextimporter.monkey_patch()
    zipextimporter.set_verbose(2)
    sys.path.insert(0, 'testpkg.zip')

    import testpkg._memimporter
    print(testpkg._memimporter.__loader__)
    assert isinstance(testpkg._memimporter.__loader__, zipextimporter.ZipExtensionImporter)

    from testpkg._memimporter import submod
    assert submod.loaded == True
    print(submod.__loader__)
    assert isinstance(submod.__loader__, zipextimporter.zipimporter)

    assert testpkg._memimporter.submod is importlib.reload(testpkg._memimporter).submod

def test_memimport():
    import sys
    import importlib
    import _memimporter

    def get_data():
        return open(_memimporter.__file__, 'rb').read()

    sys.modules['mempkg'] = mempkg = type(sys)('mempkg')
    mempkg.__path__ = []
    if not hasattr(mempkg, '__builtins__'):
        mempkg.__builtins__ = __builtins__

    from memimport import memimport, MemExtensionFileLoader
    mempkg_memimporter = memimport(data=get_data, fullname='mempkg._memimporter')
    print(mempkg_memimporter.__loader__)
    assert isinstance(mempkg_memimporter.__loader__, MemExtensionFileLoader)
    assert mempkg_memimporter is sys.modules['mempkg._memimporter']
    assert mempkg_memimporter is not _memimporter
    try:
        err = None
        importlib.reload(mempkg_memimporter)
    except Exception as e:
        err = e
    finally:
        print(err)
        assert err


if __name__ == '__main__':
    import sys
    if 'prepare' in sys.argv:
        prepare()
    if 'test' in sys.argv:
        test_zipextimporter()
        test_memimport()
