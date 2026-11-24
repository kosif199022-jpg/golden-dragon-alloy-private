# remove the burned-in white lyric text (box y 930-1130 on 1080x1920) and regrade the light
import cv2, numpy as np, sys, os
src, out = sys.argv[1], sys.argv[2]; os.makedirs(out, exist_ok=True)
cap = cv2.VideoCapture(src); i = 0
Y0, Y1, X0, X1 = 930, 1135, 90, 990
lut_r = np.clip(np.arange(256) * 1.0 + 10 * np.sin(np.arange(256) / 255 * np.pi), 0, 255).astype(np.uint8)
def grade(im):
    f = im.astype(np.float32) / 255
    # gentle S-curve contrast, warm highlights, teal shadows
    f = f * f * (3 - 2 * f) * .35 + f * .65
    l = f.mean(2, keepdims=True)
    warm = np.array([0.94, 1.0, 1.08], np.float32); teal = np.array([1.07, 1.02, 0.92], np.float32)   # BGR
    f = f * (teal * (1 - l) + warm * l)
    # bloom on bright lights
    br = np.clip((f - .62) * 2.6, 0, 1)
    bl = cv2.GaussianBlur(br, (0, 0), 14) * .55 + cv2.GaussianBlur(br, (0, 0), 4) * .25
    f = 1 - (1 - f) * (1 - bl * np.array([0.75, 0.9, 1.0], np.float32))
    return np.clip(f * 255, 0, 255).astype(np.uint8)
while True:
    ok, fr = cap.read()
    if not ok: break
    fr = cv2.resize(fr, (1080, 1920), interpolation=cv2.INTER_CUBIC)
    roi = fr[Y0:Y1, X0:X1]
    hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
    g = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
    top = cv2.morphologyEx(g, cv2.MORPH_TOPHAT, np.ones((15, 15), np.uint8))      # thin bright strokes only
    m = ((top > 38) & (hsv[..., 1] < 70) & (g > 120)).astype(np.uint8) * 255
    m = cv2.dilate(m, np.ones((5, 5), np.uint8), iterations=2)
    roi[:] = cv2.inpaint(roi, m, 7, cv2.INPAINT_TELEA)
    cv2.imwrite(f'{out}/{i + 1:04d}.jpg', grade(fr), [cv2.IMWRITE_JPEG_QUALITY, 90]); i += 1
print('frames', i)
