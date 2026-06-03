from langgraph.graph import StateGraph, START, END
from apps.backend.src.states.evidence import InsuranceState
from src.nodes.insurance_node import InsuranceNode


class GraphBuilder:
    def __init__(self,llm):
        self.llm=llm
        self.graph=StateGraph(InsuranceState)

    def build_insurance_graph(self):
        """
        Build a graph to generate insurance policy summaries.
        """

        self.insurance_node=InsuranceNode(self.llm)

        ### nodes 
        self.graph.add_node("insurance_node",self.insurance_node.get_policy_summary)

        ### edges
        self.graph.add_edge(START,"insurance_node")
        self.graph.add_edge("insurance_node",END)

        return self.graph
    
    def setup_graph(self):
        """
        Set up the graph for execution.
        """

        self.build_insurance_graph()

        try:
            compile_graph=self.graph.compile()
            return compile_graph
        except Exception as e:
            print(f"Graph compilation failed: {e}")
            raise ValueError("Error occurred while setting up the graph: " + str(e))
        