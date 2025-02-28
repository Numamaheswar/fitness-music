from dotenv import load_dotenv
import os

load_dotenv()

# Database
DATABASE_URL = os.getenv("DATABASE_URL")

# JWT
SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM = os.getenv("ALGORITHM")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES"))

# Server
HOST = os.getenv("HOST")
PORT = int(os.getenv("PORT"))
DEBUG = os.getenv("DEBUG").lower() == "true"

# Security
CORS_ORIGINS = eval(os.getenv("CORS_ORIGINS")) 