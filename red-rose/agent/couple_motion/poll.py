"""Wait for the Grok jobs in OUTDIR/sub.json and save OUTDIR/img/n<i>.png, then a contact sheet OUTDIR/scenes.jpg.
usage: python3 poll.py OUTDIR"""
import json, os, subprocess, sys, time
out = sys.argv[1]; sub = json.load(open(os.path.join(out, 'sub.json')))
os.makedirs(os.path.join(out, 'img'), exist_ok=True)
k = os.environ.get('HF_KEY', 'dummy:dummy')
for _ in range(60):
    left = 0
    for i, rid in sub.items():
        f = os.path.join(out, 'img', f'n{i}.png')
        if os.path.exists(f):
            continue
        d = json.loads(subprocess.run(['curl', '-s', '-H', f'Authorization: Key {k}',
                                       f'https://api.higgsfield.ai/requests/{rid}/status'], capture_output=True, text=True).stdout or '{}')
        st = d.get('status')
        if st == 'completed':
            subprocess.run(['curl', '-s', '-o', f, d['images'][0]['url']])
        elif st in ('failed', 'nsfw'):
            print('scene', i, st, '- rewrite its prompt and run gen.py --only', i)
        else:
            left += 1
    if not left:
        break
    time.sleep(8)
try:
    from PIL import Image
    n = sorted(int(i) for i in sub); c = min(5, len(n)); r = (len(n) + c - 1) // c
    sheet = Image.new('RGB', (c * 300, r * 533))
    for j, i in enumerate(n):
        p = os.path.join(out, 'img', f'n{i}.png')
        if os.path.exists(p):
            sheet.paste(Image.open(p).convert('RGB').resize((300, 533)), ((j % c) * 300, (j // c) * 533))
    sheet.save(os.path.join(out, 'scenes.jpg'), quality=85); print('sheet', os.path.join(out, 'scenes.jpg'))
except ImportError:
    pass
