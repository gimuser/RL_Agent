from fastapi import FastAPI

app = FastAPI(title="SOAR-RL-Agent", version="0.1.0")


@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}

print("testing")