| category | flagged / total | lintable |
|---|---|---|
| genuine-program-error | 94/115 | no |
| exitcode-misread/hidden-error | 80/94 | yes |
| encoding-unicode | 77/89 | yes |
| file-not-found/state | 17/42 | no |
| too-long (cmdline/MAX_PATH) | 10/39 | yes |
| command-not-found/PATH | 22/32 | yes |
| permission/sandbox-denied | 17/29 | no |
| other | 3/15 | no |
| path-translation/backslash | 4/13 | yes |
| user-interrupted/rejected | 3/11 | no |
| ps-parse-error | 5/6 | yes |
| file-locked/access-denied | 2/6 | no |
| ps-quoting-native-args | 6/6 | yes |
| wrong-tool-flags | 3/4 | yes |
| ps-stderr-nativecommanderror | 1/2 | yes |
| ps-alias-collision/unix-ism | 2/2 | yes |
| path-spaces-arabic | 1/1 | yes |
| ps7-feature-in-ps5.1 | 1/1 | yes |

**Lintable Windows-caused failures flagged: 212/289 (73%)**
**Successful commands with an ERROR flag: 5/600 (0.8%); with a WARN flag: 161/600 (26.8%)**

Rule hits on failures: X001 121, PS017 118, PS005 92, PS015 67, PS014 44, PS013 13, SH010 11, PS016 8, PS021 8, PS020 7, PS009 3, PS019 3, X006 2, PS006 2, SH002 2, SH009 2, SH008 1, PS002 1, PS001 1, X003 1, PS003 1, X002 1
Rule hits on successes: X001 97, PS017 66, SH010 45, PS015 34, PS005 21, PS013 12, PS014 11, PS020 2, X003 1, SH001 1, SH005 1, SH009 1, SH002 1, X006 1, PS008 1