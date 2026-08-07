from pymongo import MongoClient
from app.config.settings import settings

client = MongoClient(settings.mongo_uri)
db = client[settings.database_name]

# Collections
alerts_collection = db["alerts"]
decisions_collection = db["decisions"]
rewards_collection = db["rewards"]
evaluations_collection = db["evaluations"]
pipeline_collection = db["pipeline_logs"]