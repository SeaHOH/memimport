r"""zipextimporter - an importer which can import extension modules
from zipfiles without unpacking them to the file system.

This file is part of the py2exe package.

Overview
========

zipextimporter.py contains the ZipExtImporter class which allows to
load Python binary extension modules contained in a zip.archive,
without unpacking them to the file system.

Call the `zipextimporter.install(hook=False)` to monkey patch the zipimporter,
or call the `zipextimporter.install(hook=True)` to install the import hook,
add a zip-file containing "pyd" or "dll" extension modules to sys.path,
and import them.

It uses the _memimporter (memimport) extension which uses code from
Joachim Bauch's MemoryModule library. This library emulates the win32 api
function LoadLibrary.

Sample usage
============

You have to prepare a zip-archive "lib.zip" containing
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
import zipimport
from zipimport import *
from _frozen_importlib import ModuleSpec, spec_from_loader
from _frozen_importlib_external import ExtensionFileLoader, spec_from_file_location

from memimport import (
        memimport, export_hook_name, __version__,
        _path_join, _path_dirname, _path_basename, _path_exists, _makedirs
)


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
    pyver = '%d%d' % sys.version_info[:2]
    suffixes += [f'{pyver}{debug}.pyd']
    suffixes += [suffix.replace('.pyd', '.dll') for suffix in suffixes]
    suffixes += [debug, f'{pyver}{debug}']
    _searchorder_pyver = (
        *[(f'\\__init__{suffix}', True, True) for suffix in suffixes],
        ('\\__init__.pyc', False, True),
        ('\\__init__.py', False, True),
        *[(suffix, True, False) for suffix in suffixes],
        ('.pyc', False, False),
        ('.py', False, False),
    )
    _searchorder = [i for i in _searchorder_pyver
                    if pyver not in i[0] or 'win' in i[0]]

_generate_searchorders(); del _generate_searchorders
# pyver suffix, only match the last name
_names_pyver = {'pywintypes', 'pythoncom'}
# Use cache file instead of import from memory, only match the full name
_names_cached = set()


class _ModuleInfo:
    __slots__ = ('path', 'is_ext', 'is_package', 'cached')
    def __init__(self, *args):
        self.path, self.is_ext, self.is_package, self.cached = args


def _get_files(self):
    try:
        return self._files
    except AttributeError:
        return self._get_files()  # py >= 313


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
    files = _get_files(self)
    for suffix, is_ext, is_package in searchorder:
        path = _path + suffix
        if path not in files:
            continue
        if not is_ext:
            return _ModuleInfo(path, is_ext, is_package, None)
        if not suffix.endswith('.pyd') and initname not in self.get_data(path):
            _verbose_msg('# zipextimporter: '
                        f'skiped {path!r} in zipfile {self.archive!r}, '
                         'it is not a Python extension', 2)
            continue
        _verbose_msg('# zipextimporter: '
                    f'found {path!r} in zipfile {self.archive!r}', 2)
        mi = _ModuleInfo(
            f'{self.archive}\\{path}',
            is_ext,
            is_package,
            fullname in _names_cached and _get_cached_path(self, path) or None
        )
        _tempcache[:] = (fullname, self.archive), mi
        return mi
    if _raise:
        raise ZipImportError(f"can't find module {fullname!r}", name=fullname)


# Return the path of cached extension file, for loading memimport excluded modules.
def _get_cached_path(self, path):
    from nt import environ
    eggs_cache = environ.get('EGGS_CACHE')
    if eggs_cache is None:
        home = environ.get('PYTHONHOME')
        if home is None:
            home = _path_dirname(_path_dirname(zipimport.__file__))
        environ['EGGS_CACHE'] = eggs_cache = _path_join(home, 'Eggs-Cache')
    path_cache = _path_join(eggs_cache,
                            _path_basename(self.archive) + '-tmp',
                            path)
    if _path_exists(path_cache):
        _verbose_msg('# zipextimporter: '
                    f'found cached {path!r} at {path_cache!r}', 2)
    else:
        _makedirs(_path_dirname(path_cache))
        open(path_cache, 'wb').write(self.get_data(path))
        _verbose_msg('# zipextimporter: '
                    f'extracted cached {path!r} to {path_cache!r}', 2)
    return path_cache


# Return the path if it represent a directory.
def _get_dir_path(self, fullname):
    path = self.prefix + fullname.rpartition('.')[2]
    if f'{path}\\' in _get_files(self):
        return f'{self.archive}\\{path}'


# Implicit directories will cause namespace import fail, add them here.
def _fix_up_directory(files, archive=None):
    def ensure_archive(path):
        nonlocal archive, filter
        archive = files[path][0][:-len(path)].rstrip('\\')
        filter = fix_up_1
        fix_up_1(path)
    def fix_up_0(path):
        nonlocal count
        while True:
            i = path.rfind('\\')
            if i < 0:
                return
            dirpath = path[:i+1]
            if dirpath in files:
                return
            path = path[:i]
            files[dirpath] = None  # ('\\'.join([archive, path]), *[0]*7)
            count += 1
    def fix_up_1(path):
        nonlocal filter
        fix_up_0(path)
        if '\\' in path:
            if count == 0:
                return 1  # quick finish
            filter = fix_up_0
    count = 0
    filter = archive is None and ensure_archive or fix_up_1
    for path in tuple(files):
        if filter(path):
            break
    if count:
        _verbose_msg('# zipextimporter: '
                    f'added {count} implicit directories in {archive!r}')
    return files

def _read_directory_fixed(archive):
    return _fix_up_directory(zipimport._read_directory_orig(archive), archive)

def _fix_up_read_directory():
    if not hasattr(zipimport, '_read_directory_orig'):
        zipimport._read_directory_orig = zipimport._read_directory
        try:
            for files in zipimport._zip_directory_cache.values():
                _fix_up_directory(files)
        except:
            del zipimport._read_directory_orig
        else:
            zipimport._read_directory = _read_directory_fixed
            _verbose_msg('# zipextimporter: `_fix_up_read_directory()` succeeded')


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
                try:
                    _fix_up_directory(self._files)
                except:
                    pass

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
                    loader = ExtensionFileLoader(fullname, mi.cached)
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
                search = mi.is_package and [_path_dirname(mi.path)] or None
                if mi.cached:
                    return spec_from_file_location(
                            fullname, mi.cached,
                            submodule_search_locations=search)
                spec = ModuleSpec(fullname, self.zipextimporter, origin=mi.path)
                spec.submodule_search_locations = search
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
    if (3, 8) < sys.version_info < (3, 14):
        _fix_up_read_directory()

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
        if not isinstance(module, str):
            raise ValueError(f'the module name MUST be a str, not {type(module)}')
        attrfunc(argsfunc and argsfunc(module) or module)


verbose = sys.flags.verbose

def _verbose_msg(msg, verbosity=1):
    if max(verbose, sys.flags.verbose) >= verbosity:
        print(msg, file=sys.stderr)

def set_verbose(i=1):
    '''Set verbose, the argument as same as built-in function int's.'''
    global verbose
    verbose = int(i)
