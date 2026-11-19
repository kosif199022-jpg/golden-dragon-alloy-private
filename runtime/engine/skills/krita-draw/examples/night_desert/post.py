# Runs inside Krita after the layers are built: add a vignette paint layer with raw pixels.
W, H = doc.width(), doc.height()
buf = bytearray(W * H * 4)
cx, cy = W / 2, H / 2
maxd = (cx * cx + cy * cy) ** 0.5
i = 0
for y in range(0, H):
    dy = (y - cy) ** 2
    for x in range(W):
        d = ((x - cx) ** 2 + dy) ** 0.5 / maxd
        a = int(max(0.0, (d - 0.55) / 0.45) ** 1.6 * 200)
        buf[i + 3] = a  # B,G,R stay 0 -> black
        i += 4
v = doc.createNode("فينييت", "paintlayer")
root.addChildNode(v, None)
v.setPixelData(bytes(buf), 0, 0, W, H)
v.setBlendingMode("multiply")
result = {"vignette": True, "layers_now": len(root.childNodes())}
