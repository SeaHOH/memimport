// Need to define these to be able to use SetDllDirectory.
#define _WIN32_WINNT 0x0502
#define NTDDI_VERSION 0x05020000

#if (PY_VERSION_HEX < 0x030C0000) || !defined(STANDALONE)
#include <Python.h>
#endif
#include "_memimporter.h"

#include <windows.h>
#include <stdio.h>

static char module_doc[] =
"Importer which can load extension modules from memory";

#include "MyLoadLibrary.h"
#include "actctx.h"

#ifndef STANDALONE
#include "python-dynload.h"
#endif

/*
static int dprintf(char *fmt, ...)
{
	char Buffer[4096];
	va_list marker;
	int result;

	va_start(marker, fmt);
	result = vsprintf(Buffer, fmt, marker);
	OutputDebugString(Buffer);
	return result;
}
*/

#if (PY_VERSION_HEX >= 0x030C0000)

static PyObject *uid_name;
//extern _PyRuntimeState *_PyRuntime;

#endif

#if (PY_VERSION_HEX >= 0x03030000)

/* Magic for extension modules (built-in as well as dynamically
   loaded).  To prevent initializing an extension module more than
   once, we keep a static dictionary 'extensions' keyed by the tuple
   (module name, module name)  (for built-in modules) or by
   (filename, module name) (for dynamically loaded modules), containing these
   modules.  A copy of the module's dictionary is stored by calling
   _PyImport_FixupExtensionObject() immediately after the module initialization
   function succeeds.  A copy can be retrieved from there by calling
   _PyImport_FindExtensionObject().

   Modules which do support multiple initialization set their m_size
   field to a non-negative number (indicating the size of the
   module-specific state). They are still recorded in the extensions
   dictionary, to avoid loading shared libraries twice.
*/

/* c:/users/thomas/devel/code/cpython-3.4/Python/importdl.c 73 */

int do_import(FARPROC init_func, const char *modname, PyObject *spec, PyObject **mod)
{
	int res;
	PyModInitFunction p;
	PyObject *m = NULL, *name = NULL, *path = NULL, *usname = NULL;
	struct PyModuleDef *def;
	const char *oldcontext;

	name = PyUnicode_FromString(modname);
	if (name == NULL) {
		goto error;
	}

	path = PyObject_GetAttrString(spec, "origin");
	if (path == NULL) {
		goto error;
	}

	PyObject *modules = PyImport_GetModuleDict();
	if (PyMapping_HasKeyString(modules, modname)) {
		res = 0;
		goto finalize;
	}

	if (init_func == NULL) {
		PyObject *msg = PyUnicode_FromFormat("dynamic module does not define "
						     "init function (PyInit_%s)",
						     modname);
		if (msg != NULL) {
			PyErr_SetImportError(msg, name, NULL);
			Py_DECREF(msg);
		}
		goto error;
	}

	p = (PyModInitFunction)init_func;

	/* Package context is needed for single-phase init */
	oldcontext = _PyImport_SwapPackageContext(modname);
	fprintf(stderr, "oldcontext: %s\n", oldcontext);
	m = _PyImport_InitFunc_TrampolineCall(p);
	fprintf(stderr, "lastcontext: %s\n", _PyImport_SwapPackageContext(oldcontext));


	if (PyErr_Occurred()) {
		goto error;
	}

	/* multi-phase initialization - PEP 489 */
    if (PyObject_TypeCheck(m, &PyModuleDef_Type)) {
		*mod = PyModule_FromDefAndSpec((PyModuleDef*)m, spec);
		res = 2;
		goto finalize;
    }

	/* fall back to single-phase initialization */

	#if (PY_VERSION_HEX >= 0x030C0000)

	if (_PyImport_CheckSubinterpIncompatibleExtensionAllowed(modname) < 0) {
		goto error;
	}

	#endif

	usname = PyUnicode_AsEncodedString(name, "ascii", NULL);
	if (usname == NULL) {
		/* don't allow legacy init for non-ASCII module names */
		PyErr_Clear();
		goto error;
	}

	/* Remember pointer to module init function. */
	def = PyModule_GetDef(m);
	if (def == NULL) {
		PyObject *msg = PyUnicode_FromFormat(
			"initialization of %s did not return an extension module",
			modname);
		if (msg) {
			PyErr_SetObject(PyExc_SystemError, msg);
			Py_DECREF(msg);
		}
		goto error;
	}
	def->m_base.m_init = p;

	//#if (PY_VERSION_HEX >= 0x030C0000)
	//
	///* A hack instead of _PyImport_SwapPackageContext & _PyImport_ResolveNameWithPackageContext
	// *
	// * Origin:
	// *   _PyImport_SwapPackageContext()
	// *   call <module init func>
	// *     <module init func> -> PyModule_Create() -> PyModule_Create2() -> PyModule_CreateInitialized()
	// *       PyModule_CreateInitialized() -> _PyImport_ResolveNameWithPackageContext()
	// *       PyModule_CreateInitialized() -> PyModule_New() -> PyModule_NewObject() -> module_init_dict()
	// *         module_init_dict(): set <module attribute __name__>
	// *         module_init_dict(): set <module struct member md_name>
	// *   _PyImport_SwapPackageContext()
	// *
	// * Hack:
	// *   call <module init func>
	// *     ...
	// *   re-set <module attribute __name__>
	// *   re-set <module struct member md_name>
	// */
	//PyModuleObject *md = (PyModuleObject *)m;
	//if (strcmp(PyUnicode_AsUTF8(md->md_name), modname) != 0) {
	//	if (PyDict_SetItem(md->md_dict, uid_name, name) != 0) {
	//		goto error;
	//	}
	//	Py_XDECREF(md->md_name);
	//	Py_XSETREF(md->md_name, Py_NewRef(name));
	//}
	//
	//#endif

	#if (PY_VERSION_HEX >= 0x03070000)

	res = _PyImport_FixupExtensionObject(m, name, path, modules);

	#else

	res = _PyImport_FixupExtensionObject(m, name, path);

	#endif

	if (res < 0) {
		goto error;
	}

	Py_DECREF(name);
	Py_DECREF(path);
	Py_DECREF(usname);
	return res;

error:
	res = -1;

finalize:
	Py_XDECREF(m);
	Py_XDECREF(name);
	Py_XDECREF(path);
	Py_XDECREF(usname);
	return res;
}

