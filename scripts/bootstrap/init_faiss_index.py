import sys
import os
from pathlib import Path
from tempfile import TemporaryDirectory

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

from config import Config
from infrastructure.vector_store import FAISSManager
from infrastructure.vector_store.catalog import load_material_catalog, validate_catalog_index

def main():
    config = Config()
    
    print("正在初始化 FAISS 向量索引...")
    
    materials = load_material_catalog(config.data.standard_materials_path)
    target = Path(config.data.faiss_index_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(dir=target.parent, prefix="index-build-") as work:
        faiss_manager = FAISSManager(index_path=work)
        faiss_manager.add_documents(materials)
        validate_catalog_index(materials, faiss_manager.metadata, faiss_manager.index)
        target.mkdir(parents=True, exist_ok=True)
        for name in ("index.faiss", "metadata.pkl"):
            os.replace(Path(work) / name, target / name)
    print(f"已建立并验证 {len(materials)} 条标准物料索引")
    
    print("\nFAISS 索引初始化完成！")

if __name__ == "__main__":
    main()
