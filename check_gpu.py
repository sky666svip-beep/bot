# check_gpu.py
# import torch
# print("-" * 30)
# print(f"PyTorch 版本: {torch.__version__}")
# print(f"CUDA 是否可用: {torch.cuda.is_available()}")
# if torch.cuda.is_available():
#     print(f"当前显卡设备: {torch.cuda.get_device_name(0)}")
# print("✅ 恭喜！你的环境支持 GPU 加速。")
# else:
#     print("❌ 警告：当前只支持 CPU，无法使用显卡加速。")
# print("-" * 30) 
import paddle

# 强制检查 CUDA 环境
paddle.utils.run_check()  # 官方自带的环境检查工具

# 详细 GPU 信息验证
print("\n" + "-"*40)
print(f"PaddlePaddle 版本: {paddle.__version__}")
print(f"CUDA 编译支持: {paddle.is_compiled_with_cuda()}")
print(f"CUDA 版本: {paddle.version.cuda()}")  # 显示适配的 CUDA 版本
print(f"可用 GPU 数: {paddle.device.cuda.device_count()}")

if paddle.is_compiled_with_cuda():
    paddle.device.set_device('gpu:0')
    print(f"当前 GPU: {paddle.device.cuda.get_device_name(0)}")
    # 测试 GPU 张量运算
    x = paddle.to_tensor([1.0, 2.0, 3.0], place=paddle.CUDAPlace(0))
    y = x * 2
    print(f"GPU 运算结果: {y.numpy()}")
    print("✅ 3.2.2 版本 GPU 功能正常！")
else:
    print("❌ 3.2.2 版本未启用 GPU，尝试手动指定 CUDA 安装")
print("-"*40)