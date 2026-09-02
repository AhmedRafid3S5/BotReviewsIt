"""FastAPI backend exposing the phone database and the agent system."""
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import database

orchestrator = None


@asynccontextmanager
async def lifespan(app):
    global orchestrator
    from agents import Orchestrator
    orchestrator = Orchestrator()
    yield


app = FastAPI(title="Samsung Phone Query and Review System", lifespan=lifespan)


class AskRequest(BaseModel):
    question: str
    history: list[dict] = []


@app.get("/phones")
def phones():
    return database.list_phones()


@app.get("/phones/{name}")
def phone_specs(name: str):
    data = database.get_specs(name)
    if not data:
        raise HTTPException(404, f"Phone '{name}' not found")
    return data


@app.post("/ask")
def ask(req: AskRequest):
    if not req.question.strip():
        raise HTTPException(400, "Question is empty")
    return orchestrator.ask(req.question, req.history)


@app.get("/review/{name}")
def review(name: str):
    return {"phone": name, "review": orchestrator.review(name)}
