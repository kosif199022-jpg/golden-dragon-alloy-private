# vendor

Browser builds copied here so a demo page works with no network. All MIT; each folder has its licence text.

| folder | file | package and version | where it came from |
|---|---|---|---|
| three | three.min.js | three 0.187.0 | built from the package's own `build/three.module.js` + `three.core.js` with `esbuild --bundle --minify --format=iife --global-name=THREE` (the package ships no minified build; a classic script also loads from `file://`, a module does not) |
| animejs | anime.umd.min.js | animejs 4.5.0 | `dist/bundles/anime.umd.min.js`, unchanged |
| mojs | mo.umd.js | @mojs/core 1.3.0 | `dist/mo.umd.js`, unchanged (already minified) |
| roughjs | rough.js | roughjs 4.6.6 | `bundled/rough.js`, unchanged (already minified) |

GSAP is not here on purpose: its licence is the "standard no-charge licence", not an open-source one.
Copy it from your own install with `python3 codekit.py vendor-gsap DEST`.
