"""
Procedural pixel-art Earth texture + vectorized sphere rendering.

Everything here is generated in code (no image assets), which keeps the
project tiny and avoids any asset-loading path issues when it gets packaged
for the web with pygbag.

How the "3D" globe works with plain pygame (which has no 3D renderer):
  1. `generate_earth_texture()` builds a small equirectangular (lon/lat)
     map of Earth-ish colors using a handful of seamless sine/cosine waves
     as a height field, bucketed into a few flat pixel-art color bands.
  2. `Globe` precomputes, once, for every pixel inside a circle of the
     chosen radius: the 3D unit-sphere normal a viewer would see there,
     and from that a fixed "view longitude"/latitude and a lighting value.
  3. Each frame, rotating the globe is just subtracting the current
     rotation angle from every pixel's view-longitude and using that to
     index into the texture -- a cheap vectorized numpy gather, no
     per-frame trig needed for the whole image.
"""

import numpy as np

# Equirectangular texture resolution. Kept small on purpose -- the pixel
# art look comes from the low resolution, not from downscaling later.
TEX_W, TEX_H = 128, 64

# Magic "impossible" color used as a colorkey so the square render buffer
# can be blitted with transparent corners outside the circular globe.
COLORKEY = (1, 0, 1)


def generate_earth_texture(width=TEX_W, height=TEX_H, seed=1):
    """Build an (height, width, 3) uint8 array: a stylised pixel-art Earth."""
    rng = np.random.default_rng(seed)

    lon = np.linspace(0.0, 2 * np.pi, width, endpoint=False)
    lat = np.linspace(-np.pi / 2, np.pi / 2, height)
    lon_grid, lat_grid = np.meshgrid(lon, lat)  # both shape (height, width)

    # --- height field -----------------------------------------------
    # Using integer multiples of longitude keeps every wave perfectly
    # seamless at the lon=0/lon=2*pi wrap, so the globe has no visible seam.
    field = np.zeros_like(lon_grid)
    for _ in range(6):
        k = rng.integers(1, 6)
        phase = rng.uniform(0, 2 * np.pi)
        lat_freq = rng.uniform(0.5, 2.5)
        lat_phase = rng.uniform(-1, 1)
        amp = rng.uniform(0.3, 1.0)
        field += amp * np.cos(k * lon_grid + phase) * np.cos(lat_freq * lat_grid + lat_phase)

    for _ in range(4):
        k = rng.integers(6, 14)
        phase = rng.uniform(0, 2 * np.pi)
        lat_freq = rng.uniform(2, 6)
        lat_phase = rng.uniform(-1, 1)
        amp = rng.uniform(0.08, 0.22)
        field += amp * np.sin(k * lon_grid + phase) * np.cos(lat_freq * lat_grid + lat_phase)

    field -= field.min()
    field /= field.max()  # normalize to 0..1

    # --- pixel-art palette, banded (no smooth gradients) -------------
    deep_ocean = (16, 48, 104)
    ocean      = (26, 80, 156)
    shallow    = (52, 126, 186)
    lowland    = (70, 140, 60)
    midland    = (112, 150, 58)
    highland   = (150, 128, 68)
    mountain   = (118, 98, 88)
    snow       = (236, 238, 240)
    ice        = (208, 224, 236)

    # Thresholds are picked as quantiles of the actual field rather than
    # fixed absolute values, so the land/ocean ratio stays close to
    # Earth-like (~30% land) no matter how a given seed's random waves
    # happen to be distributed.
    def q(p):
        return np.quantile(field, p)

    land_start = q(0.68)  # top ~32% of the height field counts as land
    bands = [
        (0.0,          deep_ocean),
        (q(0.30),      ocean),
        (q(0.55),      shallow),
        (land_start,   lowland),
        (q(0.82),      midland),
        (q(0.93),      highland),
        (q(0.97),      mountain),
    ]

    tex = np.zeros((height, width, 3), dtype=np.float32)
    for threshold, color in bands:
        tex[field >= threshold] = color

    land_mask = field >= land_start

    # --- polar ice caps, blended in by latitude -----------------------
    abs_lat_deg = np.degrees(np.abs(lat_grid))
    polar = np.clip((abs_lat_deg - 58) / 20, 0.0, 1.0)  # 0 at 58deg, 1 by 78deg
    polar_color = np.where(land_mask[..., None], snow, ice)
    tex = tex * (1 - polar[..., None]) + polar_color * polar[..., None]

    # --- light per-pixel dither for a grainier, more "pixel art" feel -
    dither = rng.integers(-8, 9, size=(height, width, 1)).astype(np.float32)
    tex = np.clip(tex + dither, 0, 255)

    return tex.astype(np.uint8)


