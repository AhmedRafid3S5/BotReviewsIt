"""LangChain multi-agent system.

SpecAgent      - retrieves evidence: exact specs from SQLite + semantic RAG hits.
ReviewAgent    - writes a full product review from a phone's specs.
Orchestrator   - LLM router that classifies each query and dispatches to an agent.
"""
import json
import re
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_ollama import ChatOllama
import database
from rag import Retriever
from config import OLLAMA_HOST, OLLAMA_API_KEY, OLLAMA_MODEL

llm = ChatOllama(
    model=OLLAMA_MODEL,
    base_url=OLLAMA_HOST,
    temperature=0.2,
    client_kwargs={"headers": {"Authorization": f"Bearer {OLLAMA_API_KEY}"}},
)


def _format_specs(data, categories=None):
    lines = [f"# {data['phone']['name']}"]
    for s in data["specs"]:
        if categories and s["category"] not in categories:
            continue
        lines.append(f"{s['category']} - {s['spec_name']}: {s['spec_value']}")
    return "\n".join(lines)


class SpecAgent:
    """Fetches phone data: exact DB lookups for phones named in the query,
    plus semantic retrieval for everything else."""

    def __init__(self):
        self.retriever = Retriever()

    def detect_phones(self, text):
        names = sorted((p["name"] for p in database.list_phones()), key=len, reverse=True)
        remaining, found = text.lower(), []
        for name in names:
            short = re.sub(r"^samsung\s+(galaxy\s+)?", "", name, flags=re.I).lower()
            if short in remaining:
                found.append(name)
                remaining = remaining.replace(short, " ")
        return found[:3]

    def gather_evidence(self, question):
        parts = []
        for name in self.detect_phones(question):
            data = database.get_specs(name)
            if data:
                parts.append(_format_specs(data))
        hits = self.retriever.search(question, k=8)
        parts.extend(h["chunk"] for h in hits)
        return "\n\n---\n\n".join(parts)

    def get_full_specs(self, phone_name):
        return database.get_specs(phone_name)


ANSWER_PROMPT = ChatPromptTemplate.from_messages([
    ("system",
     "You are a helpful Samsung phone expert. Answer the user's question using ONLY "
     "the evidence below, which was retrieved from a database of GSMArena "
     "specifications. Be concise and specific; quote exact numbers. Reason from the "
     "evidence: for 'best'/'which phone' questions, compare the relevant values "
     "(e.g. battery capacity and endurance ratings for battery life) across the "
     "phones shown and pick a winner, noting the comparison covers only those "
     "phones. Only if the evidence is truly unrelated to the question should you "
     "say you don't have the data.\n\nEVIDENCE:\n{evidence}"),
    ("human", "{history}{question}"),
])

REVIEW_PROMPT = ChatPromptTemplate.from_messages([
    ("system",
     "You are a professional tech reviewer. Using ONLY the specification sheet "
     "below, write a detailed product review with these markdown sections: "
     "Overview, Design & Display, Performance, Camera, Battery & Charging, "
     "Verdict (with pros/cons list). Ground every claim in the specs; do not "
     "invent benchmark numbers or prices not present in the data."),
    ("human", "Specification sheet:\n{specs}\n\nWrite the review."),
])

ROUTER_PROMPT = ChatPromptTemplate.from_messages([
    ("system",
     "Classify a user query about Samsung phones. Reply with JSON only:\n"
     '{{"intent": "review", "phone": "<phone name>"}} if the user asks for a full '
     "product review of one specific phone,\n"
     '{{"intent": "qa"}} for any other question (specs, comparisons, recommendations).'),
    ("human", "{question}"),
])


class ReviewAgent:
    def __init__(self, spec_agent):
        self.spec_agent = spec_agent
        self.chain = REVIEW_PROMPT | llm | StrOutputParser()

    def run(self, phone_name):
        data = self.spec_agent.get_full_specs(phone_name)
        if not data:
            known = ", ".join(p["name"] for p in database.list_phones())
            return f"I don't have '{phone_name}' in the database. Known phones: {known}."
        return self.chain.invoke({"specs": _format_specs(data)})


class Orchestrator:
    def __init__(self):
        self.spec_agent = SpecAgent()
        self.review_agent = ReviewAgent(self.spec_agent)
        self.router = ROUTER_PROMPT | llm | StrOutputParser()
        self.answer = ANSWER_PROMPT | llm | StrOutputParser()

    def _route(self, question):
        try:
            raw = self.router.invoke({"question": question})
            m = re.search(r"\{.*\}", raw, re.S)
            return json.loads(m.group(0)) if m else {"intent": "qa"}
        except Exception:
            return {"intent": "qa"}

    def ask(self, question, history=None):
        route = self._route(question)
        if route.get("intent") == "review" and route.get("phone"):
            return {"agent": "review", "answer": self.review_agent.run(route["phone"])}
        hist = ""
        if history:
            turns = [f"{t['role']}: {t['content']}" for t in history[-6:]]
            hist = "Previous conversation:\n" + "\n".join(turns) + "\n\nCurrent question: "
        evidence = self.spec_agent.gather_evidence(question)
        answer = self.answer.invoke(
            {"evidence": evidence, "history": hist, "question": question})
        return {"agent": "qa", "answer": answer}

    def review(self, phone_name):
        return self.review_agent.run(phone_name)
