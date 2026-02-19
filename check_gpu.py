# check_gpu.py
import torch
import paddle

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

# ====================== PaddlePaddle 环境检查 ======================
print("\n📌 PaddlePaddle 环境检测")
print("-" * 40)
# 官方自带的环境完整性检查
paddle.utils.run_check()  

# 详细 GPU 信息验证
print(f"\nPaddlePaddle 版本: {paddle.__version__}")
print(f"CUDA 编译支持: {paddle.is_compiled_with_cuda()}")
# 兼容无CUDA环境（避免报错）
try:
    print(f"适配的 CUDA 版本: {paddle.version.cuda()}")
except:
    print("适配的 CUDA 版本: 未编译 CUDA 支持")
print(f"可用 GPU 数量: {paddle.device.cuda.device_count()}")

if paddle.is_compiled_with_cuda() and paddle.device.cuda.device_count() > 0:
    paddle.device.set_device('gpu:0')
    print(f"当前使用 GPU: {paddle.device.cuda.get_device_name(0)}")
    # 测试 GPU 张量运算
    x = paddle.to_tensor([1.0, 2.0, 3.0], place=paddle.CUDAPlace(0))
    y = x * 2
    print(f"GPU 运算测试结果: {y.numpy()}")
    print("✅ PaddlePaddle GPU 功能正常！")
else:
    print("❌ PaddlePaddle 未启用 GPU，仅支持 CPU 运行")
print("-" * 40)
print("=" * 50)