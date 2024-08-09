/*
  This file has been included in "Python-dynload.h",
  DON'T compile it directly!!!
*/
#include <windows.h>
#include <stdio.h>

static wchar_t PyCore[20];
static HMODULE hPyCore;
DWORD Py_Version_Hex = 0;
WORD Py_Minor_Version = 0;

static inline void
_LoadPyCore(WORD py_minor_version)
{
#ifdef _DEBUG
    swprintf(PyCore, L"python3%d_d.dll", py_minor_version);
#else
    swprintf(PyCore, L"python3%d.dll", py_minor_version);
#endif
    hPyCore = GetModuleHandleW(PyCore);
}

static void
LoadPyVersion(HMODULE hPyDll)
{
    if (hPyDll == NULL)
        return;

    FARPROC address = GetProcAddress(hPyDll, "Py_Version");
    if (address == NULL) {
        /* version <= 3.10 */
        address = GetProcAddress(hPyDll, "Py_GetVersion");
        if (address != NULL) {
            typedef char *(*Py_GetVersionFunction)(void);
            char *strversion = ((Py_GetVersionFunction)address)();
            WORD version = 0;
            while (*strversion != ' ') {
                if (*strversion >= '0' && *strversion <= '9') {
                    version = version * 10 + (WORD)(*strversion - '0');
                } else {
                    Py_Version_Hex <<= 8;
                    Py_Version_Hex |= version << 8;
                    version = 0;
                    if (*strversion != '.') {
                        Py_Version_Hex |= ((WORD)(*strversion - 'a') + 10) << 4;
                        Py_Version_Hex |= (WORD)(strversion[1] - '0');
                        break;
                    }
                }
                strversion++;
            }
            if (*strversion == ' ') {
                Py_Version_Hex <<= 8;
                Py_Version_Hex |= 0xF0;
            }
        }
    } else {
        /* version >= 3.11 */
        Py_Version_Hex = *(*int)address;
    }
    Py_Minor_Version = Py_Version_Hex >> 16 & 0xFF;
}

static void
LoadPyCore(void)
{
    WORD py_minor_version;

#ifdef _DEBUG
    LoadPyVersion(GetModuleHandleW(L"python3_d.dll"));
#else
    LoadPyVersion(GetModuleHandleW(L"python3.dll"));
#endif
    if (Py_Minor_Version) {
        _LoadPyCore(Py_Minor_Version);
        goto done;
    }

    for (py_minor_version=3; py_minor_version<=14; py_minor_version++) {
        _LoadPyCore(py_minor_version);
        if (hPyCore) {
            LoadPyVersion(hPyCore);
            goto done;
        }
    }
    return;
done:
    SetLastError(0);
}
