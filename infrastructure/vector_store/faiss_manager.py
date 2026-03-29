import os
import pickle
import logging
from typing import List, Dict, Optional, Tuple
import numpy as np
import faiss
from sentence_transformers import SentenceTransformer

from domain.constants import DEFAULT_EMBEDDING_MODEL, FAISS_INDEX_DIMENSION
from domain.exceptions import VectorStoreException

class FAISSManager:
    def __init__(
        self, 
        index_path: str, 
        model_name: str = DEFAULT_EMBEDDING_MODEL,
        dimension: int = FAISS_INDEX_DIMENSION
    ):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.index_path = index_path
        self.model_name = model_name
        self.dimension = dimension
        self.model = None
        self.index = None
        self.metadata: List[Dict] = []
        
        self._initialize()
    
    def _initialize(self) -> None:
        self._ensure_index_directory()
        self._load_model()
        self._load_or_create_index()
    
    def _ensure_index_directory(self) -> None:
        if not os.path.exists(self.index_path):
            os.makedirs(self.index_path, exist_ok=True)
            self.logger.info(f"创建索引目录: {self.index_path}")
    
    def _load_model(self) -> None:
        try:
            self.logger.info(f"加载嵌入模型: {self.model_name}")
            self.model = SentenceTransformer(self.model_name)
            self.logger.info("嵌入模型加载完成")
        except Exception as e:
            self.logger.error(f"嵌入模型加载失败: {str(e)}")
            raise VectorStoreException(
                f"嵌入模型加载失败: {str(e)}",
                details={"model_name": self.model_name, "error": str(e)}
            )
    
    def _get_index_file_path(self) -> str:
        return os.path.join(self.index_path, "index.faiss")
    
    def _get_metadata_file_path(self) -> str:
        return os.path.join(self.index_path, "metadata.pkl")
    
    def _load_or_create_index(self) -> None:
        index_file = self._get_index_file_path()
        metadata_file = self._get_metadata_file_path()
        
        if os.path.exists(index_file) and os.path.exists(metadata_file):
            self._load_existing_index(index_file, metadata_file)
        else:
            self._create_new_index()
    
    def _load_existing_index(self, index_file: str, metadata_file: str) -> None:
        try:
            self.logger.info(f"加载现有索引: {index_file}")
            self.index = faiss.read_index(index_file)
            
            with open(metadata_file, 'rb') as f:
                self.metadata = pickle.load(f)
            
            self.logger.info(f"索引加载完成，共 {len(self.metadata)} 条记录")
            
        except Exception as e:
            self.logger.warning(f"索引加载失败，将创建新索引: {str(e)}")
            self._create_new_index()
    
    def _create_new_index(self) -> None:
        self.logger.info("创建新的FAISS索引")
        self.index = faiss.IndexFlatL2(self.dimension)
        self.metadata = []
    
    def add_documents(self, documents: List[Dict[str, str]]) -> int:
        if not documents:
            self.logger.warning("没有文档需要添加")
            return 0
        
        try:
            texts = [doc.get('text', '') for doc in documents]
            
            self.logger.info(f"为 {len(texts)} 条文档生成嵌入向量")
            embeddings = self.model.encode(texts, convert_to_numpy=True)
            
            self.index.add(embeddings.astype('float32'))
            self.metadata.extend(documents)
            
            self._save_index()
            
            self.logger.info(f"成功添加 {len(documents)} 条文档")
            return len(documents)
            
        except Exception as e:
            self.logger.error(f"添加文档失败: {str(e)}")
            raise VectorStoreException(
                f"添加文档失败: {str(e)}",
                details={"document_count": len(documents), "error": str(e)}
            )
    
    def search(self, query: str, k: int = 5) -> List[Tuple[Dict, float]]:
        if not query or not query.strip():
            self.logger.warning("查询文本为空")
            return []
        
        if self.index.ntotal == 0:
            self.logger.warning("索引为空，无法搜索")
            return []
        
        try:
            query_embedding = self.model.encode([query], convert_to_numpy=True)
            actual_k = min(k, self.index.ntotal)
            
            distances, indices = self.index.search(query_embedding.astype('float32'), actual_k)
            
            results = []
            for i, idx in enumerate(indices[0]):
                if idx >= 0 and idx < len(self.metadata):
                    results.append((self.metadata[idx], float(distances[0][i])))
            
            return results
            
        except Exception as e:
            self.logger.error(f"搜索失败: {str(e)}")
            raise VectorStoreException(
                f"搜索失败: {str(e)}",
                details={"query": query, "k": k, "error": str(e)}
            )
    
    def _save_index(self) -> None:
        try:
            self._ensure_index_directory()
            
            index_file = self._get_index_file_path()
            metadata_file = self._get_metadata_file_path()
            
            faiss.write_index(self.index, index_file)
            
            with open(metadata_file, 'wb') as f:
                pickle.dump(self.metadata, f)
            
            self.logger.info(f"索引已保存到: {self.index_path}")
            
        except Exception as e:
            self.logger.error(f"索引保存失败: {str(e)}")
            raise VectorStoreException(
                f"索引保存失败: {str(e)}",
                details={"index_path": self.index_path, "error": str(e)}
            )
    
    def get_document_count(self) -> int:
        return len(self.metadata)
    
    def get_index_size(self) -> int:
        return self.index.ntotal if self.index else 0
    
    def clear_index(self) -> None:
        self.logger.info("清空索引")
        self.index = faiss.IndexFlatL2(self.dimension)
        self.metadata = []
        self._save_index()
    
    def update_document(self, index: int, document: Dict[str, str]) -> bool:
        if index < 0 or index >= len(self.metadata):
            self.logger.warning(f"无效的索引: {index}")
            return False
        
        self.metadata[index] = document
        self._save_index()
        return True
    
    def remove_document(self, index: int) -> bool:
        if index < 0 or index >= len(self.metadata):
            self.logger.warning(f"无效的索引: {index}")
            return False
        
        self.metadata.pop(index)
        
        texts = [doc.get('text', '') for doc in self.metadata]
        if texts:
            embeddings = self.model.encode(texts, convert_to_numpy=True)
            self.index = faiss.IndexFlatL2(self.dimension)
            self.index.add(embeddings.astype('float32'))
        else:
            self.index = faiss.IndexFlatL2(self.dimension)
        
        self._save_index()
        return True
