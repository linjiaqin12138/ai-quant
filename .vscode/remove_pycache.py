import os
import shutil
import sys

def remove_pycache(root_path: str) -> None:
    """
    递归删除指定路径下所有 __pycache__ 文件夹
    """
    for dirpath, dirnames, _ in os.walk(root_path, topdown=False):
        if '__pycache__' in dirnames:
            pycache_path = os.path.join(dirpath, '__pycache__')
            print(f"删除：{pycache_path}")
            shutil.rmtree(pycache_path)

def main():
    if len(sys.argv) != 2:
        print("用法: python remove_pycache.py <path>")
        sys.exit(1)
    
    target_path = sys.argv[1]
    if not os.path.exists(target_path):
        print("路径不存在")
        sys.exit(1)
    
    remove_pycache(target_path)

if __name__ == "__main__":
    main()