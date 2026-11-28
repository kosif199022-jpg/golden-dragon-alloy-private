"""Stage 1 ideal flat reed nib, no fluid or paper simulation."""
import math
import numpy as np
from .strokes import number


class Qalam:
    def __init__(self, width=24.0, angle=45.0):
        self.width = number(width, "width")
        self.angle = number(angle, "angle")
        if not 0 < self.width <= 4096:
            raise ValueError("width must be in (0,4096]")

    @property
    def axis(self):
        a = math.radians(self.angle % 360)
        return np.array([math.cos(a), math.sin(a)])

    def effective_width(self, direction, pressure=1.0):
        """Direction and nib angle in degrees, same image-space convention."""
        d = number(direction, "direction")
        p = number(pressure, "pressure")
        if not 0 <= p <= 1:
            raise ValueError("pressure outside [0,1]")
        return abs(math.sin(math.radians((d-self.angle) % 180)))*self.width*p

    def endpoints(self, xy, pressure):
        half = np.asarray(pressure)[...,None]*self.width/2*self.axis
        return np.asarray(xy)-half, np.asarray(xy)+half
