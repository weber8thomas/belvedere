
import uvicorn
from fastapi_consumer import app
from config import load_config

config = load_config()

if __name__ == "__main__":
    uvicorn.run(app, host=config["fastapi"]["host"], port=config["fastapi"]["port"], reload=True)
