# test_model_compare.py
# 双模型语义匹配准确度对比测试
# 对比 Qwen3-Embedding-0.6B 与 richinfoai/ritrieve_zh_v1

import os
import time
import numpy as np

os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"

from sentence_transformers import SentenceTransformer

class APIEmbeddingWrapper:
    """通过 HTTP API 调用 llama-server 以兼容 SentenceTransformer 接口"""
    def __init__(self, base_url="http://127.0.0.1:8080"):
        import requests
        self.base_url = base_url
        self.session = requests.Session()
        # 测试连接
        try:
            res = self.session.get(f"{base_url}/health", timeout=5)
            if res.status_code != 200:
                print(f"\n[WARNING] 无法连接到 API 服务: {base_url} (状态码: {res.status_code})")
        except Exception as e:
            print(f"\n[WARNING] 无法连接到 API 服务: {base_url} ({e})")
        self.dim = None

    def encode(self, sentences, normalize_embeddings=True, show_progress_bar=False):
        if isinstance(sentences, str):
            sentences = [sentences]
        
        embeddings = []
        for text in sentences:
            try:
                # llama-server 的 OpenAI 兼容接口
                response = self.session.post(
                    f"{self.base_url}/v1/embeddings",
                    json={"input": text, "model": "qwen3"},
                    timeout=30
                )
                res_data = response.json()
                vec = np.array(res_data['data'][0]['embedding'])
                
                if normalize_embeddings:
                    norm = np.linalg.norm(vec)
                    if norm > 0:
                        vec = vec / norm
                embeddings.append(vec)
            except Exception as e:
                print(f"\n[ERROR] API 调用失败: {e}")
                embeddings.append(np.zeros(self.get_sentence_embedding_dimension()))
        
        return np.array(embeddings)

    def get_sentence_embedding_dimension(self):
        if self.dim is None:
            try:
                response = self.session.post(
                    f"{self.base_url}/v1/embeddings",
                    json={"input": "test"},
                    timeout=10
                )
                res_data = response.json()
                self.dim = len(res_data['data'][0]['embedding'])
            except:
                self.dim = 1024
        return self.dim


