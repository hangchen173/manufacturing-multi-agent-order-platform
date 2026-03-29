import os
import sys
import csv
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

from config import Config
from infrastructure.vector_store import FAISSManager

def main():
    config = Config()
    
    print("正在初始化 FAISS 向量索引...")
    
    faiss_manager = FAISSManager(index_path=config.FAISS_INDEX_PATH)
    
    materials_file = config.STANDARD_MATERIALS_PATH
    
    if os.path.exists(materials_file):
        materials = []
        with open(materials_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                materials.append({
                    'sku_code': row['sku_code'],
                    'material_name': row['material_name'],
                    'specification': row['specification'],
                    'unit': row['unit'],
                    'reference_price': float(row['reference_price']),
                    'category': row['category'],
                    'text': f"{row['material_name']} {row['specification']} {row['category']}"
                })
        
        faiss_manager.clear_index()
        faiss_manager.add_documents(materials)
        print(f"已添加 {len(materials)} 个标准物料到索引")
        print(f"当前索引中共有 {faiss_manager.get_document_count()} 个文档")
        
        print("\n物料列表:")
        for mat in materials:
            print(f"  - {mat['sku_code']}: {mat['material_name']} {mat['specification']}")
    else:
        print(f"警告: 未找到标准物料文件 {materials_file}")
        print("请确保 data/standard_materials.csv 存在")
    
    print("\nFAISS 索引初始化完成！")

if __name__ == "__main__":
    main()
