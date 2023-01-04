memimporter for Python 3
========================

`memimporter` is a part of `py2exe`, which helps import Python extensions from
memory, e.g. extensions from Zip files or Web.

This repo via CI to build it as Python extensions, beacause the original has
been built into the py2exe runstubs, only run with script, no REPL.

Development of `py2exe` is hosted here: https://github.com/py2exe/py2exe.


Compatibility
-------------

Windows, CPython >= 3.6


Usage
-----

```python
import zipextimporter
import sys

sys.path.insert(0, 'path/to/libs.zip')
```

then

```python
zipextimporter.monkey_patch()  # recommend, only monkey patch `zipimport.zipimporter`
```

or

```python
zipextimporter.install()       # also, install to `sys.path_hooks` is still available
```

then

```python
import ext_mod_in_zip          # now, support __init__.pyd in packages

ext_mod_in_zip                 # <module 'ext_mod_in_zip' from 'path\\to\\libs.zip\\ext_mod_in_zip\\__init__.pyd'>
ext_mod_in_zip.__file__        # 'path\\to\\libs.zip\\ext_mod_in_zip\\__init__.pyd'>
ext_mod_in_zip.__loader__      # <ZipExtensionImporter object 'path\to\libs.zip\'>

import py_mod_in_zip

py_mod_in_zip                  # <module 'py_mod_in_zip' from 'path\\to\\libs.zip\\py_mod_in_zip\\__init__.py'>
py_mod_in_zip.__file__         # 'path\\to\\libs.zip\\py_mod_in_zip\\__init__.py'>
py_mod_in_zip.__loader__       # <zipimporter object 'path\to\libs.zip\'>
```
