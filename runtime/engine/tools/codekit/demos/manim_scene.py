"""Tiny Manim scene from the Black Dragon codekit (vertical 1080x1920, about 3 s).

Render on a machine that has Manim (pip install manim):
    manim -qh --fps 30 -r 1080,1920 manim_scene.py CodekitScene

Text() is used instead of MathTex() so that no LaTeX install is needed.
"""
from manim import BLUE, DOWN, UP, YELLOW, Circle, Create, FadeIn, Scene, Square, Text, Transform, Write


class CodekitScene(Scene):
    def construct(self):
        title = Text("a² + b² = c²").scale(1.4).shift(UP * 3)
        circle = Circle(radius=1.6, color=YELLOW)
        square = Square(side_length=3.0, color=BLUE)
        self.play(Write(title), run_time=1.0)
        self.play(Create(circle), run_time=0.8)
        self.play(Transform(circle, square), run_time=0.8)
        self.play(FadeIn(Text("Manim").shift(DOWN * 3)), run_time=0.4)