#else
# error "Python 3.0, 3.1, and 3.2 are not supported"

#endif

#ifndef STANDALONE
extern wchar_t dirname[]; // executable/dll directory
#endif

static PyObject *
import_module(PyObject *self, PyObject *args)
{
	const char *initfuncname;
	const char *modname;
	const char *pathname;
	HMODULE hmem;
	FARPROC init_func;

	ULONG_PTR cookie = 0;
	PyObject *findproc;
	PyObject *spec;

	int imp_res = -1;
	struct PyModuleDef *def;
	PyObject *state;

	//	MessageBox(NULL, "ATTACH", "NOW", MB_OK);
	//	DebugBreak();

	/* code, initfuncname, fqmodulename, path, spec */
	if (!PyArg_ParseTuple(args, "sssOO:import_module",
						  &modname, &pathname,
						  &initfuncname,
						  &findproc,
						  &spec))
		return NULL;

	PyObject *m = PyModule_New(modname);

	cookie = _My_ActivateActCtx(); // some windows manifest magic...
	/*
	 * The following problem occurs when we are a ctypes COM dll server
	 * build with bundle_files == 1 which uses dlls that are not in the
	 * library.zip. sqlite3.dll is such a DLL - py2exe copies it into the
	 * exe/dll directory.
	 *
	 * The COM dll server is in some directory, but the client exe is
	 * somewhere else.  So, the dll server directory is NOT on th default
	 * dll search path.
	 *
	 * We use SetDllDirectory(dirname) to add the dll server directory to
	 * the search path. Which works fine.  However, SetDllDirectory(NULL)
	 * restores the DEFAULT dll search path; so it may remove directories
	 * the the client has installed.  Do we have to call GetDllDirectory()
	 * and save the result to be able to restore the path afterwards
	 * again?
	 *
	 * Best would probably be to use AddDllDirectory / RemoveDllDirectory
	 * but these are not even available by default on windows7...
	 *
	 * Are there other ways to allow loading of these dlls?  Application manifests?
	 *
	 * What about this activation context stuff?
	 *
	 * Note: py2exe 0.6 doesn't have this problem since it packs the
	 * sqlite3.dll into the zip-archve when bundle_files == 1, but we want
	 * to avoid that since it fails for other dlls (libiomp5.dll from
	 * numpy is such an example).
	 */
	#ifndef STANDALONE
	BOOL res = SetDllDirectoryW(dirname); // Add a directory to the search path
	#endif

	hmem = MyLoadLibrary(pathname, NULL, 0, findproc);
	#ifndef STANDALONE
	if (res)
		SetDllDirectory(NULL); // restore the default dll directory search path
	#endif
	_My_DeactivateActCtx(cookie);

	if (!hmem) {
		char *msg;
		PyObject *error;
		FormatMessageA(FORMAT_MESSAGE_ALLOCATE_BUFFER | FORMAT_MESSAGE_FROM_SYSTEM,
					   NULL,
					   GetLastError(),
					   MAKELANGID(LANG_NEUTRAL, SUBLANG_DEFAULT),
					   (void *)&msg,
					   0,
					   NULL);
		msg[strlen(msg)-2] = '\0';
		error = PyUnicode_FromFormat("MemoryLoadLibrary failed loading %s: %s (%d)",
						pathname, msg, GetLastError());
		if (error) {
			PyErr_SetObject(PyExc_ImportError, error);
			Py_DECREF(error);
		} else {
			PyErr_Clear();
			PyErr_SetString(PyExc_ImportError, "foobar");
		}
		LocalFree(msg);
		return NULL;
	}

	init_func = MyGetProcAddress(hmem, initfuncname);
	imp_res = do_import(init_func, modname, spec, &m);

	if (imp_res < 0) {
		MyFreeLibrary(hmem);
		return NULL;
	} else if (imp_res == 2) {
		def = PyModule_GetDef(m);
		state = PyModule_GetState(m);
		if (state == NULL) {
			PyModule_ExecDef(m, def);
		}
		return m;
	}

	Py_DECREF(m);

	/* Retrieve from sys.modules */
	return PyImport_ImportModule(modname);
}

