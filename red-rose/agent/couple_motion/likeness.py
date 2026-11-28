"""Optional: redraw the man in finished scenes so he looks like the owner (Mahmoud), keeping everything else.
Used for «طمنيني». Seedream/Grok edit with the scene first, then the owner's face references.

usage: python3 likeness.py OUTDIR            (reads OUTDIR/img/n*.png URLs from OUTDIR/urls.json: {"1": "https://...", ...})
then:  python3 poll.py OUTDIR   (with sub.json replaced by likeness_sub.json, see README)
PRIVATE: the face references are the owner's photos; this file stays in the private repo only.
"""
import json, os, subprocess, sys
C = 'https://d2ol7oe51mr4n9.cloudfront.net/user_36qP6wVjfYmaRqhniKJVy5dJHoh/'
ME = [C + '5540cff0-9308-4d05-9675-bd838b0fed61.jpg', C + '47be0795-30b2-47fb-9fbf-fda0ad875f70.jpg']
P = ("Keep image 1 the same scene, composition, pose, lighting, colours and soft 3D-cartoon art style; keep the woman and his clothes unchanged. "
     "Redraw the man so he is clearly the real man in images 2 and 3, a faithful cartoon likeness: same face shape (slim, long oval face, defined jaw), "
     "same short neat black hair with side part, same thick straight dark eyebrows, same deep-set dark brown eyes, same nose and lips, light stubble beard, "
     "warm light-tan skin, no glasses. Natural adult body proportions: his head size in correct proportion to his shoulders and body (about one-seventh of "
     "his height), same proportion style as the woman, tall slim build, head not oversized. Vertical 9:16, no text, no watermark.")
out = sys.argv[1]; urls = json.load(open(os.path.join(out, 'urls.json')))
k = os.environ.get('HF_KEY', 'dummy:dummy'); sub = {}
for i, u in urls.items():
    b = {'prompt': P, 'image_urls': [u] + ME, 'aspect_ratio': '9:16'}
    r = subprocess.run(['curl', '-s', '-m', '60', '-X', 'POST', 'https://api.higgsfield.ai/xai/grok-imagine-image-2.0',
                        '-H', f'Authorization: Key {k}', '-H', 'Content-Type: application/json', '-d', json.dumps(b)], capture_output=True, text=True).stdout
    sub[i] = json.loads(r)['request_id']; print(i, sub[i])
json.dump(sub, open(os.path.join(out, 'likeness_sub.json'), 'w'), indent=1)
