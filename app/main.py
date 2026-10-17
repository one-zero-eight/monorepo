from fastapi import FastAPI

app = FastAPI(title="monorepo API")


@app.get("/")
def read_root():
    return {"message": "Hello from FastAPI template!"}
