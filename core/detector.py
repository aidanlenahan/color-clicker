import numpy as np
import config


class ColorDetector:
    def find_color(self, frame: np.ndarray, target_color: tuple) -> tuple | None:
        """
        Locate target color in a BGR frame.

        Returns (x, y) in frame-local pixel coordinates, or None if not found.
        Uses OpenCV contour centroid when available (largest matching blob),
        falls back to NumPy centroid of all matching pixels.
        """
        r0, g0, b0 = target_color
        target_bgr = np.array([b0, g0, r0], dtype=np.int16)
        diff = np.abs(frame.astype(np.int16) - target_bgr)
        mask = np.all(diff <= config.COLOR_TOLERANCE, axis=2)

        if not mask.any():
            return None

        if config.USE_OPENCV:
            result = self._opencv_centroid(mask)
            if result is not None:
                return result

        coords = np.column_stack(np.where(mask))
        y, x = coords.mean(axis=0)
        return int(x), int(y)

    def _opencv_centroid(self, mask: np.ndarray) -> tuple | None:
        try:
            import cv2
            mask8 = mask.astype(np.uint8) * 255
            contours, _ = cv2.findContours(mask8, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            if not contours:
                return None
            largest = max(contours, key=cv2.contourArea)
            M = cv2.moments(largest)
            if M["m00"] == 0:
                return None
            return int(M["m10"] / M["m00"]), int(M["m01"] / M["m00"])
        except Exception:
            return None
