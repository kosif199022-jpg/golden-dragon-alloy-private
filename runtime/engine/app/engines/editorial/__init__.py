"""Editorial film edit: real footage in a soft archival editorial style — film grain, bloom/halation, doc / B&W / film
grades, archive age, word-by-word captions with italic serif accents, kinetic emphasis type and presenter splits.

An edit is an EDL JSON (data/example.edl.json); build() makes one seekable page from the layer modules in assets/ and
render() turns it into an MP4 through engines/render/render.cjs. Style guide: data/style-guide.md.
"""
from .edit import EXAMPLE, MODULES, bundle, build, check, doctor, example, generate_media, load, render, resolve_media, verify

__all__ = ["EXAMPLE", "MODULES", "bundle", "build", "check", "doctor", "example", "generate_media", "load", "render",
           "resolve_media", "verify"]
