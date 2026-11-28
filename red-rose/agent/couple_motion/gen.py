"""Generate «الراجل والست» scenes with Grok Imagine 2.0 through the Higgsfield direct API.

usage: python3 gen.py scenes.json OUTDIR          submit every scene, write OUTDIR/sub.json
       python3 gen.py scenes.json OUTDIR --only 4  resubmit scene 4 only (1-based)
then:  python3 poll.py OUTDIR                      download OUTDIR/img/n1.png ...

The Higgsfield key is never in this file: in a Claude cloud session the proxy injects it for
api.higgsfield.ai (send the dummy header below). Elsewhere set HF_KEY="<id>:<secret>".
Paid: each image costs credits, so the owner's «أيوه» (or an explicit Higgsfield request) comes first.
"""
import json, os, subprocess, sys

API = 'https://api.higgsfield.ai/xai/grok-imagine-image-2.0'
CDN = 'https://d2ol7oe51mr4n9.cloudfront.net/user_36qP6wVjfYmaRqhniKJVy5dJHoh/'
# the three style references (copies in refs/; re-upload them with media_upload if these links ever die)
REFS = [CDN + '40b14133-0d43-49d0-aed8-36a08911ba8e.jpg',   # ../../characters/el-ragel-wel-sit/ref_couple.jpg  (THE characters)
        CDN + '033dc628-f0cf-46dd-ab43-57af4094d22a.jpg',   # ref_ragel.jpg
        CDN + 'f497d860-d929-475e-b986-52bc5c4e7a5b.jpg']   # ref_sit.jpg
# older style refs (refs/style_*.jpg) gave a glossier 3D look and a velvet dress; the owner said «الملامح متغيرة»
STYLE_REFS = [CDN + 'f1a055a9-8dd3-42fb-88e0-f7e24afe2dac.jpg', CDN + '51b8b30b-449a-45a4-aac7-9bd8fe8a0bad.jpg',
              CDN + '03fb31c5-6c60-434c-af62-88bc25359465.jpg']   # refs/style_shop.jpg

# the two characters: never change these words, they are what keeps the couple the same in every song
CHARACTERS = (
    "Use the EXACT same two characters as the reference images: identical faces, identical hairstyles, identical outfits "
    "and the identical painted storybook illustration style (soft digital painting, warm cinematic light), as if drawn by "
    "the same artist in the same series. "
    "The woman: same face, big brown eyes, long brown hair in one thick side braid, crimson red belted wool coat-dress, "
    "dark tights, red ankle boots. "
    "The man: same face, messy dark-brown curly hair, thin round black glasses, burgundy scarf, long grey coat, "
    "white shirt or light sweater, dark trousers, black shoes. ")
TAIL = " Vertical 9:16, absolutely no text, no letters, no writing, no watermark."


def headers():
    k = os.environ.get('HF_KEY', 'dummy:dummy')
    return ['-H', f'Authorization: Key {k}', '-H', 'Content-Type: application/json']


def main():
    spec, out = sys.argv[1], sys.argv[2]
    only = int(sys.argv[sys.argv.index('--only') + 1]) if '--only' in sys.argv else None
    S = json.load(open(spec, encoding='utf-8'))
    refs = S.get('refs') or REFS
    os.makedirs(out, exist_ok=True)
    subp = os.path.join(out, 'sub.json')
    sub = json.load(open(subp)) if os.path.exists(subp) else {}
    for i, scene in enumerate(S['scenes'], 1):
        if only and i != only:
            continue
        body = {'prompt': CHARACTERS + scene + ' ' + S['mood'] + TAIL, 'image_urls': refs, 'aspect_ratio': S.get('aspect', '9:16')}
        r = subprocess.run(['curl', '-s', '-m', '60', '-X', 'POST', API, *headers(), '-d', json.dumps(body)],
                           capture_output=True, text=True).stdout
        sub[str(i)] = json.loads(r)['request_id']
        img = os.path.join(out, 'img', f'n{i}.png')
        if os.path.exists(img):
            os.remove(img)            # a resubmitted scene is downloaded again
        print(i, sub[str(i)])
    json.dump(sub, open(subp, 'w'), indent=1)


if __name__ == '__main__':
    main()
