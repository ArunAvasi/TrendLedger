

from pathlib import Path
import sys

project_root = Path(__file__).parent.parent.resolve()
sys.path.append(str(project_root))

from etl.config     import engine
from backend.models import Base

def main():
    Base.metadata.create_all(engine)
    print("✅ Tables created or already exist.")

if __name__ == "__main__":
    main()