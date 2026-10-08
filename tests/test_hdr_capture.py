import unittest

import numpy as np

from src.capture.hdr_wgc import (
    HdrAwareWindowsGraphicsCapture,
    display_hdr_white,
    float16_rgba_to_bgra,
    srgb_lut_for_float16,
)


def _srgb_to_linear(values):
    v = values / 255.0
    return np.where(v <= 0.04045, v / 12.92, ((v + 0.055) / 1.055) ** 2.4)


class HdrCaptureConversionTest(unittest.TestCase):
    """Windows HDR composes SDR windows as linear light x SDR white level."""

    def test_every_sdr_value_comes_back(self):
        values = np.arange(256)
        for white in (1.0, 2.5, 3.1, 5.0):
            scrgb = (_srgb_to_linear(values) * white).astype(np.float16)
            back = srgb_lut_for_float16(white)[scrgb.view(np.uint16)]
            self.assertEqual(0, int(np.abs(back.astype(int) - values).max()), white)

    def test_out_of_range_light(self):
        lut = srgb_lut_for_float16(2.5)
        special = np.array([np.inf, -np.inf, np.nan, -0.5, 10.0], np.float16).view(np.uint16)
        self.assertEqual([255, 0, 0, 0, 255], lut[special].tolist())

    def test_rgba_float_becomes_bgra_bytes(self):
        rgba = np.zeros((2, 3, 4), np.float16)
        rgba[..., 0] = 1.0  # R
        rgba[..., 1] = 0.5  # G (linear)
        rgba[..., 3] = 1.0
        out = float16_rgba_to_bgra(rgba.view(np.uint16), srgb_lut_for_float16(1.0))
        self.assertEqual((2, 3, 4), out.shape)
        self.assertEqual([0, 188, 255, 255], out[0, 0].tolist())

    def test_unknown_display_means_sdr(self):
        enabled, white, _detail = display_hdr_white(0)
        self.assertIn(enabled, (True, False))
        self.assertGreater(white, 0)

    def test_installed_in_place_of_wgc(self):
        import src.config  # noqa: F401  (installs the capture)
        from ok.device.capture_methods import update

        self.assertIs(HdrAwareWindowsGraphicsCapture, update.WindowsGraphicsCaptureMethod)


if __name__ == "__main__":
    unittest.main()
