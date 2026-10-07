"""Helper for test_cudo.ps1: PyTorch CUDA on host."""
import sys

try:
    import torch
except Exception as exc:
    print("IMPORT_FAIL", exc)
    sys.exit(2)

print("VERSION", torch.__version__)
cuda = torch.cuda.is_available()
print("CUDA", cuda)
if not cuda:
    print(
        "HINT",
        "pip install torch torchvision --index-url https://download.pytorch.org/whl/cu128",
    )
    sys.exit(1)

print("DEVICE", torch.cuda.get_device_name(0))
tensor = torch.zeros(1, device="cuda")
print("TENSOR", tensor.device)
sys.exit(0)
