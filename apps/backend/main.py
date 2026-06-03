from src.llms.groqllm import GroqLLM
from src.graphs.graph_builder import GraphBuilder   
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
import os
import uvicorn

app = FastAPI()


def _parse_csv_env(name: str, default: str) -> list[str]:
    raw_value = os.getenv(name, default)
    return [value.strip() for value in raw_value.split(",") if value.strip()]


cors_origins = _parse_csv_env(
    "CORS_ORIGINS",
    "http://localhost:3002",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.post("/api/generate_summary")
async def generate_summary(request: Request):
    data= await request.json()
    policy_name=data.get("policy_name")

    if not policy_name:
        return {"error": "policy_name is required"}
    
    ## Initialize the GroqLLM and get the LLM instance
    groq_llm=GroqLLM()
    llm=groq_llm.get_llm()

    ## get the graph
    graph_builder=GraphBuilder(llm)
    graph=graph_builder.setup_graph()
    state=graph.invoke({"policy_summary": {"policy_name": policy_name}})

    return {"data":state}


if __name__ == "__main__":
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8082"))
    reload_mode = os.getenv("RELOAD", "false").lower() == "true"

    uvicorn.run("main:app", host=host, port=port, reload=reload_mode)
