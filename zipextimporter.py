r"""zipextimporter - an importer which can import extension modules
from zipfiles without unpacking them to the file system.

This file is part of the py2exe package.

Overview
========

zipextimporter.py contains the ZipExtImporter class which allows to
load Python binary extension modules contained in a zip.archive,
without unpacking them to the file system.

Call the zipextimporter.monkey_patch() function to monkey patch the zipimporter,
or call the zipextimporter.install() function to install the import hook,
add a zip-file containing .pyd or .dll extension modules to sys.path,
and import them.

It uses the _memimporter (memimport) extension which uses code from
Joachim Bauch's MemoryModule library. This library emulates the win32 api
function LoadLibrary.

Sample usage
============

You have to prepare a zip-archive 'lib.zip' containing
your Python's _socket.pyd for this example to work.

>>> import zipextimporter
>>> zipextimporter.monkey_patch()
>>> import sys
>>> sys.path.insert(0, "lib.zip")
>>> import _socket
>>> print(_socket)
<module '_socket' from 'lib.zip\\_socket.pyd'>
>>> _socket.__file__
'lib.zip\\_socket.pyd'
>>> _socket.__loader__
<ZipExtensionImporter object 'lib.zip\'>
>>> # Reloading also works correctly:
>>> import importlib
>>> _socket is importlib.reload(_socket)
True
>>>

"""
import sys
from zipimport import zipimporter, ZipImportError
from _frozen_importlib import ModuleSpec

from memimport import memimport, get_verbose_flag


pyver = '%d%d' % sys.version_info[:2]

class ZipExtensionImporter(zipimporter):
    '''Import Python extensions from Zip files, just likes built-in zipimporter.
    Supported file extensions: "pyd", "dll", " "(none).
    '''
    from importlib.machinery import EXTENSION_SUFFIXES as suffixes
    suffixes = suffixes + ['.dll', '']
    suffixes_pkg = [(f'\\__init__{suffix}', True) for suffix in suffixes]
    suffixes_pyver = [(f'{pyver}{suffix}', False) for suffix in suffixes
                      if pyver not in suffix]
    suffixes = [(suffix, False) for suffix in suffixes]
    suffixes += suffixes_pkg
    suffixes_pyver += suffixes
    names_pyver = 'pywintypes', 'pythoncom'
    verbose = get_verbose_flag()
    del suffixes_pkg

    def __init__(self, path_or_importer):
        if isinstance(path_or_importer, zipimporter):
            self.zipimporter = path_or_importer
        else:
            self.zipimporter = zipimporter(path_or_importer)
            if hasattr(zipimporter, '_files'):
                super().__init__(path_or_importer)

    def __getattr__(self, name):
        return getattr(self.zipimporter, name)

    @property
    def zipextimporter(self):
        if isinstance(self, ZipExtensionImporter):
            return self
        try:
            zipextimporter = self._zipextimporter
        except AttributeError:
            self._zipextimporter = zipextimporter = ZipExtensionImporter(self)
        return zipextimporter

    def find_extension(self, fullname, cache={}):
        path_info = cache.get(fullname)
        if path_info:
            return path_info
        name = fullname.rpartition('.')[2]
        initname = f'PyInit_{name}'.encode()
        _path = self.prefix + name
        if name.endswith(self.names_pyver):
            suffixes = self.suffixes_pyver
        else:
            suffixes = self.suffixes
        for suffix, is_package in suffixes:
            path = _path + suffix
            if path in self._files:
                if not suffix.endswith('.pyd') and initname not in self.get_data(path):
                    if self.verbose > 1:
                        print(f'# found {path} in zipfile {self.archive}, '
                               'but it is not a Python extension',
                              file=sys.stderr)
                    continue
                if self.verbose > 1:
                    print(f'# found {path} in zipfile {self.archive}',
                          file=sys.stderr)
                cache[fullname] = path_info = f'{self.archive}\\{path}', is_package
                return path_info
        return None, None

    if hasattr(zipimporter, 'find_loader'):
        def find_loader(self, fullname, path=None):
            try:
                loader, portion = self._find_loader(fullname)
            except AttributeError:
                loader, portion = self.zipimporter.find_loader(fullname)
            if loader is not None:
                return loader, portion
            zipextimporter = self.zipextimporter
            path, is_package = zipextimporter.find_extension(fullname)
            return path and zipextimporter, []

    if hasattr(zipimporter, 'find_spec'):
        def find_spec(self, fullname, target=None):
            try:
                spec = self._find_spec(fullname)
            except AttributeError:
                spec = self.zipimporter.find_spec(fullname)
            if spec is not None:
                return spec
            zipextimporter = self.zipextimporter
            path, is_package = zipextimporter.find_extension(fullname)
            if path:
                return ModuleSpec(fullname, zipextimporter, origin=path, is_package=is_package)

    def load_module(self, fullname):
        mod = memimport(fullname=fullname, loader=self.zipextimporter)
        if self.verbose:
            print(f'import {fullname} # loaded from zipfile {self.archive}',
                  file=sys.stderr)
        return mod

    def create_module(self, spec):
        mod = memimport(spec=spec)
        if self.verbose:
            print(f'import {spec.name} # loaded from zipfile {self.archive}',
                  file=sys.stderr)
        return mod

    def exec_module(self, module):
        pass

    def get_code(self, fullname):
        path, is_package = self.find_extension(fullname)
        if path is None:
            return self.zipimporter.get_code(fullname)

    def get_source(self, fullname):
        path, is_package = self.find_extension(fullname)
        if path is None:
            return self.zipimporter.get_source(fullname)

    def get_filename(self, fullname):
        path, is_package = self.find_extension(fullname)
        if path is None:
            return self.zipimporter.get_filename(fullname)
        return path

    def is_package(self, fullname):
        path, is_package = self.find_extension(fullname)
        if path is None:
            return self.zipimporter.is_package(fullname)
        return is_package

    def __repr__(self):
        return super().__repr__().replace('zipimporter', 'ZipExtensionImporter')


def install():
    '''Install the zipextimporter.'''
    if ZipExtensionImporter in sys.path_hooks:
        return
    try:
        i = sys.path_hooks.index(zipimporter)
    except ValueError:
        sys.path_hooks.insert(0, ZipExtensionImporter)
    else:
        sys.path_hooks[i] = ZipExtensionImporter
    sys.path_importer_cache.clear()
    ## # Not sure if this is needed...
    ## import importlib
    ## importlib.invalidate_caches()


def monkey_patch():
    '''Monkey patch the zipimporter, best compatibility.'''
    if hasattr(zipimporter, '_files'):
        return install()
    if hasattr(zipimporter, 'zipextimporter'):
        return
    zipimporter.zipextimporter = ZipExtensionImporter.zipextimporter
    if hasattr(zipimporter, 'find_loader'):
        zipimporter._find_loader = zipimporter.find_loader
        zipimporter.find_loader = ZipExtensionImporter.find_loader
    if hasattr(zipimporter, 'find_spec'):
        zipimporter._find_spec = zipimporter.find_spec
        zipimporter.find_spec = ZipExtensionImporter.find_spec


def set_verbose(i):
    '''Set verbose, the argument as same as built-in function int's.'''
    i = int(i)
    ZipExtensionImporter.verbose = i
    if i > 1:
        import memimport
        memimport.set_verbose(i)
