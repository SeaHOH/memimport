import sys

IncludeDir = rf'{sys.prefix}\Include'

ends_replace_entries = [
['pyport.h', 26,
b'''
#undef PyAPI_FUNC
#undef PyAPI_DATA
#ifdef PYTHON_DYNLOAD_H
#       define PyAPI_FUNC(RTYPE) extern RTYPE
#       define PyAPI_DATA(RTYPE) extern RTYPE
#else
#       define PyAPI_FUNC(RTYPE) RTYPE
#       define PyAPI_DATA(RTYPE) RTYPE
#endif
#endif /* Py_PYPORT_H */
''']
]

def ends_replace(f, l, s, p):
    with open(rf'{IncludeDir}\{f}', 'r+b') as f:
        f.seek(-len(s), 2)
        _s = f.read()
        if _s == s:
            if not p:
                f.seek(-len(s), 2)
                f.truncate()
                f.write(s[-l:])
            return True
        if _s[-l:] == s[-l:]:
            if p:
                f.seek(-l, 2)
                f.write(s)
            return True
    return False

def patch():
    for entry in ends_replace_entries:
        print('patch', entry[0],
              ends_replace(*entry, True) and 'succeeded' or 'failed')

def unpatch():
    for entry in ends_replace_entries:
        print('uppatch', entry[0],
              ends_replace(*entry, False) and 'succeeded' or 'failed')

if __name__ == '__main__':
    patch()
