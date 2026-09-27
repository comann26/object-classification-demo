import numpy as np

from demo.contracts import Detection, Frame
from demo.detector import FakeDetector, filter_min, threat_nms

_BOX = (0.1, 0.1, 0.5, 0.5)
# Two equal-size boxes overlapping by IoU exactly 0.1 (see task-5 report for the algebra).
_BOX_A = (0.0, 0.0, 0.55, 0.4)
_BOX_B = (0.45, 0.0, 1.0, 0.4)


def _frame() -> Frame:
    return Frame(index=0, ts=0.0, image=np.zeros((4, 4, 3), np.uint8))


def test_nms_keeps_best_threat_class():
    dets = [
        Detection("knife", 0.4, _BOX),
        Detection("gun", 0.3, _BOX),
    ]
    kept = threat_nms(dets, {"knife", "gun"}, iou=0.5)
    assert kept == [Detection("knife", 0.4, _BOX)]


def test_nms_leaves_person_alone():
    dets = [
        Detection("person", 0.9, _BOX),
        Detection("person", 0.8, _BOX),
    ]
    kept = threat_nms(dets, {"knife", "gun"}, iou=0.5)
    assert kept == dets


def test_nms_keeps_separate_objects():
    dets = [
        Detection("knife", 0.4, _BOX_A),
        Detection("knife", 0.35, _BOX_B),
    ]
    kept = threat_nms(dets, {"knife"}, iou=0.5)
    assert kept == dets


def test_filter_min():
    dets = [
        Detection("person", 0.30, _BOX),
        Detection("knife", 0.16, _BOX),
    ]
    kept = filter_min(dets, person_min=0.35, object_min=0.15)
    assert kept == [Detection("knife", 0.16, _BOX)]


def test_fake_detector_records_classes_and_calls_script():
    seen_frames = []

    def script(frame: Frame) -> list[Detection]:
        seen_frames.append(frame)
        return [Detection("knife", 0.5, _BOX)]

    det = FakeDetector(script=script)
    det.set_classes(["person", "knife"])
    frame = _frame()

    result = det.detect(frame, input_size=640)

    assert result == [Detection("knife", 0.5, _BOX)]
    assert seen_frames == [frame]
    assert det.classes == ["person", "knife"]
    assert det.model_name == "fake"
    assert det.model_sha256 == "0" * 64
