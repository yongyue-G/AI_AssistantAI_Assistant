import pdfplumber
import jieba
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np

# utils.py
import fitz  # PyMuPDF

def extract_text_with_pages(pdf_source):
    """使用 PyMuPDF 极速提取文字"""
    pages_data = []
    try:
        # 适配文件流和路径字符串
        if isinstance(pdf_source, str):
            doc = fitz.open(pdf_source)
        else:
            doc = fitz.open(stream=pdf_source.read(), filetype="pdf")
            
        for i, page in enumerate(doc):
            text = page.get_text()
            if text:
                pages_data.append({"page_num": i + 1, "text": text})
        doc.close()
    except Exception as e:
        return [{"page_num": 0, "text": f"解析出错: {e}"}]
    return pages_data

def chunk_with_metadata(pages_data, chunk_size=500, overlap=50):
    """切片时，让每一块肉都带上它原本的页码骨头"""
    chunks = []
    for page in pages_data:
        text = page["text"]
        page_num = page["page_num"]
        
        if len(text) < chunk_size:
            chunks.append({"page_num": page_num, "text": text})
            continue
            
        for i in range(0, len(text), chunk_size - overlap):
            chunk_text = text[i : i + chunk_size]
            chunks.append({"page_num": page_num, "text": chunk_text})
    return chunks

class LightRAG:
    def __init__(self, chunks):
        self.chunks = chunks  # 这里的 chunks 变成了一个包含页码和文字的字典列表
        # 把纯文字抽出来去算数学向量
        self.texts = [c["text"] for c in chunks]
        self.vectorizer = TfidfVectorizer(tokenizer=jieba.lcut, token_pattern=None)
        self.tfidf_matrix = self.vectorizer.fit_transform(self.texts)

    def search(self, query, top_k=3):
        if not self.chunks:
            return []
        
        # 精确匹配优先
        exact_matches = [c for c in self.chunks if query in c["text"]]
        if exact_matches:
            return exact_matches[:top_k]

        # 模糊向量匹配
        query_vec = self.vectorizer.transform([query])
        sims = cosine_similarity(query_vec, self.tfidf_matrix)[0]
        top_indices = np.argsort(sims)[-top_k:][::-1]
        
        # 过滤低分结果
        results = [self.chunks[i] for i in top_indices if sims[i] > 0.05]
        return results  # 注意：现在返回的是 [{"page_num": 10, "text": "..."}] 这种格式