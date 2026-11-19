| test | result | ok |
|---|---|---|
| ps1 without BOM: length of 'مرحبا' (5 expected) | `10` | ❌ |
| ps1 with BOM: length of 'مرحبا' (5 expected) | `5` | ✅ |
| PS 5.1 redirect > | `UTF-16LE with BOM (ff fe 45 06 31 06 2d 06 28 06 27 06 ... 16 bytes)` | ❌ |
| PS 5.1 Out-File (default) | `UTF-16LE with BOM (ff fe 45 06 31 06 2d 06 28 06 27 06 ... 16 bytes)` | ❌ |
| PS 5.1 Set-Content (default) | `ANSI, Arabic lost as '?' (3f 3f 3f 3f 3f 0d 0a ... 7 bytes)` | ❌ |
| PS 5.1 Set-Content -Encoding UTF8 | `UTF-8 with BOM (ef bb bf d9 85 d8 b1 d8 ad d8 a8 d8 ... 15 bytes)` | ✅ |
| PS 5.1 Out-File -Encoding utf8 | `UTF-8 with BOM (ef bb bf d9 85 d8 b1 d8 ad d8 a8 d8 ... 15 bytes)` | ✅ |
| PS 5.1 [IO.File]::WriteAllText (no BOM) | `UTF-8 without BOM (d9 85 d8 b1 d8 ad d8 a8 d8 a7 ... 10 bytes)` | ✅ |
| PS 5.1 pipe Arabic -> native stdin (default $OutputEncoding) | `3f3f3f3f3f0d0a` | ❌ |
| PS 5.1 capture python UTF-8 output into a variable | `9496,224,9578,9618,9578,161,9578,191,9578,186` | ❌ |
| python -I print Arabic to a pipe | `UnicodeEncodeError: 'charmap' codec can't encode characters in position 0-4: cha` | ❌ |
| python -I -X utf8 print Arabic to a pipe | `ok utf-8` | ✅ |
| python (no flags, PYTHONUTF8 unset) print Arabic to a pipe | `UnicodeEncodeError: 'charmap' codec can't encode characters in position 0-4: cha` | ❌ |