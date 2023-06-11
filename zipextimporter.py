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

import os
import sys
from zipimport import *
from _frozen_importlib import ModuleSpec, spec_from_loader
from _frozen_importlib_external import ExtensionFileLoader, spec_from_file_location

from memimport import memimport, export_hook_name


__all__ = [
    'install', 'set_verbose',
    'set_exclude_modules', 'set_ver_binding_modules',
    'list_exclude_modules', 'list_ver_binding_modules'
]


# Makes order as same as import from Non-Zip.
def _generate_searchorders():
    global _searchorder, _searchorder_pyver
    import _imp
    suffixes = _imp.extension_suffixes()
    debug = '_d.pyd' in suffixes and '_d' or ''
    suffixes += [f'{debug}.dll', f'{debug}']
    pyver = '%d%d' % sys.version_info[:2]
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
        (f'{pyver}{debug}.dll', True, False),
        (f'{pyver}{debug}.pyd', True, False),
        (f'{pyver}{debug}', True, False),
        *_searchorder[-2:],
    )
_generate_searchorders(); del _generate_searchorders
# pyver suffix, only match the last name
_names_pyver = {'pywintypes', 'pythoncom'}
# Use cache file instead of import from memory, only match the full name
_names_cached = set()


class _ModuleInfo:
    __slots__ = ('path', 'is_ext', 'is_package', 'cached')
    def __init__(self, *args):
        self.path, self.is_ext, self.is_package, self.cached = args


# Return some information about a module.
def _get_module_info(self, fullname, _raise=False, _tempcache=[None, None]):
    key, mi = _tempcache
    if key == (fullname, self.archive):
        return mi
    name = fullname.rpartition('.')[2]
    initname = export_hook_name(name).encode()
    if name in _names_pyver:
        searchorder = _searchorder_pyver
    else:
        searchorder = _searchorder
    _path = self.prefix + name
    for suffix, is_ext, is_package in searchorder:
        path = _path + suffix
        if path not in self._files:
            continue
        if not is_ext:
            return _ModuleInfo(path, is_ext, is_package, None)
        if not suffix.endswith('.pyd') and initname not in self.get_data(path):
            _verbose_msg('# zipextimporter: '
                        f'skiped {path} in zipfile {self.archive}, '
                         'it is not a Python extension', 2)
            continue
        _verbose_msg('# zipextimporter: '
                    f'found {path} in zipfile {self.archive}', 2)
        if fullname in _names_cached:
            path = _get_cached_path(self, path)
        else:
            path = f'{self.archive}\\{path}'
        mi = _ModuleInfo(path, is_ext, is_package, False)
        _tempcache[:] = (fullname, self.archive), mi
        return mi
    if _raise:
        raise ZipImportError(f"can't find module {fullname!r}", name=fullname)


# Return the path of cached extension file, for loading memimport excluded modules.
def _get_cached_path(self, path):
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
    if os.path.exists(path_cache):
        _verbose_msg('# zipextimporter: '
                    f'found cached {path} at {path_cache}', 2)
    else:
        os.makedirs(os.path.dirname(path_cache), exist_ok=True)
        open(path_cache, 'wb').write(self.get_data(path))
        _verbose_msg('# zipextimporter: '
                    f'extracted cached {path} to {path_cache}', 2)
    return path_cache


# Return the path if it represent a directory.
def _get_dir_path(self, fullname):
    path = self.prefix + fullname.rpartition(".")[2]
    if f"{path}\\" in self._files:
        return f"{self.archive}\\{path}"


class ZipExtensionImporter(zipimporter):
    '''Import Python extensions from Zip files, just likes built-in zipimporter.
    Supported file extensions: "pyd", "dll", " "(none).
    '''
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

    if hasattr(zipimporter, 'find_loader'):
        def find_loader(self, fullname, path=None):
            mi = _get_module_info(self.zipextimporter, fullname)
            if mi is None:
                dirpath = _get_dir_path(self, fullname)
                if dirpath:
                    return None, [dirpath]
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
            mi = _get_module_info(self.zipextimporter, fullname)
            if mi is None:
                dirpath = _get_dir_path(self, fullname)
                if dirpath:
                    spec = ModuleSpec(fullname, None)
                    spec.submodule_search_locations = [dirpath]
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
        _verbose_msg(f'import {spec.name} # loaded from zipfile {mod.__file__}')
        return mod

    def exec_module(self, module):
        # all has been done in create_module(), also skip importlib.reload()
        pass

    def get_code(self, fullname):
        mi = _get_module_info(self, fullname, _raise=True)
        if not mi.is_ext:
            return self.zipimporter.get_code(fullname)

    def get_source(self, fullname):
        mi = _get_module_info(self, fullname, _raise=True)
        if not mi.is_ext:
            return self.zipimporter.get_source(fullname)

    def get_filename(self, fullname):
        mi = _get_module_info(self, fullname, _raise=True)
        return mi.path

    def is_package(self, fullname):
        mi = _get_module_info(self, fullname, _raise=True)
        return mi.is_package

    def __repr__(self):
        return f'<ZipExtensionImporter object "{self.archive}\\{self.prefix}">'


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
        import _warnings
        _warnings.warn('Did nothing. Please manually uninstall before call '
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
        import _warnings
        _warnings.warn('Did nothing. Please manually uninstall before call '
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
    _set_importer(modules, _names_cached.add)


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
    return list(_names_cached)


def list_ver_binding_modules():
    '''Return a list of modules which will be add a version suffix.
    Also see `set_ver_binding_modules`.
    '''
    return list(_names_pyver)


def _set_ver_binding_modules(modules, f=lambda m:str.rpartition(m,'.')[2]):
    _set_importer(modules, _names_pyver.add, f)


def _set_importer(modules, attrfunc, argsfunc=None):
    if not isinstance(modules, (list, tuple)):
        modules = [modules]
    for module in modules:
        if not isinstance((module, str)):
            raise ValueError(f'the module name MUST be a str, not {type(module)}')
        attrfunc(argsfunc and argsfunc(module) or module)


verbose = sys.flags.verbose

def _verbose_msg(msg, verbosity=1):
    if max(verbose, sys.flags.verbose) >= verbosity:
        print(msg, file=sys.stderr)

def set_verbose(i):
    '''Set verbose, the argument as same as built-in function int's.'''
    global verbose
    verbose = int(i)
