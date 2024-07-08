r"""memimport - an import function which can import extension modules
from memory without write them to the file system.

The _memimporter module is part of the py2exe package.

Overview
========

It uses the _memimporter extension which uses code from Joachim
Bauch's MemoryModule library. This library emulates the win32 api
function LoadLibrary.

memimport provides a loader MemExtensionFileLoader for basic usage.
Users should write a custom loader for specific requirement,
just likes zipextimporter does.

Sample usage
============

>>> from memimport import memimport
>>> data = some_gen(*any_args)  # read from Disk or Web
>>> mem_mod = memimport(data=data, fullname="mem_mod")
>>> print(mem_mod)
<module 'mem_mod' from '<unknown>'>
>>> mem_mod.__file__
'<unknown>'
>>> mem_mod.__loader__
<memimport.MemExtensionFileLoader object at 0x0000000001132E90>
>>> # Reloading will not works:
>>> import importlib
>>> importlib.reload(mem_mod)
'Some error message'
>>>

"""

import sys
from _frozen_importlib import ModuleSpec
from _frozen_importlib_external import ExtensionFileLoader

# _memimporter is a module built into the py2exe runstubs,
# or a standalone module of memimport.
from _memimporter import import_module


__version__ = '0.13.0.0.post8'

__all__ = [
    'memimport_from_data', 'memimport_from_loader', 'memimport_from_spec',
    'memimport', 'set_verbose'
]


class MemExtensionFileLoader(ExtensionFileLoader):

    def __init__(self, name, path, data):
        self.name = name
        self.path = path
        self.data = data

    def create_module(self, spec):
        pass

    def exec_module(self, module):
        pass

    def load_module(self, fullname):
        pass

    def get_data(self, path):
        try:
            if callable(self.data):
                return self.data(path)
        except TypeError as e:
            if 'takes 0 positional arguments' not in str(e):
                raise
        if path in (self.name, self.path):
            if callable(self.data):
                return self.data()
            return self.data
        raise OSError(0, '', path)


def memimport_from_data(fullname, data, is_package=None):
    return memimport(data=data, fullname=fullname, is_package=is_package)

def memimport_from_loader(fullname, loader, data=None, is_package=None):
    return memimport(data=data, loader=loader, fullname=fullname, is_package=is_package)

def memimport_from_spec(spec, data=None, is_package=None):
    return memimport(data=data, spec=spec, is_package=is_package)


def memimport(data=None, spec=None,
              fullname=None, loader=None, origin=None, is_package=None):
    if spec:
        if not fullname:
            fullname = spec.name
        if is_package and spec.submodule_search_locations is None:
            spec.submodule_search_locations = []
    elif fullname:
        if not origin:
            try:
                origin = loader.get_filename(fullname)
            except (NameError, AttributeError):
                if data is None:
                    raise ValueError(
                        f'loader {loader} has no `get_filename` attribute, '
                        'so argument "data" or "origin" MUST be provided.'
                        )
                origin = '<unknown>'
        origin = origin.replace('/', '\\')
        if loader is None:
            if data is None:
                if not _path_isfile(origin):
                    raise ValueError('argument "loader" MUST be provided, or '
                                     'argument "origin" MUST be a locale file.')
                loader = ExtensionFileLoader(fullname, origin)
            else:
                loader = MemExtensionFileLoader(fullname, origin, data)
        if is_package is None:
            is_package = loader.is_package(fullname)
        spec = ModuleSpec(fullname, loader, origin=origin, is_package=is_package)
    else:
        raise ValueError('argument "spec" or "fullname" MUST be provided.')

    loader = spec.loader
    origin = spec.origin
    path = origin == '<unknown>' and fullname or origin
    spec._set_fileattr = origin != '<unknown>'  # has_location, use for reload
    sub_search = spec.submodule_search_locations
    if sub_search is not None and not sub_search:
        sub_search.append(origin.rpartition('\\')[0])

    initname = export_hook_name(fullname)
    mod = import_module(fullname, path, initname, loader.get_data, spec)
    # init attributes
    mod.__spec__ = spec
    mod.__file__ = origin
    mod.__loader__ = loader
    mod.__package__ = spec.parent
    if sub_search is not None:
        mod.__path__ = sub_search
    _verbose_msg(f'import {fullname} # loaded from {origin}')
    return mod


# PEP 489 multi-phase initialization / Export Hook Name
def export_hook_name(fullname):
    name = fullname.rpartition('.')[2]
    try:
        name.encode('ascii')
    except UnicodeEncodeError:
        return 'PyInitU_' + name.encode('punycode') \
                                .decode('ascii').replace('-', '_')
    else:
        return 'PyInit_' + name


verbose = sys.flags.verbose

def _verbose_msg(msg, verbosity=1):
    if max(verbose, sys.flags.verbose) >= verbosity:
        print(msg, file=sys.stderr)

def set_verbose(i=1):
    '''Set verbose, the argument as same as built-in function int's.'''
    global verbose
    verbose = int(i)


################################################################################
# Replacement for functions in non-built-in/non-frozen modules
################################################################################

from _frozen_importlib_external import \
        _path_join, _path_stat, _path_isfile, _path_isdir

def _path_split(path):
    '''Replacement for os.path.split.'''
    i = path.rfind('\\')
    if i < 0:
        return '', path
    return path[:i], path[i+1:]

def _path_dirname(path):
    '''Replacement for os.path.dirname.'''
    return _path_split(path)[0]

def _path_basename(path):
    '''Replacement for os.path.basename.'''
    return _path_split(path)[1]

def _path_exists(path):
    '''Replacement for os.path.exists.'''
    try:
        _path_stat(path)
    except (OSError, ValueError):
        return False
    return True


from nt import mkdir as _mkdir

def _makedirs(name, mode=0o777):
    '''Replacement for os.makedirs.'''
    head, tail = _path_split(name)
    if not tail:
        head, tail = _path_split(head)
    if head and tail and not _path_exists(head):
        try:
            _makedirs(head)
        except FileExistsError:
            pass
        if tail == '.':           # xxx/newdir/. exists if xxx/newdir exists
            return
    try:
        _mkdir(name, mode)
    except OSError:
        if not _path_isdir(name):
            raise
