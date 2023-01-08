memimport for Python 3
========================

![operating system](https://img.shields.io/badge/OS-Windows-success)
[![Python implementation](https://img.shields.io/badge/implementation-CPython-success)](https://www.python.org/downloads/)
[![Python versions](https://img.shields.io/pypi/pyversions/memimport)](https://www.python.org/downloads/)
[![licenses](https://img.shields.io/badge/license-MIT_|_MPL2-blue)](https://github.com/SeaHOH/memimport/blob/master/LICENSE.txt)
![development status](https://img.shields.io/pypi/status/memimport)  
[![latest tag](https://img.shields.io/github/v/tag/SeaHOH/memimport)](https://github.com/SeaHOH/memimport/tags)
[![build status](https://img.shields.io/github/actions/workflow/status/SeaHOH/memimport/CI.yml)](https://github.com/SeaHOH/memimport/actions/workflows/CI.yml)
[![latest version](https://img.shields.io/pypi/v/memimport)](https://pypi.org/project/memimport/)
[![package format](https://img.shields.io/pypi/format/memimport)](https://pypi.org/project/memimport/#files)
[![monthly downloads](https://img.shields.io/pypi/dm/memimport)](https://pypi.org/project/memimport/#files)

`memimport` is a part of `py2exe`, which helps import Python extensions from
memory, e.g. extensions from Zip files or Web.

This repo via CI to build it as Python extensions, beacause the original has
been built into the py2exe runstubs, only run with script, no REPL.

Development of `memimport` is hosted here: https://github.com/SeaHOH/memimport.  
Development of `py2exe` is hosted here: https://github.com/py2exe/py2exe.


Installation
------------

    pip install memimport


Usage
-----

```python
import zipextimporter
import sys

sys.path.insert(0, 'path/to/libs.zip')
```

then

```python
zipextimporter.install()            # default, prefer `hook=False`, `hook=True` as fallback
```

or

```python
zipextimporter.install(hook=False)  # better compatibility, monkey patch `zipimport.zipimporter`
                                    # equal to empty argument, `hook=True` as fallback
```

or

```python
zipextimporter.install(hook=True)   # not recommend, install to `sys.path_hooks`
```

then

```python
import ext_mod_in_zip      # now, support __init__.pyd in packages

ext_mod_in_zip             # <module 'ext_mod_in_zip' from 'path\\to\\libs.zip\\ext_mod_in_zip\\__init__.pyd'>
ext_mod_in_zip.__file__    # 'path\\to\\libs.zip\\ext_mod_in_zip\\__init__.pyd'>
ext_mod_in_zip.__loader__  # <ZipExtensionImporter object 'path\to\libs.zip\'>

import py_mod_in_zip

py_mod_in_zip              # <module 'py_mod_in_zip' from 'path\\to\\libs.zip\\py_mod_in_zip\\__init__.py'>
py_mod_in_zip.__file__     # 'path\\to\\libs.zip\\py_mod_in_zip\\__init__.py'>
py_mod_in_zip.__loader__   # <zipimporter object 'path\to\libs.zip\'>
```

More usage see source or use help function.
