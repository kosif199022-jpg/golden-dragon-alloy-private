# V74 Living Pen — Stage 1

Native, original CPU implementation. Python 3.12 + NumPy + Pillow; no network, fonts, GPU, Numba, or paid generator used. The CLI reads a local UTF-8 JSON, writes a new PNG only with explicit approval, and returns dimensions and SHA-256. Existing files are never overwritten.

```powershell
python -X utf8 rose.py pen stroke living_pen/sample_salam.json --out سلام.png --approve-write
python -X utf8 -W error::ResourceWarning -m unittest test_living_pen_v74 -v
```

JSON: width, height (1..4096), background RGB, supersample (2..8; max 100M subpixels), strokes (1..256). Each stroke has points (2..4096, XY pixel pairs, no identical neighbors), pressure (scalar or per-point, 0..1), tilt (degrees 0..90, stored but not used by ideal nib), duration (seconds >0), start_time (seconds >=0), tool ("qalam"), pigment (RGB), nib (width in pixels, angle in degrees). See sample_salam.json. Angles are measured clockwise from image +X. List order determines layering; time is metadata for future reveal/animation. Repeating the first point closes a stroke; the pressure/tilt seam must agree.

## Math and provenance

- Catmull and Rom, *A Class of Local Interpolating Splines* (1974), https://doi.org/10.1016/B978-0-12-079050-0.50020-5. Centripetal knots h_i = ||P_(i+1)-P_i||^0.5 per Yuksel, Schaefer, Keyser (2011), https://www.cemyuksel.com/research/catmullrom_param/. Original implementation via weighted neighboring secants and cubic Hermite coefficients, with one-sided end tangents and periodic tangents for closed paths.
- Arc length integral of ||C'(u)|| is approximated by a cumulative chord table (128 subdivisions/segment), then inverted with linear interpolation. Signed curvature k = (x'y'' - y'x'') / ||C'||^3 from differential geometry; undefined at stationary cusps (NaN), not a fabricated zero. For the radius-100 circle represented by 128 knots, observed length 628.3184812842353 px vs 628.3185307179587 px, relative error 7.87e-8 (test tolerance 1e-5).
- Scalar minimum-jerk timing s = L(10q^3-15q^4+6q^5), q=(t-t0)/T; speed = (L/T)30q^2(1-q)^2. Derived by imposing zero endpoint velocity and acceleration on a quintic. Flash & Hogan (1985), https://doi.org/10.1523/JNEUROSCI.05-07-01688.1985. This minimizes jerk of **arc distance**, not full Cartesian jerk on a curved path.
- Nib law from owner specification and geometric projection: w_eff = |sin(direction-angle)| * nib_width * pressure. A swept segment along the nib axis generates the footprint; the renderer fills successive quadrilaterals at <=0.5 px arc spacing, then area-averages the supersampled mask and composites RGB with integer round-to-nearest. Ideal parallel motion has zero area; no fictitious minimum width.
- All implementation code is newly authored; mathematical references are citations, not copied code.

## Evidence and limits

Windows / CPython 3.12.10 / NumPy 2.5.4 / Pillow 13.0.0: 17 focused tests passed. Includes actual CLI subprocess, Arabic input/output filenames, approval and overwrite rejection, circle error, speed, negative inputs, antialias, nib-width pixels, deterministic PNG and sample image. SHA-256 determinism is tested within the same software environment, not a promise across Pillow/zlib versions or platforms.

The handwritten sample is an illustrative six-stroke skeleton of the Arabic word salam, not a font or a classical calligraphic proportions certification. 1080 x 1080 PNG, SHA-256 1025488aac9bb58f781778016f8c0ab1c5e873109bd7fc92367a310957ca5dd6. It was rendered with the actual CLI and visually inspected. No authorized real-reed reference photo was supplied; a measured photo comparison remains NOT TESTED. Stage 2+ (ink, paper, letter grammar, animation, GPU, tiled/resumable frames) not implemented. No change to existing capability adapter registry, counts, or tests; this is a dedicated CLI extension. Review sample before Stage 2.
