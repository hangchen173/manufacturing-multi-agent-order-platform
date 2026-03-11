import os
import sys
import json
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.vector_store.faiss_manager import FAISSManager
from config import Config

def main():
    config = Config()
    
    print("正在初始化 FAISS 向量索引...")
    
    faiss_manager = FAISSManager(index_path=config.FAISS_INDEX_PATH)
    
    materials_file = os.path.join(config.STANDARD_MATERIALS_PATH, "sample_materials.json")
    
    if os.path.exists(materials_file):
        with open(materials_file, 'r', encoding='utf-8') as f:
            materials = json.load(f)
        
        faiss_manager.add_documents(materials)
        print(f"已添加 {len(materials)} 个标准物料到索引")
        print(f"当前索引中共有 {faiss_manager.get_document_count()} 个文档")
    else:
        print(f"警告: 未找到标准物料文件 {materials_file}")
        print("请先在 data/standard_materials/ 目录下添加标准物料数据")
    
    print("FAISS 索引初始化完成！")

if __name__ == "__main__":
    main()
