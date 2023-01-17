r"""zipextimporter - an importer which can import extension modules
from zipfiles without unpacking them to the file system.

This file is part of the py2exe package.

Overview
========

zipextimporter.py contains the ZipExtImporter class which allows to
load Python binary extension modules contained in a zip.archive,
without unpacking them to the file system.

Call the zipextimporter.install(hook=False) to monkey patch the zipimporter,
or call the zipextimporter.install(hook=True) to install the import hook,
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
>>> zipextimporter.install()
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
import _imp
from zipimport import zipimporter
try:
    import _warnings as warnings
except ImportError:
    import warnings
try:
    from _frozen_importlib import ModuleSpec, spec_from_loader
    from _frozen_importlib_external import ExtensionFileLoader, spec_from_file_location
except ImportError:
    from importlib.machinery import ModuleSpec, ExtensionFileLoader
    from importlib.util import spec_from_loader, spec_from_file_location

from memimport import memimport, export_hook_name, get_verbose_flag


__all__ = [
    'install', 'set_verbose',
    'set_exclude_modules', 'set_ver_binding_modules',
    'list_exclude_modules', 'list_ver_binding_modules'
]


class _ModuleInfo:
    __slots__ = ('path', 'is_ext', 'is_package', 'cached')
    def __init__(self, *args):
        self.path, self.is_ext, self.is_package, self.cached = args


class ZipExtensionImporter(zipimporter):
    '''Import Python extensions from Zip files, just likes built-in zipimporter.
    Supported file extensions: "pyd", "dll", " "(none).
    '''
    suffixes = _imp.extension_suffixes() + ['.dll', '']
    pyver = '%d%d' % sys.version_info[:2]
    suffixes_pyver = f'{pyver}.dll', f'{pyver}.pyd', pyver
    _searchorder = (
        *[(f'\\__init__{suffix}', True, True) for suffix in suffixes],
        ('\\__init__.pyc', False, True),
        ('\\__init__.py', False, True),
        *[(suffix, True, False) for suffix in suffixes],
        ('.pyc', False, False),
        ('.py', False, False),
    )
    _searchorder_pyver = (
        *_searchorder[:-2],
        *[(suffix, True, False) for suffix in suffixes_pyver],
        *_searchorder[-2:],
    )
    # add pyver suffix, only match the last name
    names_pyver = {'pywintypes', 'pythoncom'}
    # use cache file instead of import from memory, only match the full name
    names_cached = {'greenlet._greenlet'}
    verbose = get_verbose_flag()
    del suffixes, suffixes_pyver, pyver

    def __init__(self, path_or_importer):
        if isinstance(path_or_importer, zipimporter):
            self.zipimporter = path_or_importer
        else:
            self.zipimporter = zipimporter(path_or_importer)
            if hasattr(zipimporter, '_files'):  # py <= 37, built-in
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

    def _get_module_info(self, fullname, _raise=False):
        name = fullname.rpartition('.')[2]
        initname = export_hook_name(name).encode()
        if name in self.names_pyver:
            searchorder = self._searchorder_pyver
        else:
            searchorder = self._searchorder
        _path = self.prefix + name
        for suffix, is_ext, is_package in searchorder:
            path = _path + suffix
            if path not in self._files:
                continue
            if not is_ext:
                return _ModuleInfo(path, is_ext, is_package, None)
            if not suffix.endswith('.pyd') and initname not in self.get_data(path):
                if self.verbose > 1:
                    print(f'# found {path} in zipfile {self.archive}, '
                           'but it is not a Python extension',
                          file=sys.stderr)
                continue
            if self.verbose > 1:
                print(f'# found {path} in zipfile {self.archive}',
                      file=sys.stderr)
            if fullname in self.names_cached:
                mi = self._get_cached_path(path), is_ext, is_package, True
            else:
                mi = f'{self.archive}\\{path}', is_ext, is_package, False
            return _ModuleInfo(*mi)
        if _raise:
            raise ZipImportError(f"can't find module {fullname!r}", name=fullname)

    def _get_cached_path(self, path):
        import os
        eggs_cache = os.getenv('EGGS_CACHE')
        if eggs_cache is None:
            home = os.getenv('PYTHONHOME')
            if eggs_cache is None:
                from zipimport import __file__
                home = os.path.dirname(os.path.dirname(__file__))
            os.environ['EGGS_CACHE'] = eggs_cache = os.path.join(home, 'Eggs-Cache')
        path_cache = os.path.join(os.path.abspath(eggs_cache),
                                  os.path.basename(self.archive) + '-tmp',
                                  path)
        if not os.path.exists(path_cache):
            os.makedirs(os.path.dirname(path_cache), exist_ok=True)
            open(path_cache, 'wb').write(self.get_data(path))
        return path_cache

    if hasattr(zipimporter, 'find_loader'):
        def find_loader(self, fullname, path=None):
            mi = self.zipextimporter._get_module_info(fullname)
            if mi is None:
                path = self.prefix + fullname.rpartition('.')[2]
                if f'{path}\\' in self._files:
                    return None, [f'{self.archive}\\{path}']
                return None, []
            if mi.is_ext:
                if mi.cached:
                    loader = ExtensionFileLoader(fullname, mi.path)
                else:
                    loader = self.zipextimporter
            else:
                try:
                    loader = self.zipimporter
                except AttributeError:
                    loader = self
            return loader, []

    if hasattr(zipimporter, 'find_spec'):
        def find_spec(self, fullname, target=None):
            mi = self.zipextimporter._get_module_info(fullname)
            if mi is None:
                path = self.prefix + fullname.rpartition('.')[2]
                if f'{path}\\' in self._files:
                    spec = ModuleSpec(fullname, None)
                    spec.submodule_search_locations = [f'{self.archive}\\{path}']
                    return spec
                return None
            if mi.is_ext:
                if mi.cached:
                    return spec_from_file_location(fullname, mi.path)
                spec = ModuleSpec(fullname, self.zipextimporter, origin=mi.path)
                if mi.is_package:
                    spec.submodule_search_locations = [mi.path.rpartition('\\')[0]]
            else:
                try:
                    loader = self.zipimporter
                except AttributeError:
                    loader = self
                spec = spec_from_loader(fullname, loader, is_package=mi.is_package)
            return spec

    if hasattr(zipimporter, 'load_module'):
        def load_module(self, fullname):
            # will never enter here, raise error for developers
            raise NotImplementedError('load_module() is not implemented, '
                                      'use create_module() instead.')

    def create_module(self, spec):
        mod = memimport(spec=spec)
        if self.verbose:
            print(f'import {spec.name} # loaded from zipfile {self.archive}',
                  file=sys.stderr)
        return mod

    def exec_module(self, module):
        # all has been done in create_module(), also skip importlib.reload()
        pass

    ## ====================== improves compatibility ======================
    def get_code(self, fullname):
        mi = self._get_module_info(fullname, _raise=True)
        if not mi.is_ext:
            return self.zipimporter.get_code(fullname)

    def get_source(self, fullname):
        mi = self._get_module_info(fullname, _raise=True)
        if not mi.is_ext:
            return self.zipimporter.get_source(fullname)

    def get_filename(self, fullname):
        mi = self._get_module_info(fullname, _raise=True)
        if not mi.is_ext:
            return self.zipimporter.get_filename(fullname)
        return mi.path

    def is_package(self, fullname):
        mi = self._get_module_info(fullname, _raise=True)
        return mi.is_package
    ## ====================================================================

    def __repr__(self):
        return super().__repr__().replace('zipimporter', 'ZipExtensionImporter')


def install(hook=hasattr(zipimporter, '_files')):
    '''Install the zipextimporter.'''
    if hook:
        _install_hook()
    else:
        _monkey_patch()


def _install_hook():
    '''Install the zipextimporter to `sys.path_hooks`.'''
    if ZipExtensionImporter in sys.path_hooks:
        return
    if hasattr(zipimporter, 'zipextimporter'):
        warnings.warn('Did nothing. Please manually uninstall before call '
                      'install() multi-times with different argument values.',
                      category=RuntimeWarning, stacklevel=3)
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


def _monkey_patch():
    '''Monkey patch the zipimporter, best compatibility.'''
    if hasattr(zipimporter, '_files'):  # py <= 37, built-in
        return _install_hook()
    if hasattr(zipimporter, 'zipextimporter'):
        return
    if ZipExtensionImporter in sys.path_hooks:
        warnings.warn('Did nothing. Please manually uninstall before call '
                      'install() multi-times with different argument values.',
                      category=RuntimeWarning, stacklevel=3)
        return
    zipimporter.zipextimporter = ZipExtensionImporter.zipextimporter
    if hasattr(zipimporter, 'find_loader'):
        zipimporter._find_loader = zipimporter.find_loader
        zipimporter.find_loader = ZipExtensionImporter.find_loader
    if hasattr(zipimporter, 'find_spec'):
        zipimporter._find_spec = zipimporter.find_spec
        zipimporter.find_spec = ZipExtensionImporter.find_spec


def set_exclude_modules(modules):
    '''Set modules which will not be import from memory, instead use cache file.
    Notice:
        Please ensure input fullname of modules.
    '''
    _set_importer(modules, ZipExtensionImporter.names_cached.add)


def set_ver_binding_modules(modules):
    '''Set modules which will be add a version suffix of currrent Python.
    Notice:
        All parent names will be ignored from the input modules.
    '''
    _set_ver_binding_modules(modules)


def list_exclude_modules():
    '''Return a list of modules which will not be import from memory.
    Also see `set_exclude_modules`.
    '''
    return list(ZipExtensionImporter.names_cached)


def list_ver_binding_modules():
    '''Return a list of modules which will be add a version suffix.
    Also see `set_ver_binding_modules`.
    '''
    return list(ZipExtensionImporter.names_pyver)


def _set_ver_binding_modules(modules, f=lambda m:str.rpartition(m,'.')[2]):
    _set_importer(modules, ZipExtensionImporter.names_pyver.add, f)


def _set_importer(modules, attrfunc, argsfunc=None):
    if not isinstance(modules, (list, tuple)):
        modules = [modules]
    for module in modules:
        if not isinstance((module, str)):
            raise ValueError(f'the module name MUST be a str, not {type(module)}')
        attrfunc(argsfunc and argsfunc(module) or module)


def set_verbose(i):
    '''Set verbose, the argument as same as built-in function int's.'''
    i = int(i)
    ZipExtensionImporter.verbose = i
    if i > 1:
        import memimport
        memimport.set_verbose(i)
