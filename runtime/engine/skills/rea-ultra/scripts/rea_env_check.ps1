# rea_env_check.ps1 - one-shot readiness check for REA engines on this Windows machine.
# Usage: powershell -NoProfile -File rea_env_check.ps1 [-Provider ghidra]
param([string]$Provider = "")
$vars = 'GHIDRA_INSTALL_DIR','JAVA_HOME','REA_JADX_MCP_JAR','REA_APKTOOL_COMMAND','REA_ADB_PATH',
        'REA_RIZIN_COMMAND','REA_WABT_BIN_DIRECTORY','REA_TSHARK_COMMAND','REA_CAPINFOS_COMMAND'
foreach ($v in $vars) {
  $val = [Environment]::GetEnvironmentVariable($v,'User')
  if ($val) { Set-Item "env:$v" $val }
  $ok = if ($val -and (Test-Path $val)) { 'OK ' } elseif ($val) { 'BAD' } else { '-- ' }
  "{0} {1,-24} {2}" -f $ok, $v, $val
}
"--- MCP registration (.claude.json -> mcpServers.rea.env) ---"
python -I -c "import json;d=json.load(open(r'$env:USERPROFILE\.claude.json',encoding='utf-8'));print(sorted((d['mcpServers']['rea'].get('env') or {}).keys()))"
"--- rea doctor ---"
if ($Provider) { rea doctor --provider $Provider 2>&1 | Select-String 'healthy|classification|detail' }
else { rea doctor 2>&1 | Select-String '^\s*- name|classification|^healthy' }
