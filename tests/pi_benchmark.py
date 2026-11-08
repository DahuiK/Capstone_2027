#!/usr/bin/env python3
"""Pi 3 B+ speed checks, runnable before the camera or CAN HAT arrive.

  1. 12 MP JPEG encode time  -> sets the minimum gap between survey photos
  2. AprilTag detection rate at 640x480 -> how fast LAND_TARGET can update

    python3 tests/pi_benchmark.py
    python3 tests/pi_benchmark.py --camera   # also time a real 12 MP still (Camera Module 3 fitted)

Targets: JPEG < 2 s per photo; tag detection >= 5 Hz (10 Hz ideal).
"""
import argparse
import time

import cv2
import numpy as np


def bench_jpeg(runs=3):
    h, w = 2592, 4608  # Camera Module 3 full resolution (12 MP)
    rng = np.random.default_rng(0)
    # Smooth noise compresses like a real photo better than pure random noise
    small = rng.integers(0, 255, (h // 16, w // 16, 3), dtype=np.uint8)
    img = cv2.resize(small, (w, h), interpolation=cv2.INTER_CUBIC)
    times = []
    for _ in range(runs):
        t0 = time.perf_counter()
        ok, buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 90])
        times.append(time.perf_counter() - t0)
    avg = sum(times) / len(times)
    print(f"12 MP JPEG encode: {avg:.2f} s per photo ({len(buf) / 1e6:.1f} MB)  "
          f"-> {'OK' if avg < 2 else 'SLOW: use a lower capture resolution'}")


def make_tag_frame():
    """640x480 grey frame with one tag36h11 (id 0), ~120 px wide."""
    aruco = getattr(cv2, "aruco", None)
    if aruco is None:
        return None
    d = aruco.getPredefinedDictionary(aruco.DICT_APRILTAG_36h11)
    if hasattr(aruco, "generateImageMarker"):      # OpenCV >= 4.7
        tag = aruco.generateImageMarker(d, 0, 100)
    else:                                          # OpenCV 4.6 (Debian Bookworm)
        tag = aruco.drawMarker(d, 0, 100)
    tag = cv2.copyMakeBorder(tag, 10, 10, 10, 10, cv2.BORDER_CONSTANT, value=255)
    frame = np.full((480, 640), 128, np.uint8)
    y, x = 180, 260
    frame[y:y + tag.shape[0], x:x + tag.shape[1]] = tag
    return frame


def bench_apriltag(runs=50):
    try:
        from pupil_apriltags import Detector
    except ImportError:
        print("AprilTag: pupil-apriltags not installed (pip install pupil-apriltags)")
        return
    frame = make_tag_frame()
    if frame is None:
        print("AprilTag: OpenCV has no aruco module, timing on a blank frame instead")
        frame = np.full((480, 640), 128, np.uint8)
    det = Detector(families="tag36h11", nthreads=4, quad_decimate=2.0)
    found = det.detect(frame)
    t0 = time.perf_counter()
    for _ in range(runs):
        det.detect(frame)
    rate = runs / (time.perf_counter() - t0)
    ids = [d.tag_id for d in found]
    print(f"AprilTag 640x480: {rate:.1f} detections/s, tags found: {ids}  "
          f"-> {'OK' if rate >= 5 else 'SLOW: lower resolution or raise quad_decimate'}")


def bench_camera():
    try:
        from picamera2 import Picamera2
    except ImportError:
        print("Camera: picamera2 not available")
        return
    cam = Picamera2()
    cam.configure(cam.create_still_configuration(buffer_count=1))
    cam.start()
    time.sleep(2)
    t0 = time.perf_counter()
    cam.capture_file("/tmp/bench_12mp.jpg")
    print(f"Camera 12 MP capture + save: {time.perf_counter() - t0:.2f} s")
    cam.stop()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--camera", action="store_true")
    args = ap.parse_args()
    bench_jpeg()
    bench_apriltag()
    if args.camera:
        bench_camera()
