"""Print exactly what Windows handed to this process: the raw command line and the CRT-parsed argv.
Output is one ASCII line: PROBE {"raw": ..., "argv": [...]} so no console encoding can corrupt it."""
import ctypes, json, sys

GetCommandLineW = ctypes.windll.kernel32.GetCommandLineW
GetCommandLineW.restype = ctypes.c_wchar_p
print("PROBE " + json.dumps({"raw": GetCommandLineW(), "argv": sys.argv[1:]}, ensure_ascii=True), flush=True)
