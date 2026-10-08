from src.compat import ocr_memory
from src.compat.ocr_memory import (
    CACHE_CAPACITY_KEY,
    CPU_RUNTIME_CACHE_CAPACITY,
    patch_core_compile_model,
)


def _fake_core_class():
    class FakeCore:
        def compile_model(self, model, device_name=None, config=None):
            return model, device_name, config

    patch_core_compile_model(FakeCore)
    return FakeCore


def test_cpu_compile_gets_cache_cap():
    core = _fake_core_class()()
    assert core.compile_model(model="m", device_name="CPU") == (
        "m",
        "CPU",
        {CACHE_CAPACITY_KEY: CPU_RUNTIME_CACHE_CAPACITY},
    )


def test_existing_config_is_kept_and_own_cap_wins():
    core = _fake_core_class()()
    _, _, config = core.compile_model("m", "CPU", {"A": 1, CACHE_CAPACITY_KEY: 7})
    assert config == {"A": 1, CACHE_CAPACITY_KEY: 7}


def test_other_devices_untouched():
    core = _fake_core_class()()
    assert core.compile_model(model="m", device_name="NPU") == ("m", "NPU", None)
    assert core.compile_model("m") == ("m", None, None)


def test_patch_is_applied_once():
    cls = _fake_core_class()
    patched = cls.compile_model
    patch_core_compile_model(cls)
    assert cls.compile_model is patched


def test_real_openvino_ocr_compiles_and_reads_with_cap(monkeypatch):
    import numpy as np
    import openvino

    seen = []
    ocr_memory.install_ocr_memory_cap()
    patched = openvino.Core.compile_model

    def spy(self, model, device_name=None, config=None, *args, **kwargs):
        result = patched(self, model, device_name, config, *args, **kwargs)
        seen.append((device_name, config))
        return result

    monkeypatch.setattr(openvino.Core, "compile_model", spy)
    from onnxocr.onnx_paddleocr import ONNXPaddleOcr

    ocr = ONNXPaddleOcr(use_angle_cls=False, use_openvino=True)
    ocr.ocr(np.full((64, 200, 3), 255, dtype=np.uint8))
    assert seen and all(device == "CPU" for device, _ in seen)
