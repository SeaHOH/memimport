'''Test memory importer'''

def prepare():
    import zipfile
    import _memimporter
    with zipfile.ZipFile('testpkg.zip', 'w') as zf:
        zf.write(_memimporter.__file__, 'testpkg/_memimporter/__init__.pyd')
        zf.writestr('testpkg/_memimporter/submod.py', b'loaded = True')

def test_zipextimporter():
    import importlib
    import zipimport
    import zipextimporter
    zipextimporter.install()
    zipextimporter.set_verbose(2)
    sys.path.insert(0, 'testpkg.zip')

    # namespace package with implicit directory
    import testpkg
    assert 'namespace' in str(testpkg.__loader__).lower()

    import testpkg._memimporter
    print(testpkg._memimporter.__loader__)
    import_module_old = testpkg._memimporter.import_module
    assert isinstance(testpkg._memimporter.__loader__, zipextimporter.ZipExtensionImporter)
    assert testpkg._memimporter is sys.modules['testpkg._memimporter']

    # same as ExtensionFileLoader
    importlib.reload(testpkg._memimporter)
    assert import_module_old is testpkg._memimporter.import_module

    # different to ExtensionFileLoader
    sys.modules.pop('testpkg._memimporter')
    import testpkg._memimporter
    assert import_module_old is not testpkg._memimporter.import_module

    from testpkg._memimporter import submod
    assert submod.loaded == True
    print(submod.__loader__)
    assert isinstance(submod.__loader__, zipimport.zipimporter)

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
        print('excepted error:', repr(err))
        assert err


if __name__ == '__main__':
    import sys
    if 'prepare' in sys.argv:
        prepare()
    if 'test' in sys.argv:
        test_zipextimporter()
        test_memimport()
