from langgraph.graph import StateGraph, END
from langchain_core.messages import HumanMessage, SystemMessage
import yaml
from app.tools.sir_optimized_api import sir_optimized_api_tool
from app.utils.llm_client import llm
from app.prompts.system_prompts import load_system_prompt  # new import

def load_system_prompt():
    with open("app/prompts/system_prompts.yaml", "r") as f:
        data = yaml.safe_load(f)
    return data["system_prompt"]

def create_agent():
    graph = StateGraph(dict)
    
    def router(state):
        messages = state["messages"]
        system_prompt_text = load_system_prompt()
        
        # Add the system instructions + tool info
        full_messages = [SystemMessage(content=system_prompt_text)] + messages
        tool_info = f"Available tool: {sir_optimized_api_tool['description']}"
        response = llm.invoke(
            full_messages + [HumanMessage(content=f"Decide which tool to call. {tool_info}")]
        )
        return {"messages": messages + [response]}
    
    graph.add_node("router", router)
    graph.set_entry_point("router")
    graph.add_edge("router", END)
    
    return graph.compile()

bykemania_agent = create_agent()