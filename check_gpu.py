# check_gpu.py
import torch

# ====================== PyTorch 环境检查 ======================
print("=" * 50)
print("📌 PyTorch 环境检测")
print("-" * 30)
print(f"PyTorch 版本: {torch.__version__}")
print(f"CUDA 是否可用: {torch.cuda.is_available()}")

if torch.cuda.is_available():
    print(f"当前显卡设备: {torch.cuda.get_device_name(0)}")
    print("✅ 恭喜！PyTorch 支持 GPU 加速。")
else:
    print("❌ 警告：PyTorch 仅支持 CPU，无法使用显卡加速。")
print("-" * 30) 

