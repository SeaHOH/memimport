typedef PyObject *(*PyModInitFunction)(void);

#if (PY_VERSION_HEX >= 0x030B0000) && defined(__EMSCRIPTEN__) && defined(PY_CALL_TRAMPOLINE)
/* Python/import.c */
#include <emscripten.h>
EM_JS(PyObject*, _PyImport_InitFunc_TrampolineCall, (PyModInitFunction func), {
    return wasmTable.get(func)();
});
#else
/* Python/importdl.h */
#define _PyImport_InitFunc_TrampolineCall(func) (func)()
#endif

#if (PY_VERSION_HEX >= 0x030C0000)

/* Include/internal/pycore_moduleobject.h */
typedef struct {
    PyObject ob_base;
    PyObject *md_dict;
    PyModuleDef *md_def;
    void *md_state;
    PyObject *md_weaklist;
    PyObject *md_name;
} PyModuleObject;

PyAPI_FUNC(int) _PyImport_CheckSubinterpIncompatibleExtensionAllowed(
    const char *name);
#endif

#if (PY_VERSION_HEX >= 0x030C0000)
//#define PKGCONTEXT (_PyRuntimeC.imports.pkgcontext)
const char *pkgcontext = "";
#define PKGCONTEXT pkgcontext
#else
#define PKGCONTEXT _Py_PackageContext
#endif

inline const char *
_PyImport_SwapPackageContext(const char *newcontext)
{
    #if (PY_VERSION_HEX >= 0x03070000)
    const char *oldcontext = PKGCONTEXT;
    PKGCONTEXT = newcontext;
    #else
    const char *oldcontext = (const char *)PKGCONTEXT;
    PKGCONTEXT = (char *)newcontext;
    #endif

    return oldcontext;
}

