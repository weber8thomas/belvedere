from fastapi import FastAPI, HTTPException, BackgroundTasks
import httpx
import asyncio
import uvicorn

fastapi_app = FastAPI()


async def fetch_data_from_api():
    url_api = "http://127.0.0.1:8058/api/workflows"
    max_retries = 5
    wait_time = 10

    async with httpx.AsyncClient() as client:
        for attempt in range(max_retries):
            try:
                response = await client.get(
                    url_api, headers={"Accept": "application/json"}
                )
                response_json = response.json()
                return response_json
            except httpx.ReadTimeout:  # <- Modified here
                if attempt == max_retries - 1:
                    print(
                        f"Failed to fetch progress from API after {max_retries} attempts."
                    )
                    return {"workflows": []}
                print(
                    f"Timeout error: Attempt {attempt + 1} of {max_retries}. Retrying in {wait_time} seconds."
                )
                await asyncio.sleep(wait_time)
            except Exception as e:
                print(f"An unexpected error occurred: {e}")
                return {"workflows": []}



@fastapi_app.get("/get-progress")
async def async_fetch():
    return await fetch_data_from_api()

if __name__ == "__main__":
    uvicorn.run(fastapi_app, host="localhost", port=8059)