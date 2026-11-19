| case | intended | python_list | ps51_literal | cmd_batch | cmd_c_line | gitbash_literal |
|---|---|---|---|---|---|---|
| space | `"hello world"` | ✅ | ✅ | ✅ | ✅ | ✅ |
| empty | `""` | ✅ | ❌ [] | ✅ | ✅ | ✅ |
| inner_dq | `"say \"hi\""` | ✅ | ❌ ["say hi"] | ❌ ["say hi"] | ❌ ["say hi"] | ✅ |
| py_code_dq | `"print(\"ok\")"` | ✅ | ❌ ["print(ok)"] | ❌ ["print(ok)"] | ❌ ["print(ok)"] | ✅ |
| json | `"{\"k\": \"v\"}"` | ✅ | ❌ ["{k: v}"] | ❌ ["{k: v}"] | ❌ ["{k: v}"] | ✅ |
| trailing_bs | `"C:\\dir with space\\"` | ✅ | ❌ ["C:\\dir with space\""] | ❌ ["C:\\dir with space\""] | ❌ ["C:\\dir with space\""] | ✅ |
| bs_dq | `"a\\\"b"` | ✅ | ❌ ["a\"b"] | ❌ ["a\"b"] | ❌ ["a\"b"] | ✅ |
| percent_var | `"%PATH%"` | ✅ | ✅ | ❌ ["C:\\Users\\<user>\\bin;C:\\Program Files\\Git\\ucrt64\\bin; | ❌ ["C:\\Users\\<user>\\bin;C:\\Program Files\\Git\\ucrt64\\bin; | ✅ |
| percent_lit | `"100%"` | ✅ | ✅ | ❌ ["100"] | ✅ | ✅ |
| bang | `"!x!"` | ✅ | ✅ | ✅ | ✅ | ✅ |
| amp_pipe | `"a&b|c"` | ✅ | ✅ | ✅ | ✅ | ✅ |
| caret | `"a^b"` | ✅ | ✅ | ✅ | ✅ | ✅ |
| redir | `"<x>"` | ✅ | ✅ | ✅ | ✅ | ✅ |
| dollar | `"$HOME"` | ✅ | ✅ | ✅ | ✅ | ✅ |
| backtick | `"a`tb"` | ✅ | ✅ | ✅ | ✅ | ✅ |
| comma | `"1,2"` | ✅ | ✅ | ✅ | ✅ | ✅ |
| at | `"@x"` | ✅ | ✅ | ✅ | ✅ | ✅ |
| braces | `"{x}"` | ✅ | ✅ | ✅ | ✅ | ✅ |
| semicolon | `"a;b"` | ✅ | ✅ | ✅ | ✅ | ✅ |
| arabic | `"مرحبا عالم"` | ✅ | ✅ | ✅ | ✅ | ✅ |
| posix_flag | `"/c"` | ✅ | ✅ | ✅ | ✅ | ❌ ["C:/"] |
| posix_path | `"/tmp/x.txt"` | ✅ | ✅ | ✅ | ✅ | ❌ ["C:/Users/<user>/AppData/Local/Temp/x.txt"] |
| eq_posix | `"--out=/tmp/y"` | ✅ | ✅ | ✅ | ✅ | ❌ ["--out=C:/Users/<user>/AppData/Local/Temp/y"] |
| win_path | `"C:\\Users\\x"` | ✅ | ✅ | ✅ | ✅ | ✅ |
| dashdash_pct | `"--%"` | ✅ | ❌ [] | ❌ ["--"] | ✅ | ✅ |
| lone_dq | `"\""` | ✅ | ❌ [""] | ✅ | ✅ | ✅ |

**Correct out of 26:** python_list 26, ps51_literal 18, cmd_batch 18, cmd_c_line 20, gitbash_literal 23