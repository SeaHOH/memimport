#ifndef Py_BUILD_CORE

/* internal/pycore_moduleobject.h */
typedef struct {
    PyObject ob_base;
    PyObject *md_dict;
    PyModuleDef *md_def;
    void *md_state;
    PyObject *md_weaklist;
    PyObject *md_name;
} PyModuleObject;

#endif
