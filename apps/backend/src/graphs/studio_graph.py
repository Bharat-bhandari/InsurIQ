from src.llms.groqllm import GroqLLM
from src.graphs.graph_builder import GraphBuilder

def get_graph():
    llm= GroqLLM().get_llm()
    return GraphBuilder(llm).setup_graph()