# ============================================================
# 测试用例定义
# 每组: (查询, 候选, 期望相似度趋势)
#   "high"   = 语义相同/近似，期望高分
#   "low"    = 语义不同/反转，期望低分
# ============================================================
TEST_CASES = [
    # --- 1. 精确匹配 ---
    ("光合作用的原料是什么", "光合作用的原料是什么", "high"),
    ("牛顿第一定律是什么", "牛顿第一定律是什么", "high"),
    ("中国的国旗是什么", "中国的国旗是什么", "high"),
    ("Python中如何定义列表", "Python中如何定义列表", "high"),

    # --- 2. 近义改写 ---
    ("光合作用需要哪些物质", "光合作用的原料是什么", "high"),
    ("地球围绕太阳转一圈要多久", "地球公转周期是多少", "high"),
    ("鲁迅的真名叫什么", "鲁迅原名是什么", "high"),
    ("怎么蒸米饭", "蒸米饭的步骤是什么", "high"),
    ("苹果的热量高吗", "苹果的卡路里含量怎么样", "high"),
    ("这道数学题怎么解", "这道数学题的解法是什么", "high"),

    # --- 3. 逻辑反转（期望低分）---
    ("下列属于哺乳动物的是", "下列不属于哺乳动物的是", "low"),
    ("正确的说法是", "错误的说法是", "low"),
    ("温度升高反应速率加快", "温度降低反应速率加快", "low"),
    ("所有金属都导电", "所有金属都不导电", "low"),
    ("明天会下雨", "明天不会下雨", "low"),
    ("他是学生", "他不是学生", "low"),

    # --- 4. 学科限定差异（期望低分）---
    ("英语完形填空", "语文阅读理解", "low"),
    ("数学求导公式", "物理加速度公式", "low"),
    ("化学元素周期表", "历史朝代顺序表", "low"),
    ("英语语法时态", "数学几何定理", "low"),
    ("生物细胞结构", "物理力学公式", "low"),

    # --- 5. 长短文本匹配 ---
    ("AI是什么", "人工智能（AI）是模拟人类智能的计算机系统，能够执行学习、推理和决策等任务", "high"),
    ("什么是区块链", "区块链是一种分布式账本技术，通过密码学将数据以区块的形式链接起来，具有去中心化、不可篡改等特点", "high"),
    ("怎么学编程", "学习编程需要从基础语言学起，多写代码练习，结合项目实践，逐步提升编程能力", "high"),

    # --- 6. 无关文本（期望低分）---
    ("今天天气怎么样", "光合作用的原料是什么", "low"),
    ("如何做红烧肉", "二次方程的求根公式", "low"),
    ("世界杯几年举办一次", "如何种植多肉植物", "low"),
    ("李白的诗有哪些", "汽车保养周期是多久", "low"),
    ("股票怎么开户", "蛋糕的制作方法", "low"),

    # --- 7. 部分重叠但语义不同 ---
    ("中国最大的淡水湖是什么", "中国最大的咸水湖是什么", "low"),
    ("第一次世界大战的起因", "第二次世界大战的起因", "low"),
    ("中国的首都是哪里", "美国的首都是哪里", "low"),
    ("直角三角形的面积公式", "等边三角形的面积公式", "low"),
    ("红楼梦的作者", "西游记的作者", "low"),

    # --- 8. 同义但用词差异大 ---
    ("H2O的化学名称", "水的分子式是什么", "high"),
    ("CPU全称是什么", "中央处理器的英文缩写是什么", "high"),
    ("NaCl的俗称", "食盐的化学名称是什么", "high"),
    ("GDP全称", "国内生产总值的英文缩写", "high"),
    ("HTTP是什么", "超文本传输协议的英文简称", "high"),

    # --- 9. 语序调整但语义不变 ---
    ("北京是中国的首都", "中国的首都是北京", "high"),
    ("我吃了苹果", "苹果被我吃了", "high"),
    ("他每天都跑步", "每天他都跑步", "high"),
    ("这朵花很漂亮", "很漂亮的这朵花", "high"),

    # --- 10. 包含冗余信息但核心语义一致 ---
    ("光合作用的原料是什么", "请问一下，你知道光合作用的原料是什么吗", "high"),
    ("地球公转周期", "我想了解一下地球围绕太阳转一圈的周期是多少", "high"),
    ("鲁迅原名", "有个问题想请教，鲁迅的原名到底是什么呢", "high"),

    # --- 11. 否定+肯定转换（语义一致）---
    ("他不是不聪明", "他很聪明", "high"),
    ("这个问题不难", "这个问题很简单", "high"),
    ("我不会不去", "我会去", "high"),

    # --- 12. 同一概念的不同表述（专业 vs 通俗）---
    ("计算机中央处理器", "电脑的CPU", "high"),
    ("生物体的基本单位", "细胞是什么", "high"),
    ("大气压强", "气压", "high"),

    # --- 13. 数字/单位转换但语义一致 ---
    ("1米等于多少厘米", "100厘米是多少米", "high"),
    ("1千克等于多少克", "1000克是多少千克", "high"),
    ("这个物体重5公斤", "这个物体重5千克", "high"),

    # --- 14. 隐含语义匹配（需要推理）---
    ("他穿着雨衣出门了", "外面在下雨", "high"),
    ("她买了很多菜", "她准备做饭", "high"),
    ("学生们都在认真听讲", "老师正在上课", "high"),

    # --- 15. 易混淆概念区分（期望低分）---
    ("电压和电流", "电压和电阻", "low"),
    ("质量和重量", "质量和密度", "low"),
    ("动能和势能", "动能和动量", "low"),
]

# ============================================================
# 模型配置
# ============================================================
MODELS = {
    "Qwen3-Embedding-0.6B": {
        "name": "Qwen/Qwen3-Embedding-0.6B",
        "cache": os.path.join(os.getcwd(), "model_cache_qwen"),
        "kwargs": {"trust_remote_code": True, "tokenizer_kwargs": {"fix_mistral_regex": True}},
    },
    "Qwen3-Embedding-4B-GGUF": {
        "name": "Qwen/Qwen3-Embedding-4B-GGUF",
        "api_url": "http://127.0.0.1:8080",
        "is_api": True
    },
}


