from fastapi import FastAPI

app = FastAPI(title="AIde", docs_url=None, redoc_url=None)


@app.get("/health")
async def health():
    return {"status": "ok"}
