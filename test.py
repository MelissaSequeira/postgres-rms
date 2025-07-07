from dotenv import load_dotenv
import os
from pathlib import Path

# 👇 explicitly load .env from current dir
env_path = Path('.') / '.env'
load_dotenv(dotenv_path=env_path)

print("ENV:", os.getenv("DATABASE_URL"))