static PyObject *
get_verbose_flag(PyObject *self, PyObject *args)
{
	#if (PY_VERSION_HEX >= 0x030C0000)

	return PyLong_FromLong(_Py_GetConfig()->verbose);

	#else

	return PyLong_FromLong(Py_VerboseFlag);

	#endif
}

static PyMethodDef methods[] = {
	{ "import_module", import_module, METH_VARARGS,
	  "import_module(modname, pathname, initfuncname, finder, spec) -> module" },
	{ "get_verbose_flag", get_verbose_flag, METH_NOARGS,
	  "Return the Py_Verbose flag" },
	{ NULL, NULL }, /* Sentinel */
};

static struct PyModuleDef moduledef = {
	PyModuleDef_HEAD_INIT,
	"_memimporter", /* m_name */
	module_doc,     /* m_doc */
	-1,             /* m_size */
	methods,        /* m_methods */
	NULL,           /* m_reload */
	NULL,           /* m_traverse */
	NULL,           /* m_clear */
	NULL,           /* m_free */
};


PyMODINIT_FUNC PyInit__memimporter(void)
{
	#if (PY_VERSION_HEX >= 0x030C0000)

	uid_name = PyUnicode_FromString("__name__");

	#ifdef STANDALONE

	PyObject *pmodname = PyUnicode_FromString("sys");
	PyObject *pattrname = PyUnicode_FromString("dllhandle");
	PyObject *sys = PyImport_Import(pmodname);
	PyObject *dllhandle = PyObject_GetAttr(sys, pattrname);
	HMODULE hmod_pydll = (HMODULE)PyLong_AsVoidPtr(dllhandle);
	Py_DECREF(pattrname);
	Py_DECREF(pmodname);
	Py_DECREF(sys);
	Py_DECREF(dllhandle);

	//fprintf(stderr, "dllhandle: %s\n", hmod_pydll);

	#define DL_FUNC(name) (FARPROC)name = GetProcAddress(hmod_pydll, #name)
	#define DL_DATA_PTR(name, myname) (FARPROC)myname = GetProcAddress(hmod_pydll, #name)

	_PyRuntimeState *_My_PyRuntime;
	DL_DATA_PTR(_PyRuntime, _My_PyRuntime);

	fprintf(stderr, "_PyRuntime: %s %s\n", &(_PyRuntime.imports.pkgcontext), &(_My_PyRuntime->imports.pkgcontext));
	fprintf(stderr, "_PyRuntime: %d %d\n", *(int*)(&(_PyRuntime.imports.pkgcontext)), *(int*)(&(_My_PyRuntime->imports.pkgcontext)));
	#define SEARCH_RANGE 300
	#define SEARCH_STEP 1
	#define SEARCH_LENGHT 12
	int offset = -SEARCH_RANGE, index = 0, pi;
	_Py_PackageContext = _My_PyRuntime->imports.pkgcontext;
	char *mn = "_memimporter";
	const char *p;
	do {
		p = *(const char**)(&(_My_PyRuntime->imports.pkgcontext) + offset);
		index = 0;
		pi = *(int*)(&p);
		//fprintf(stderr, "p: %d\n", pi);
		//fprintf(stderr, "offset: %d\n", offset);
		if (pi > 100000 || pi < -100000 ) {
			fprintf(stderr, "offset: %d | p: %d, %s\n", offset, pi, p);
		}
		//while ( (pi > 100000 || pi < -100000 ) && index < SEARCH_LENGHT ) {
		//	if (*(char*)(mn+index) != *(char*)(p+index)) {
		//		index = SEARCH_LENGHT;
		//	}
		//	index += SEARCH_STEP;
		//}
		//fprintf(stderr, "index: %d\n", index);
		//if (index == SEARCH_LENGHT) {
		//	_Py_PackageContext = p;
		//	offset = SEARCH_RANGE;
		//}
		offset += SEARCH_STEP;
	} while ( offset <= SEARCH_RANGE );
	fprintf(stderr, "PKGCONTEXTb: %s\n", _Py_PackageContext);
	//
	//#endif
	#endif

	return PyModule_Create(&moduledef);
}
