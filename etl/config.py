
import os
from pathlib import Path
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

project_root = Path(__file__).parent.parent.resolve()
load_dotenv(project_root / ".env")

USER     = os.getenv("user")
PASSWORD = os.getenv("password")
HOST     = os.getenv("host")
PORT     = os.getenv("port")
DBNAME   = os.getenv("dbname")

if not all([USER, PASSWORD, HOST, PORT, DBNAME]):
    raise RuntimeError("One or more DB connection vars are missing in .env")

db_url = f"postgresql://{USER}:{PASSWORD}@{HOST}:{PORT}/{DBNAME}?sslmode=require"

engine  = create_engine(db_url, echo=False)
Session = sessionmaker(bind=engine)