"""
scripts/create_views.py
Creates SQL views in the database to simplify querying.
Usage: python -m scripts.create_views
"""
 
import logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
 
from app.agent import initialize
from app.views import create_all_views, list_views
 
if __name__ == "__main__":
    initialize()
 
    print(f"\n{'='*50}")
    print("Creating SQL views...")
    print(f"{'='*50}\n")
 
    results = create_all_views()
    for view_name, success in results.items():
        status = "✅" if success else "❌"
        print(f"  {status} {view_name}")
 
    print(f"\nExisting views in database:")
    for v in list_views():
        print(f"  • {v}")
 
    print(f"\n{'='*50}\n")