def load_model(config):
    """加载模型，支持 SentenceTransformer 和 GGUF"""
    if config.get("is_api"):
        api_url = config["api_url"]
        print(f"  通过 API 加载: {api_url}")
        t0 = time.time()
        model = APIEmbeddingWrapper(api_url)
        load_time = time.time() - t0
        return model, load_time

    cache_path = config["cache"]
    config_json = os.path.join(cache_path, "config.json")
    if os.path.exists(cache_path) and os.path.exists(config_json):
        print(f"  从本地加载: {cache_path}")
        load_path = cache_path
        local_only = True
    else:
        print(f"  从远程下载: {config['name']}")
        load_path = config["name"]
        local_only = False

    t0 = time.time()
    model = SentenceTransformer(load_path, local_files_only=local_only, **config["kwargs"])
    load_time = time.time() - t0

    # 首次下载后保存到本地
    if not local_only:
        model.save(cache_path)
        print(f"  模型已缓存至: {cache_path}")

    return model, load_time


def cosine_sim(a, b):
    """计算余弦相似度"""
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))


def run_test(model, model_name):
    """对单个模型运行全部测试用例"""
    print(f"\n{'='*60}")
    print(f"  模型: {model_name}")
    print(f"  维度: {model.get_sentence_embedding_dimension()}")
    print(f"{'='*60}")

    results = []
    # 批量编码所有文本（去重后）
    all_texts = list(set(
        [q for q, _, _ in TEST_CASES] + [c for _, c, _ in TEST_CASES]
    ))
    t0 = time.time()
    all_vecs = model.encode(all_texts, normalize_embeddings=True, show_progress_bar=False)
    encode_time = time.time() - t0
    # 构建文本 -> 向量的映射
    text2vec = {t: v for t, v in zip(all_texts, all_vecs)}

    for query, candidate, expected in TEST_CASES:
        score = cosine_sim(text2vec[query], text2vec[candidate])
        # 判断是否符合期望
        if expected == "high":
            passed = score >= 0.6
        else:
            passed = score < 0.6
        results.append((query, candidate, expected, score, passed))

    return results, encode_time