def generate_moon_texture(width=TEX_W, height=TEX_H, seed=3):
    """Build an (height, width, 3) uint8 array: a stylised pixel-art Moon --
    grey regolith with a few darker mare patches and scattered impact
    craters (dark floor + bright rim), no oceans/vegetation like Earth."""
    rng = np.random.default_rng(seed)

    lon = np.linspace(0.0, 2 * np.pi, width, endpoint=False)
    lat = np.linspace(-np.pi / 2, np.pi / 2, height)
    lon_grid, lat_grid = np.meshgrid(lon, lat)

    # --- broad, seamless regolith shading (mare vs highland patches) ----
    # Waves that are separable in lon/lat (cos(k*lon) * cos(f*lat)) have
    # axis-aligned crests, so summing them just produces pole-to-pole
    # stripes, not blobs. Using a random *oriented* plane wave per octave
    # (cos(kx*lon + ky*lat + phase), crests tilted at a random angle) gives
    # genuinely mottled, isotropic patches instead -- kx stays integer so it
    # still wraps seamlessly at lon=0/2*pi, ky doesn't need to (lat isn't
    # periodic). Amplitude falls off with frequency (~1/f) so low-frequency
    # blobs dominate and high frequency just adds grain, like real terrain.
    field = np.zeros_like(lon_grid)
    for _ in range(10):
        kx = rng.integers(1, 9)
        ky = rng.uniform(-6.0, 6.0)
        phase = rng.uniform(0, 2 * np.pi)
        freq = abs(kx) + abs(ky)
        amp = rng.uniform(0.6, 1.0) / (1.0 + 0.35 * freq)
        field += amp * np.cos(kx * lon_grid + ky * lat_grid + phase)
    field -= field.min()
    field /= field.max()

    highland = np.array((176, 174, 170), dtype=np.float32)
    midtone = np.array((152, 150, 148), dtype=np.float32)
    dim = np.array((124, 122, 122), dtype=np.float32)
    mare = np.array((92, 90, 96), dtype=np.float32)

    def q(p):
        return np.quantile(field, p)

    tex = np.empty((height, width, 3), dtype=np.float32)
    tex[:] = highland
    tex[field < q(0.78)] = midtone
    tex[field < q(0.48)] = dim
    tex[field < q(0.22)] = mare

    # --- impact craters: dark floor + bright rim, wrapped in longitude ---
    for _ in range(24):
        clon = rng.uniform(0, 2 * np.pi)
        clat = rng.uniform(-np.pi / 2 + 0.2, np.pi / 2 - 0.2)
        r = rng.uniform(0.05, 0.20)

        dlon = np.abs(lon_grid - clon)
        dlon = np.minimum(dlon, 2 * np.pi - dlon)      # seamless wraparound
        d = np.sqrt(dlon ** 2 + (lat_grid - clat) ** 2)

        floor = d < r * 0.62
        rim = (d >= r * 0.62) & (d < r)
        tex[floor] *= 0.55
        tex[rim] = np.clip(tex[rim] * 1.35 + 20, 0, 255)

    # --- light per-pixel dither for a grainier, more "pixel art" feel ----
    dither = rng.integers(-6, 7, size=(height, width, 1)).astype(np.float32)
    tex = np.clip(tex + dither, 0, 255)

    return tex.astype(np.uint8)


class Globe:
    """A rotatable sphere rendered by texture-mapping an equirectangular
    image, with fixed view-space lighting for a simple lit-sphere look."""

    def __init__(self, radius, texture, light_dir=(-0.5, 0.6, 0.7)):
        self.radius = radius
        self.texture = texture
        self.tex_h, self.tex_w = texture.shape[:2]
        self.size = radius * 2
        self._precompute(light_dir)

    def _precompute(self, light_dir):
        r = self.radius
        size = self.size

        ys, xs = np.mgrid[0:size, 0:size]
        dx = xs - r + 0.5
        dy = ys - r + 0.5
        dist2 = dx * dx + dy * dy
        mask = dist2 <= r * r

        nx = np.zeros((size, size))
        ny = np.zeros((size, size))
        nz = np.zeros((size, size))
        nx[mask] = dx[mask] / r
        ny[mask] = -dy[mask] / r  # screen y grows downward, sphere "up" should be positive
        nz[mask] = np.sqrt(np.clip(1.0 - nx[mask] ** 2 - ny[mask] ** 2, 0.0, 1.0))

        lat = np.zeros((size, size))
        lat[mask] = np.arcsin(np.clip(ny[mask], -1.0, 1.0))
        lon_view = np.zeros((size, size))
        lon_view[mask] = np.arctan2(nx[mask], nz[mask])

        self.mask = mask
        self.lat_idx = np.clip(
            ((lat + np.pi / 2) / np.pi * (self.tex_h - 1)).astype(np.int32),
            0, self.tex_h - 1,
        )
        # keep as float; the per-frame rotation shift is fractional
        self.lon_frac = (lon_view + np.pi) / (2 * np.pi) * self.tex_w

        light = np.array(light_dir, dtype=np.float64)
        light /= np.linalg.norm(light)
        diffuse = np.clip(nx * light[0] + ny * light[1] + nz * light[2], 0.0, 1.0)
        self.brightness = 0.48 + 0.62 * diffuse  # ambient + diffuse term

    def render(self, angle):
        """Return an (size, size, 3) uint8 array for the given rotation (radians)."""
        shift = (angle / (2 * np.pi) * self.tex_w) % self.tex_w
        lon_idx = ((self.lon_frac - shift) % self.tex_w).astype(np.int32)

        colors = self.texture[self.lat_idx, lon_idx]
        shaded = np.clip(colors * self.brightness[..., None], 0, 255).astype(np.uint8)

        out = np.empty((self.size, self.size, 3), dtype=np.uint8)
        out[...] = COLORKEY
        out[self.mask] = shaded[self.mask]
        return out
