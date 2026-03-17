# test_hybrid_search.py
from app.services.nlp_service import nlp_engine

def run_hybrid_tests():
    print("="*50)
    print("🚀 混合检索 (Hybrid Search) 效果验证测试")
    print("="*50)

    # 1. 模拟注入纯净的小型题库数据
    mock_data = [
        {"id": 1, "question": "匀速圆周运动的向心力大小怎么算？", "answer": "F = m*v^2/r"},
        {"id": 2, "question": "向心加速度与线速度和角速度的关系是什么？", "answer": "a = v*w"},
        {"id": 3, "question": "物体做平抛运动时的飞行时间由什么决定？", "answer": "仅由下落高度h决定: t = sqrt(2h/g)"},
        {"id": 4, "question": "自由落体运动的下落高度计算法则。", "answer": "h = 1/2*g*t^2"},
        {"id": 5, "question": "一元二次方程 ax^2+bx+c=0 的求根公式是什么？", "answer": "x = (-b ± sqrt(b^2-4ac)) / 2a"}
    ]

    print("\n📦 正在构建测试索引...")
    # 清空现有索引，避免干扰
    nlp_engine._corpus_tensor = None
    nlp_engine._corpus_data = []
    nlp_engine._bm25_idf = {}
    nlp_engine._bm25_inverted = {}
    nlp_engine._bm25_doc_lens = []
    nlp_engine._std_q_map = {}
    
    # 逐条热更新入库
    for item in mock_data:
        # 模拟生成向量
        emb = nlp_engine.encode(item["question"])
        nlp_engine.add_to_index(
            question=item["question"],
            embedding=emb,
            answer=item["answer"],
            reason="测试生成"
        )
    print("✅ 测试索引构建完毕！")

    # 2. 定义测试用例
    test_cases = [
        {
            "name": "测试 1: 语义碾压 (Embedding 立功, BM25 抓瞎)",
            "query": "那个抛出去的东西在天上飞多久和啥有关？",
            "target_id": 3,
            "desc": "用户口语化提问，毫无物理专业词汇，BM25 找不到字面重合，必须靠 Embedding 的语义理解力挽狂澜。"
        },
        {
            "name": "测试 2: 关键词绝杀 (BM25 立功, Embedding 迷糊)",
            "query": "求根公式",
            "target_id": 5,
            "desc": "极短查询，Embedding 可能会因为上下文太少给出一个不上不下的余弦分数（例如 0.75），但 BM25 会精准命中这四个字，强行保送过阈值。"
        },
        {
            "name": "测试 3: O(1) 极速拦截 (引擎层拦截)",
            "query": "自由落体运动的下落高度计算法则。",
            "target_id": 4,
            "desc": "一字不差的题目，直接命中 std_q 哈希表，应该返回 1.0 的置信度，并且不会有双路对比的日志。"
        }
    ]

    # 3. 执行测试
    print("\n" + "="*50)
    for i, tc in enumerate(test_cases, 1):
        print(f"\n▶️ {tc['name']}")
        print(f"   输入提问: [{tc['query']}]")
        print(f"   预期目标: ID {tc['target_id']}")
        
        # 调用我们重构的双路搜索
        best_match, score = nlp_engine.search_best_match(tc['query'], threshold=0.80)
        
        if best_match:
            actual_id = best_match.get('id', -1)
            is_success = (actual_id == tc['target_id'])
            icon = "✅ Pass" if is_success else "❌ Fail"
            print(f"   {icon} | 命中 ID: {actual_id} | 最终综合置信度: {score:.4f}")
            print(f"   找出的题目: {best_match['question']}")
        else:
            print(f"   ❌ Fail | 未找到匹配项或低于阈值 0.80")

if __name__ == "__main__":
    run_hybrid_tests()
