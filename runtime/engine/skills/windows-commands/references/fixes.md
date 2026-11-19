| shell | case | typed | note | got | ok |
|---|---|---|---|---|---|
| ps51 | empty | `'""'` | pass two double quotes inside a single-quoted literal | `[""]` | ✅ |
| ps51 | inner_dq | `'say \"hi\"'` | backslash-escape inner double quotes | `["say \"hi\""]` | ✅ |
| ps51 | py_code_dq | `'print(\"ok\")'` | backslash-escape inner double quotes | `["print(\"ok\")"]` | ✅ |
| ps51 | py_code_sq | `"print('ok')"` | or use single quotes inside the code | `["print('ok')"]` | ✅ |
| ps51 | json | `'{\"k\": \"v\"}'` | backslash-escape inner double quotes | `["{\"k\": \"v\"}"]` | ✅ |
| ps51 | trailing_bs | `'C:\dir with space\\'` | double the trailing backslash | `["C:\\dir with space\\"]` | ✅ |
| ps51 | dashdash_pct_var | `$a` | pass via variable ($a='--%') | `[]` | ❌ |
| ps51 | dashdash_pct_bt | `'-`-%'` | nope: backtick is literal inside single quotes (control) | `["-`-%"]` | ❌ |
| ps51 | lone_dq | `'\"'` | backslash-escape | `["\""]` | ✅ |
| ps51 | stop_parsing | `--% "say \"hi\"" x` | --% then raw CRT text | `["say \"hi\"", "x"]` | ✅ |
| cmd_batch | inner_dq | `"say \"hi\""` | CRT escape \" inside the quotes | `["say \"hi\""]` | ✅ |
| cmd_batch | json | `"{\"k\": \"v\"}"` | CRT escape | `["{\"k\": \"v\"}"]` | ✅ |
| cmd_batch | trailing_bs | `"C:\dir with space\\"` | double trailing backslash | `["C:\\dir with space\\"]` | ✅ |
| cmd_batch | percent_lit_batch | `"100%%"` | %% in a batch file | `["100%"]` | ✅ |
| cmd_batch | percent_var_batch | `"%%PATH%%"` | %% in a batch file | `["%PATH%"]` | ✅ |
| cmd_batch | dashdash_pct | `"--%%"` | %% in a batch file | `["--%"]` | ✅ |
| cmd_batch | amp_unquoted_caret | `a^&b` | caret-escape when not quoted | `["a&b"]` | ✅ |
| gitbash | posix_flag_env | `'/c'` | MSYS_NO_PATHCONV=1 | `["/c"]` | ✅ |
| gitbash | posix_flag_dbl | `'//c'` | double leading slash | `["/c"]` | ✅ |
| gitbash | posix_path_env | `'/tmp/x.txt'` | MSYS_NO_PATHCONV=1 | `["/tmp/x.txt"]` | ✅ |
| gitbash | eq_posix_excl | `'--out=/tmp/y'` | MSYS2_ARG_CONV_EXCL=--out= | `["--out=/tmp/y"]` | ✅ |
| gitbash | unquoted_winpath | `C:\Users\x` | control: unquoted backslashes in bash | `["C:Usersx"]` | ❌ |
| gitbash | dq_winpath | `"C:\Users\x"` | double-quoted backslashes in bash | `["C:\\Users\\x"]` | ✅ |
| gitbash | fwd_winpath | `'C:/Users/x'` | forward slashes | `["C:/Users/x"]` | ✅ |