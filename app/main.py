from fastapi import FastAPI
from app.api.routes.routes import router

app = FastAPI(title="FRIDAY", version="0.1.0")
app.include_router(router)

@app.get("/")
def root():
    return {"name": "FRIDAY", "version": "0.1.0", "status": "online"}

@app.get("/health")
def health():
    return {"status": "healthy"}
