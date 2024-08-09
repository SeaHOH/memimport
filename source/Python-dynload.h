/*
  This module allows us to import Python API from dynamically loaded DLL.

  We shall patched PyAPI_FUNC and PyAPI_DATA in "pyport.h" to disable
  API import before compile codes, then anyhow dynamically load can works,
  and without defined functions ourselves, but exported variables still
  be defineded the following here.

  patch/diff:
    @@ -x,3 +x,12 @@
     #endif
     
    +#undef PyAPI_FUNC
    +#undef PyAPI_DATA
    +#ifdef PYTHON_DYNLOAD_H
    +#       define PyAPI_FUNC(RTYPE) extern RTYPE
    +#       define PyAPI_DATA(RTYPE) extern RTYPE
    +#else
    +#       define PyAPI_FUNC(RTYPE) RTYPE
    +#       define PyAPI_DATA(RTYPE) RTYPE
    +#endif
     #endif // Py_PYPORT_H

  Usage:
    `#include <Python.h>` in other files need be replaced with
    `#include "Python-dynload.h"`.

  Problems:
  //- We cannot use vararg functions that have no va_list counterpart.
  //- What about the flags or other data exported from Python?
  //- Error handling MUST be improved...
  - Should we use a python script to generate this code
    from function prototypes automatically?
*/

#include <Python.h>

#ifndef PYTHON_DYNLOAD_H
#define PYTHON_DYNLOAD_H

/*
  We have to #define Py_BUILD_CORE when we compile our stuff,
  then the exe doesn't try to link with pythonXY.lib, and also
  the following definitions compile.

  We use MyGetProcAddress to get the functions from the dynamically
  loaded python DLL, so it will work both with the DLL loaded from the
  file system as well as loaded from memory.
*/
#if defined(Py_BUILD_CORE) || !defined(STANDALONE)
#   define GetProcAddress MyGetProcAddress
#   include "MyLoadLibrary.h"
#endif

#ifdef IMPORT_FUNC
#   undef IMPORT_FUNC
#endif
#define IMPORT_FUNC(name) (FARPROC)name = GetProcAddress(hPyCore, #name)
#define IMPORT_DATA(name) (FARPROC)name##_Ptr = GetProcAddress(hPyCore, #name)
#define IMPORT_DATA_PTR(name) (void *)name = *((void **)GetProcAddress(hPyCore, #name))
#define DATA_PTR(type, name) type *name##_Ptr

#define Py_OptimizeFlag (*Py_OptimizeFlag_Ptr)

#else  // PYTHON_DYNLOAD_H

#undef DATA_PTR
#define DATA_PTR(type, name) extern type *name##_Ptr

#endif  // PYTHON_DYNLOAD_H

/***************************************************************************/
DATA_PTR(int, Py_OptimizeFlag);
/***************************************************************************/

#ifndef PYTHON_DYNLOAD_HC
#define PYTHON_DYNLOAD_HC

#include "Python-dynload.hc"

void
InitExports(void)
{
    static BOOL initialized = FALSE;

    if (initialized) {
        return;
    }
    initialized = TRUE;

    LoadPyCore();

    IMPORT_DATA(Py_OptimizeFlag);

    IMPORT_DATA_PTR(PyExc_SystemError);

    IMPORT_FUNC(PyArg_ParseTuple);
    IMPORT_FUNC(PyBytes_AsString);
    IMPORT_FUNC(PyModule_Create2);
    IMPORT_FUNC(PyObject_CallFunction);
    IMPORT_FUNC(PyUnicode_AsWideCharString);
}

#else  // PYTHON_DYNLOAD_HC

extern DWORD Py_Version_Hex;
extern WORD Py_Minor_Version;
extern void InitExports(void);

#endif  // PYTHON_DYNLOAD_HC

#ifdef GetProcAddress
#undef GetProcAddress
