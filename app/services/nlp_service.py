#app/services/nlp_service.py
import jieba
import os
import json
import torch
import logging
import re
import math
import numpy as np
from sentence_transformers import SentenceTransformer, util

class NLPService:
    _instance = None
    model = None
    device = None
    # 停用词集合
    stopwords = set()
    # --- ML 核心数据结构 ---
    # corpus_tensor: 存放所有题目的向量矩阵 (N, 1024)，驻留在 GPU
    _corpus_tensor = None
    # corpus_data: 存放题目元数据 (ID, 答案等)，驻留在内存
    _corpus_data = []
    # --- BM25+ 核心数据结构 ---
    _BM25_K1 = 1.5
    _BM25_B = 0.75
    _BM25_DELTA = 1.0
    _bm25_idf = {}         # key: word, value: idf_score
    _bm25_inverted = {}    # key: word, value: {doc_idx: freq}
    _bm25_doc_lens = []    # 文档长度列表，索引对齐 _corpus_data
    _bm25_avgdl = 0.0      # 平均文档长度
    _std_q_map = {}         # std_q -> corpus_data 索引，O(1) 精确匹配
    _RRF_K = 20             # RRF 融合参数，小语料用小值拉开排名差距
    _RECALL_TOP_K = 10      # 每路召回数量，2万词库取 Top-10 已充分覆盖
    MODEL_PATH = os.path.join(os.getcwd(), 'model_cache_qwen')
    MODEL_NAME = 'Qwen/Qwen3-Embedding-0.6B'
    # 定义停用词路径
    STOPWORDS_PATH = os.path.join(os.getcwd(), 'stopwords.txt')
    # 定义类级别的分类配置
    CATEGORY_CONFIG = {
        "subject": {
            "name": "学科限定",
            "words": {'英文', '英语', '语文', '数学', '物理', '化学', '生物', '地理', '历史', '计算机', '政治'},
            "missing_penalty": 0.25,
            "redundant_penalty": 0.02
        },
        "logic": {
            "name": "逻辑反转",
            "words": {
                '不', '非', '除了', '错误', '正确', '属于', '不属于', '必须', '存在', '不存在','不包含','没有'
                '符合', '不符合', '不是', '一定', '否定', '无关', '增加', '减少', '上升', '下降',
                '加速', '减速', '大于', '小于', '等于','不等于', '大于等于', '小于等于',  '正数',
                '负数', '正相关', '负相关', '正电荷','不得','内部', '外部','主动', '被动','正', '负',
                '负电荷', '吸引', '排斥', '引力', '斥力', '正极', '负极', '阳极', '阴极', '正反馈', '负反馈',
                '高温', '低温', '干燥', '潮湿', '优点', '缺点', '成功', '失败', '安全', '危险',
                '主观', '客观', '褒义', '贬义', '同义', '反义', '肯定', '疑问', '反问', '正反应', '逆反应'
                '主语', '宾语', '唯物主义', '唯心主义', '酸性', '碱性', '溶解', '沉淀', '吸热', '放热',
            },
            "missing_penalty": 0.4,
            "redundant_penalty": 0.2
        },
        "format": {
            "name": "题型限制",
            "words": {'填空', '多选', '单选', '判断', '简答', '作文', '短文'},
            "missing_penalty": 0.04,
            "redundant_penalty": 0.02
        }
    }

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(NLPService, cls).__new__(cls)
            cls._instance._load_model()
            cls._instance._load_stopwords()
            # 初始化时同步自定义词库
            cls._instance._sync_custom_words()
        return cls._instance

    def _sync_custom_words(self):
        """将逻辑词同步到 jieba，防止被切碎"""
        count = 0
        for cat in self.CATEGORY_CONFIG.values():
            for word in cat['words']:
                # 设定高词频 2000，确保原子化不被切分
                jieba.add_word(word, freq=2000, tag='nz')
                count += 1
        print(f"[NLPService] 已锁定 {count} 个逻辑原子词，防止分词切碎")

    def _load_stopwords(self):
        """加载自定义停用词表"""
        if os.path.exists(self.STOPWORDS_PATH):
            try:
                with open(self.STOPWORDS_PATH, 'r', encoding='utf-8') as f:
                    # 过滤掉空行
                    self.stopwords = set([line.strip() for line in f if line.strip()])
                print(f"停用词表加载成功: {len(self.stopwords)} 个词")
            except Exception as e:
                logging.error(f"停用词加载失败: {e}")
        else:
            print("未找到 stopwords.txt，预处理将跳过停用词过滤")

    def clean_prefix(self, text):
        """
        统一清洗逻辑：彻底剔除题号前缀（包括数字、字母、中文数字、各种标点）
        """
        if not text: return ""
        # 增强正则：支持中文逗号 '，'、句号 '。' 以及各种粘连格式
        pattern = r'^\s*[\(（]?(\d+|[a-zA-Z]+|[一二三四五六七八九十百]+)[\)）]?[\.\、\．\:\：\,\，\s\-\—\s]+'
        cleaned = re.sub(pattern, '', text)
        return cleaned.strip() if cleaned.strip() else text

    def tokenize(self, text):
        """
        核心分词逻辑，返回 token 列表。复用于预处理和 BM25 索引。
        """
        if not text:
            return []
        # 1. 基础清洗 (保留汉字、英文字母、数字)
        text = self.clean_prefix(text).lower()
        words = jieba.cut(text)
        # --- 过滤停用词 + 提取核心 (只留汉字字母，排除数字) ---
        core_words = []
        for word in words:
            # A. 命中停用词，去掉
            if word in self.stopwords:
                continue
            # B. 排除纯数字题号残留
            if re.match(r'^\d+$', word):
                continue
            # C. 只保留核心字符
            cleaned_word = "".join(re.findall(r'[\u4e00-\u9fa5a-zA-Z0-9]', word))
            if cleaned_word:
                core_words.append(cleaned_word)

        if not core_words:
            fallback = "".join(re.findall(r'[\u4e00-\u9fa5a-zA-Z0-9]', text))
            if fallback:
                return [fallback]
        return core_words

    def standardize_text(self, text):
        """
        核心预处理管道拼接
        """
        return "".join(self.tokenize(text))

    def _determine_device(self):
        if torch.cuda.is_available():
            return "cuda"
        elif torch.backends.mps.is_available():
            return "mps"
        return "cpu"

    def _load_model(self):
        if self.model is not None:
            return
        print("正在初始化 NLP 引擎...")
        # 1. 配置设备
        self.device = self._determine_device()
        print(f"计算设备: {self.device.upper()}")
        # 2. 检查本地模型是否完整
        local_config_path = os.path.join(self.MODEL_PATH, 'config.json')
        is_local_run = False
        if os.path.exists(self.MODEL_PATH) and os.path.exists(local_config_path):
            print(f"检测到完整的本地模型，正在离线加载: {self.MODEL_PATH}")
            load_path = self.MODEL_PATH
            is_local_run = True
        else:
            print(f"本地未找到完整模型 (缺失 config.json)，准备从 HuggingFace 下载: {self.MODEL_NAME}")
            print(f"   (下载完成后将自动保存至: {self.MODEL_PATH})")
            load_path = self.MODEL_NAME
            is_local_run = False
        try:
            # 3. 加载模型
            self.model = SentenceTransformer(
                load_path,
                device=self.device,
                trust_remote_code=True,
                local_files_only=is_local_run,
                tokenizer_kwargs={"fix_mistral_regex": True}
            )
            # 4. 获取并保存模型维度
            self.embedding_dim = self.model.get_sentence_embedding_dimension()
            print(f"模型加载完毕 | 维度: {self.embedding_dim}")
            # 5. 如果是刚从网络下载的，保存为标准格式到本地
            if not is_local_run:
                print(f"正在将模型保存为标准格式: {self.MODEL_PATH} ...")
                # 这步会将杂乱的缓存文件转存为 clean 的 config.json + model.safetensors
                self.model.save(self.MODEL_PATH)
                print("模型已保存，下次启动将自动进入离线模式")
        except Exception as e:
            logging.error(f"模型加载失败: {e}")
            print("建议操作：请删除 model_cache_qwen 文件夹后重试，确保网络畅通。")
            raise e

    @staticmethod
    def clean_text(text):
        """保留用于辅助的旧清洗函数"""
        if not text: return ""
        text = str(text).lower()
        return re.sub(r'[^\u4e00-\u9fa5a-zA-Z0-9]', '', text)

    def encode(self, text):
        """单条文本向量化"""
        if not self.model or not text: return []
        #  使用标准化后的文本进行编码，保证存入向量库的是纯净语义
        std_text = self.standardize_text(text)
        with torch.no_grad():
            vector = self.model.encode(std_text, convert_to_numpy=True, normalize_embeddings=True)
        return vector.tolist()

    def refresh_index(self, app_context_model):
        """构建索引：从数据库加载数据"""
        print("正在构建向量索引矩阵...")
        try:
            all_questions = app_context_model.query.all()
            embeddings, metadata = [], []
            for q in all_questions:
                if not q.embedding: continue
                try:
                    emb_vec = json.loads(q.embedding)
                    if len(emb_vec) == self.embedding_dim:
                        embeddings.append(emb_vec)
                        metadata.append({
                            "id": q.id,
                            "question": q.question,
                            "std_q": q.std_q,
                            "answer": q.answer,
                            "options": q.options,
                            "reason": q.reason
                        })
                    else:
                        pass
                except:
                    continue

            if not embeddings:
                print(f"索引未构建：未发现符合 {self.embedding_dim} 维度的向量数据")
                print("请运行 rebuild_vectors.py 以根据新模型重刷数据库")
                return
            self._corpus_tensor = torch.tensor(embeddings, dtype=torch.float32).to(self.device)
            self._corpus_data = metadata
            
            # --- 增加构建 BM25 稀疏倒排索引 ---
            self._build_bm25_index()

            mem_size = self._corpus_tensor.element_size() * self._corpus_tensor.nelement()
            print(f"索引构建完成！有效数据: {len(metadata)} 条 (显存: {mem_size / 1024 / 1024:.2f} MB)")

        except Exception as e:
            logging.error(f"索引构建失败: {e}")

    def _build_bm25_index(self):
        """构建全量 BM25 倒排索引"""
        print("正在构建 BM25+ 倒排索引...")
        self._bm25_idf = {}
        self._bm25_inverted = {}
        self._bm25_doc_lens = []
        
        N = len(self._corpus_data)
        if N == 0:
            return
            
        total_len = 0
        df = {} # word -> doc count
        
        for idx, item in enumerate(self._corpus_data):
            # 将原始题目进行 tokenize
            tokens = self.tokenize(item.get('question', ''))
            doc_len = len(tokens)
            self._bm25_doc_lens.append(doc_len)
            total_len += doc_len
            
            # 统计词频
            tf = {}
            for t in tokens:
                tf[t] = tf.get(t, 0) + 1
                
            # 更新 df 和 inverted matrix
            for t, freq in tf.items():
                if t not in self._bm25_inverted:
                    self._bm25_inverted[t] = {}
                self._bm25_inverted[t][idx] = freq
                df[t] = df.get(t, 0) + 1
                
        self._bm25_avgdl = total_len / N if N > 0 else 0
        
        # 计算 IDF, 采用标准的 Robertson-Sparck Jones IDF 对取正公式
        for t, count in df.items():
            # 加平滑处理避免负数
            idf = math.log(((N - count + 0.5) / (count + 0.5)) + 1)
            self._bm25_idf[t] = idf
        
        # 构建 std_q -> index 哈希映射，供精确匹配 O(1) 查找
        self._std_q_map = {}
        for idx, item in enumerate(self._corpus_data):
            sq = item.get('std_q')
            if sq:
                self._std_q_map[sq] = idx
            
        print(f"BM25+ 索引构建完成，词表大小: {len(self._bm25_idf)} | 精确匹配表: {len(self._std_q_map)}")

    def verify_match_quality(self, user_query, candidate_question, original_score):
        """
        对向量搜索的结果进行关键词层面的二次校验 (分层级动态惩罚版)
        :param user_query: 用户输入的原始文本
        :param candidate_question: 数据库匹配到的原始题目
        :param original_score: 向量匹配的原始得分 (0.0 - 1.0)
        :return: 修正后的最终得分
        """
        # 1. 强制 1.0 逻辑保持不变 (如果是精确匹配，无需校验)
        if original_score >= 0.95:
            return original_score
        # --- A. 准备数据 ---
        # 使用 lcut 得到列表，转为 set 方便计算交集
        query_words = set(jieba.lcut(user_query))
        candidate_words = set(jieba.lcut(candidate_question))
        # --- B. 定义分层级惩罚配置 ---
        category_config = self.CATEGORY_CONFIG
        total_penalty = 0.0
        # --- C. 遍历配置进行校验 ---
        for cat_key, config in category_config.items():
            target_words = config["words"]
            # 检查每一个敏感词
            for word in target_words:
                # 场景 1: 缺失惩罚 (用户有，题库无)
                if word in query_words and word not in candidate_words:
                    penalty = config["missing_penalty"]
                    total_penalty += penalty
                    print(f"[{config['name']}] 属性缺失: 用户要求[{word}] -> 扣分 {penalty}")
                # 场景 2: 冗余惩罚 (用户无，题库有)
                elif word not in query_words and word in candidate_words:
                    penalty = config["redundant_penalty"]
                    total_penalty += penalty
                    print(f"[{config['name']}] 属性冗余: 题库包含[{word}] -> 扣分 {penalty}")
        # --- D. 关键词重合度 (覆盖率) ---
        intersection = query_words & candidate_words
        if len(query_words) > 0:
            coverage = len(intersection) / len(query_words)
        else:
            coverage = 0
        # --- E. 最终分数融合 ---
        # 公式：(向量分 * 0.95) + (覆盖率 * 0.05) - 总惩罚
        base_score = (original_score * 0.95) + (coverage * 0.05)
        final_score = base_score - total_penalty
        # 限制范围在 0.0 到 1.0 之间
        final_score = max(0.0, min(1.0, final_score))
        print(
            f"校验详情 | 原始分:{original_score:.4f} | 覆盖率:{coverage:.4f} | 惩罚:-{total_penalty:.4f} | 最终:{final_score:.4f}")
        return final_score

    def _bm25_plus_search(self, query_tokens, top_k=20):
        """执行 BM25+ 召回"""
        if not self._bm25_doc_lens or self._bm25_avgdl == 0:
            return []
            
        scores = {}  # {doc_idx: score}
        for q in set(query_tokens):  # 去重避免重复累加
            if q not in self._bm25_inverted:
                continue
            idf = self._bm25_idf.get(q, 0)
            for doc_idx, freq in self._bm25_inverted[q].items():
                doc_len = self._bm25_doc_lens[doc_idx]
                numerator = freq * (self._BM25_K1 + 1)
                denominator = freq + self._BM25_K1 * (
                    1 - self._BM25_B + self._BM25_B * (doc_len / self._bm25_avgdl)
                )
                # BM25+ 的 delta 项下限保护
                q_score = idf * (numerator / denominator + self._BM25_DELTA)
                scores[doc_idx] = scores.get(doc_idx, 0) + q_score
                
        # 提取 top_k (如果数据多，建议用 heapq)
        sorted_hits = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:top_k]
        return sorted_hits

    def _rrf_merge(self, bm25_hits, emb_hits, k=60):
        """
        RRF (Reciprocal Rank Fusion) 融合
        bm25_hits: [(doc_idx, bm25_score), ...] 已经按分数降序
        emb_hits:  [(doc_idx, emb_score), ...]  已经按分数降序
        """
        rrf_scores = {}
        
        for rank, (doc_idx, _) in enumerate(bm25_hits):
            rrf_scores[doc_idx] = rrf_scores.get(doc_idx, 0) + 1.0 / (k + rank + 1)
            
        for rank, (doc_idx, _) in enumerate(emb_hits):
            rrf_scores[doc_idx] = rrf_scores.get(doc_idx, 0) + 1.0 / (k + rank + 1)
            
        # 按照 RRF score 排序返回最终结果
        final_sorted = sorted(rrf_scores.items(), key=lambda x: x[1], reverse=True)
        return final_sorted

    def search_best_match(self, query_text, threshold=0.80):
        """标准化双路召回搜索 + RRF融合"""
        if self.model is None or self._corpus_tensor is None or len(self._corpus_data) == 0:
            return None, 0
            
        # 1. 解析查询词
        query_tokens = self.tokenize(query_text)
        std_query = "".join(query_tokens)
        
        # 快速路径：O(1) 精确匹配，跳过全部向量与 BM25 计算
        if std_query in self._std_q_map:
            return self._corpus_data[self._std_q_map[std_query]], 1.0
        
        # 2. 向量化运算 (Embedding Top-K)
        with torch.no_grad():
            query_emb = self.model.encode(std_query, convert_to_tensor=True, device=self.device)
        cosine_scores = util.cos_sim(query_emb, self._corpus_tensor)[0]
        
        top_k = min(self._RECALL_TOP_K, len(self._corpus_data))
        emb_topk_val, emb_topk_idx = torch.topk(cosine_scores, top_k)
        emb_hits = [(idx.item(), score.item()) for idx, score in zip(emb_topk_idx, emb_topk_val)]
        
        # 3. BM25+ 稀疏查询 (BM25 Top-K)
        bm25_hits = self._bm25_plus_search(query_tokens, top_k=top_k)
        
        # 4. RRF 融合
        final_hits = self._rrf_merge(bm25_hits, emb_hits, k=self._RRF_K)
        if not final_hits:
            return None, 0
            
        # 5. 复合置信度：RRF 归一化 与 Embedding 余弦分 取 max
        best_idx, rrf_score = final_hits[0]
        candidate = self._corpus_data[best_idx]
        best_emb_score = cosine_scores[best_idx].item()
        
        # RRF 归一化到 [0, 1]（理论最大值 = 双路都排 Top-1）
        max_rrf =  2/ (self._RRF_K + 1)
        rrf_confidence = min(rrf_score / max_rrf, 1.0)
        confidence = max(best_emb_score, rrf_confidence)
        
        # 双路对比日志
        bm25_top = bm25_hits[0][0] if bm25_hits else -1
        emb_top = emb_hits[0][0]
        print(f"[双路召回] BM25 Top1: idx={bm25_top} | Emb Top1: idx={emb_top} | RRF Winner: idx={best_idx} | emb={best_emb_score:.4f} rrf_conf={rrf_confidence:.4f} -> confidence={confidence:.4f}")
            
        if confidence >= threshold:
            return candidate, confidence
            
        return None, 0
    def add_to_index(self, question, embedding, answer, reason, options=None):
        """热更新索引"""
        if self.model is None: return
        # 1. 构建元数据
        new_metadata = {
            "id": None,
            "question": question,
            "std_q": self.standardize_text(question),
            "answer": answer,
            "options": options,
            "reason": reason
        }
        # 2. 更新矩阵和元数据
        new_vec_tensor = torch.tensor([embedding], dtype=torch.float32).to(self.device)
        if self._corpus_tensor is None:
            self._corpus_tensor = new_vec_tensor
            self._corpus_data = [new_metadata]
        else:
            self._corpus_tensor = torch.cat([self._corpus_tensor, new_vec_tensor], dim=0)
            self._corpus_data.append(new_metadata)
            
        # 3. 热更新 BM25+ (增量更新，避免全局重建)
        new_idx = len(self._corpus_data) - 1
        tokens = self.tokenize(question)
        doc_len = len(tokens)
        self._bm25_doc_lens.append(doc_len)
        
        tf = {}
        for t in tokens:
            tf[t] = tf.get(t, 0) + 1
            
        for t, freq in tf.items():
            if t not in self._bm25_inverted:
                self._bm25_inverted[t] = {}
            self._bm25_inverted[t][new_idx] = freq
            # 近似: 假设增量对全局 IDF 影响极小，暂时跳过全量重新计算 IDF 和 avgdl（提升热插入性能）。
            if t not in self._bm25_idf:
                self._bm25_idf[t] = 1.0  # 新词赋予一个基础 IDF
                
        # 更新 avgdl
        N = len(self._corpus_data)
        if N > 0:
            self._bm25_avgdl = ((self._bm25_avgdl * (N - 1)) + doc_len) / N
        
        # 同步精确匹配哈希表
        sq = new_metadata.get('std_q')
        if sq:
            self._std_q_map[sq] = new_idx
            
        print(f"索引热更新成功 | 当前矩阵规模: {self._corpus_tensor.shape[0]} | BM25同步完毕")

nlp_engine = NLPService()