from motor.motor_asyncio import AsyncIOMotorClient

#MONGO_URL = "mongodb+srv://priyagovindarajulu_db_user:YOUR_PASSWORD@cluster0.prvspza.mongodb.net/?appName=Cluster0"
MONGO_URL = "mongodb+srv://priyagovindarajulu_db_user:YOUR_PASSWORD@cluster0.prvspza.mongodb.net/?appName=Cluster0"
DB_NAME = "ai_mock_interviewer"

client = AsyncIOMotorClient(MONGO_URL, serverSelectionTimeoutMS=5000)
db = client[DB_NAME]

async def ping():
    return await db.command("ping")