def main():
    print("=" * 60)
    print("  双模型语义匹配准确度对比测试")
    print("=" * 60)

    all_results = {}
    model_meta = {}

    for model_name, config in MODELS.items():
        print(f"\n>>> 加载模型: {model_name}")
        model, load_time = load_model(config)
        dim = model.get_sentence_embedding_dimension()
        model_meta[model_name] = {"load_time": load_time, "dim": dim}

        results, encode_time = run_test(model, model_name)
        all_results[model_name] = results
        model_meta[model_name]["encode_time"] = encode_time

        # 释放显存
        del model

    # ============================================================
    # 输出对比结果
    # ============================================================
    model_names = list(MODELS.keys())
    m1, m2 = model_names[0], model_names[1]

    # 手动定义类别边界（与 TEST_CASES 顺序一致）
    CATEGORIES = [
        ("1. 精确匹配", 0, 4),
        ("2. 近义改写", 4, 10),
        ("3. 逻辑反转", 10, 16),
        ("4. 学科限定差异", 16, 21),
        ("5. 长短文本匹配", 21, 24),
        ("6. 无关文本", 24, 29),
        ("7. 部分重叠但语义不同", 29, 34),
        ("8. 同义但用词差异大", 34, 39),
        ("9. 语序调整但语义不变", 39, 43),
        ("10. 包含冗余信息但核心语义一致", 43, 46),
        ("11. 否定+肯定转换", 46, 49),
        ("12. 专业 vs 通俗表述", 49, 52),
        ("13. 数字/单位转换", 52, 55),
        ("14. 隐含语义匹配", 55, 58),
        ("15. 易混淆概念区分", 58, 61),
    ]

    sep = "=" * 100
    print(f"\n\n{sep}")
    print("  双模型语义匹配对比结果")
    print(sep)

    # 模型基本信息
    for name in model_names:
        meta = model_meta[name]
        print(f"  [{name}] 维度={meta['dim']}, 加载耗时={meta['load_time']:.1f}s, 编码耗时={meta['encode_time']:.3f}s")
    print()

    # 全局统计
    m1_wins, m2_wins, ties = 0, 0, 0
    m1_pass, m2_pass = 0, 0
    cat_stats = []  # 分类别统计

    for cat_name, start, end in CATEGORIES:
        print(f"  ┌─ {cat_name} ──────────────────────────────────────────")

        cat_m1_pass, cat_m2_pass = 0, 0
        cat_m1_scores, cat_m2_scores = [], []

        for idx in range(start, end):
            r1 = all_results[m1][idx]
            r2 = all_results[m2][idx]
            query, candidate, expected, score1, pass1 = r1
            _, _, _, score2, pass2 = r2

            # 胜出判定
            if expected == "high":
                if score1 > score2 + 0.02:
                    winner = f"← {m1}"
                    m1_wins += 1
                elif score2 > score1 + 0.02:
                    winner = f"→ {m2}"
                    m2_wins += 1
                else:
                    winner = "≈ 平局"
                    ties += 1
            else:
                if score1 < score2 - 0.02:
                    winner = f"← {m1}"
                    m1_wins += 1
                elif score2 < score1 - 0.02:
                    winner = f"→ {m2}"
                    m2_wins += 1
                else:
                    winner = "≈ 平局"
                    ties += 1

            if pass1:
                m1_pass += 1
                cat_m1_pass += 1
            if pass2:
                m2_pass += 1
                cat_m2_pass += 1
            cat_m1_scores.append(score1)
            cat_m2_scores.append(score2)

            # 通过/失败标记
            mark1 = "✓" if pass1 else "✗"
            mark2 = "✓" if pass2 else "✗"

            # 分值差异高亮
            diff = abs(score1 - score2)
            diff_marker = " ★" if diff > 0.1 else ""

            print(f"  │ [{idx+1:>2}] 期望={expected:<4}  {m1}: {score1:.4f}{mark1}  {m2}: {score2:.4f}{mark2}  {winner}{diff_marker}")
            print(f"  │      查询: {query}")
            print(f"  │      候选: {candidate}")

        # 类别小计
        cat_count = end - start
        avg1 = np.mean(cat_m1_scores)
        avg2 = np.mean(cat_m2_scores)
        cat_stats.append((cat_name, cat_count, cat_m1_pass, cat_m2_pass, avg1, avg2))
        print(f"  └─ 小计: {m1} 通过 {cat_m1_pass}/{cat_count} (均分{avg1:.4f}) | {m2} 通过 {cat_m2_pass}/{cat_count} (均分{avg2:.4f})")
        print()

    # ============================================================
    # 总结统计
    # ============================================================
    total = len(TEST_CASES)
    print(sep)
    print("  总结统计")
    print(sep)

    # 分类别统计表
    print(f"\n  {'类别':<28} {'用例':>4}  {m1+' 通过':>12}  {m2+' 通过':>12}  {m1+' 均分':>12}  {m2+' 均分':>12}")
    print(f"  {'-'*96}")
    for cat_name, count, c1_pass, c2_pass, avg1, avg2 in cat_stats:
        print(f"  {cat_name:<28} {count:>4}  {c1_pass:>6}/{count:<5}  {c2_pass:>6}/{count:<5}  {avg1:>10.4f}    {avg2:>10.4f}")
    print(f"  {'-'*96}")
    print(f"  {'合计':<28} {total:>4}  {m1_pass:>6}/{total:<5}  {m2_pass:>6}/{total:<5}")

    # 最终得分
    print(f"\n  ┌──────────────────────────────────────────────┐")
    print(f"  │  通过率: {m1}: {m1_pass}/{total} ({m1_pass/total*100:.0f}%)")
    print(f"  │  通过率: {m2}: {m2_pass}/{total} ({m2_pass/total*100:.0f}%)")
    print(f"  │  胜负: {m1} {m1_wins}胜 | {m2} {m2_wins}胜 | 平局 {ties}")
    print(f"  └──────────────────────────────────────────────┘")
    print(sep)


if __name__ == "__main__":
    main()

