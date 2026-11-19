"""Pack local text files into ONE bash command for Higgsfield sandbox_exec (no upload needed).
usage: python -X utf8 pack.py JOB_NAME FILE [FILE...] [--out cmd.sh]
Writes a command that recreates the files under /home/user/jobs/JOB_NAME/in/ plus the skill's
sandbox scripts under /home/user/bdtools/. Prints its size; keep it under ~200 KB."""
import base64, gzip, io, os, sys, tarfile

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = ["hf_bootstrap.sh", "hf_render.sh", "hf_finish.sh"]

def main():
    a = sys.argv[1:]
    out = None
    if "--out" in a:
        i = a.index("--out"); out = a[i + 1]; del a[i:i + 2]
    if len(a) < 1:
        print(__doc__); sys.exit(2)
    job, files = a[0], a[1:]
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz", compresslevel=9) as tf:
        for t in TOOLS:
            tf.add(os.path.join(HERE, t), arcname=f"bdtools/{t}")
        for f in files:
            tf.add(f, arcname=f"jobs/{job}/in/{os.path.basename(f)}")
    b64 = base64.b64encode(buf.getvalue()).decode()
    cmd = (f"mkdir -p /home/user && cd /home/user && base64 -d > /tmp/pk.tgz <<'B64EOF'\n{b64}\nB64EOF\n"
           f"tar -xzf /tmp/pk.tgz && sed -i 's/\\r$//' bdtools/*.sh && chmod +x bdtools/*.sh && "
           f"ls -la bdtools jobs/{job}/in && echo PACK_OK")
    if out:
        with open(out, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(cmd)
    print(f"command bytes={len(cmd)} files={len(files) + len(TOOLS)} job={job}" + (f" -> {out}" if out else ""))
    if not out:
        print(cmd)

if __name__ == "__main__":
    main()
