"""Unit tests for ImageQualityValidator and quality error handling"""

import numpy as np
from types import SimpleNamespace

from app.core.quality import ImageQualityValidator
from app.utils.exceptions import (
    ImageResolutionError,
    ImageBlurError,
    ImageLightingError,
    FaceTooSmallError,
    FaceNotFullyVisibleError,
    FaceOccludedError,
)


def test_validate_resolution_passes():
    res = ImageQualityValidator.validate_resolution(width=300, height=400, min_width=200, min_height=200)
    assert res["width"] == 300
    assert res["height"] == 400


def test_validate_resolution_fails_width():
    try:
        ImageQualityValidator.validate_resolution(width=150, height=400, min_width=200, min_height=200)
        assert False, "Should have raised ImageResolutionError"
    except ImageResolutionError as e:
        assert e.code == "IMAGE_RESOLUTION_TOO_LOW"
        assert e.details["detected_width"] == 150


def test_validate_resolution_fails_height():
    try:
        ImageQualityValidator.validate_resolution(width=300, height=120, min_width=200, min_height=200)
        assert False, "Should have raised ImageResolutionError"
    except ImageResolutionError as e:
        assert e.code == "IMAGE_RESOLUTION_TOO_LOW"
        assert e.details["detected_height"] == 120


def test_validate_blur_passes():
    # Create sharp high-frequency checkerboard pattern
    sharp_img = np.zeros((200, 200, 3), dtype=np.uint8)
    sharp_img[::4, ::4] = 255
    sharp_img[1::4, 1::4] = 255
    score = ImageQualityValidator.validate_blur(sharp_img, threshold=50.0)
    assert score >= 50.0


def test_validate_blur_fails():
    # Completely flat/uniform image has variance 0.0
    blurry_img = np.full((200, 200, 3), 128, dtype=np.uint8)
    try:
        ImageQualityValidator.validate_blur(blurry_img, threshold=100.0)
        assert False, "Should have raised ImageBlurError"
    except ImageBlurError as e:
        assert e.code == "IMAGE_BLURRY"
        assert e.details["blur_score"] < 100.0


def test_validate_lighting_passes():
    normal_img = np.full((200, 200, 3), 120, dtype=np.uint8)
    val = ImageQualityValidator.validate_lighting(normal_img, min_brightness=40.0, max_brightness=220.0)
    assert 40.0 <= val <= 220.0


def test_validate_lighting_fails_too_dark():
    dark_img = np.full((200, 200, 3), 15, dtype=np.uint8)
    try:
        ImageQualityValidator.validate_lighting(dark_img, min_brightness=40.0, max_brightness=220.0)
        assert False, "Should have raised ImageLightingError"
    except ImageLightingError as e:
        assert e.code == "IMAGE_LIGHTING_INVALID"
        assert e.details["issue"] == "underexposed_too_dark"


def test_validate_lighting_fails_too_bright():
    bright_img = np.full((200, 200, 3), 245, dtype=np.uint8)
    try:
        ImageQualityValidator.validate_lighting(bright_img, min_brightness=40.0, max_brightness=220.0)
        assert False, "Should have raised ImageLightingError"
    except ImageLightingError as e:
        assert e.code == "IMAGE_LIGHTING_INVALID"
        assert e.details["issue"] == "overexposed_too_bright"


def test_validate_face_integrity_passes():
    bbox = [50, 50, 200, 200]
    res = ImageQualityValidator.validate_face_integrity(
        img_shape=(400, 400, 3),
        bbox=bbox,
        min_face_size=80,
        boundary_margin=5
    )
    assert res["face_width"] == 150
    assert res["face_height"] == 150


def test_validate_face_integrity_too_small():
    bbox = [50, 50, 80, 80]  # width = 30, height = 30
    try:
        ImageQualityValidator.validate_face_integrity(
            img_shape=(400, 400, 3),
            bbox=bbox,
            min_face_size=80,
            boundary_margin=5
        )
        assert False, "Should have raised FaceTooSmallError"
    except FaceTooSmallError as e:
        assert e.code == "FACE_TOO_SMALL"
        assert e.details["face_width"] == 30


def test_validate_face_integrity_cut_off():
    bbox = [2, 50, 150, 200]  # x1 = 2 <= margin 5 (touches left edge)
    try:
        ImageQualityValidator.validate_face_integrity(
            img_shape=(400, 400, 3),
            bbox=bbox,
            min_face_size=80,
            boundary_margin=5
        )
        assert False, "Should have raised FaceNotFullyVisibleError"
    except FaceNotFullyVisibleError as e:
        assert e.code == "FACE_NOT_FULLY_VISIBLE"
        assert "left edge" in e.details["boundary_issues"]


def test_validate_landmarks_passes():
    mock_face = SimpleNamespace(
        kps=np.array([[100, 100], [150, 100], [125, 125], [110, 150], [140, 150]]),
        det_score=0.92
    )
    res = ImageQualityValidator.validate_landmarks_and_occlusion(mock_face)
    assert res["landmarks_detected"] == 5
    assert res["detection_score"] == 0.92


def test_validate_landmarks_missing():
    mock_face = SimpleNamespace(
        kps=None,
        det_score=0.9
    )
    try:
        ImageQualityValidator.validate_landmarks_and_occlusion(mock_face)
        assert False, "Should have raised FaceOccludedError"
    except FaceOccludedError as e:
        assert e.code == "FACE_OCCLUDED"


def test_validate_landmarks_low_confidence():
    mock_face = SimpleNamespace(
        kps=np.array([[100, 100], [150, 100], [125, 125], [110, 150], [140, 150]]),
        det_score=0.35  # lower than default 0.6
    )
    try:
        ImageQualityValidator.validate_landmarks_and_occlusion(mock_face)
        assert False, "Should have raised FaceOccludedError"
    except FaceOccludedError as e:
        assert e.code == "FACE_OCCLUDED"


if __name__ == "__main__":
    test_validate_resolution_passes()
    test_validate_resolution_fails_width()
    test_validate_resolution_fails_height()
    test_validate_blur_passes()
    test_validate_blur_fails()
    test_validate_lighting_passes()
    test_validate_lighting_fails_too_dark()
    test_validate_lighting_fails_too_bright()
    test_validate_face_integrity_passes()
    test_validate_face_integrity_too_small()
    test_validate_face_integrity_cut_off()
    test_validate_landmarks_passes()
    test_validate_landmarks_missing()
    test_validate_landmarks_low_confidence()
    print("ALL 14 QUALITY VALIDATION TESTS PASSED SUCCESSFULLY!")
