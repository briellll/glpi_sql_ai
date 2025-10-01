import os
from dotenv import load_dotenv
from langchain_community.utilities import SQLDatabase
from langchain_openai import ChatOpenAI


load_dotenv()


API_KEY = os.getenv("OPENAI_API_KEY")
if not API_KEY:
    raise ValueError("OPENAI_API_KEY não encontrada no arquivo .env")

DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_HOST = os.getenv("DB_HOST")
DB_NAME = os.getenv("DB_NAME")


print("🔌 Conectando ao banco de dados...")
db_uri = f"mysql+mysqlconnector://{DB_USER}:{DB_PASSWORD}@{DB_HOST}/{DB_NAME}"
db = SQLDatabase.from_uri(db_uri)

print("🤖 Inicializando o modelo de linguagem...")
llm = ChatOpenAI(model="gpt-3.5-turbo", temperature=0, api_key=API_KEY) #type: ignore