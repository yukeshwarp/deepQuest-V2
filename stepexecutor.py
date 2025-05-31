import streamlit as st
from web_agent import search_google
from dotenv import load_dotenv
from config import client

load_dotenv()

def execute_step(step, context):
    """Execute a single research step using function calling and web search."""
    exec_prompt = (
        f"You are an autonomous research agent. Execute the following research step:\n\n"
        f"Step: {step}\n\n"
        f"Context so far: {context}\n\n"
        "If you need up-to-date information, use the search_google function."
    )
    functions = [
        {
            "name": "search_google",
            "description": "Searches Google and returns relevant web results for a query.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The search query for Google."
                    }
                },
                "required": ["query"]
            }
        }
    ]
    messages = [
        {"role": "system", "content": "You are a research execution agent."},
        {"role": "user", "content": exec_prompt}
    ]
    response = client.chat.completions.create(
        model="gpt-4.1",
        messages=messages,
        functions=functions,
        function_call="auto"
    )
    msg = response.choices[0].message

    if msg.function_call and msg.function_call.name == "search_google":
        import json
        search_args = json.loads(msg.function_call.arguments)
        web_results = search_google(search_args["query"])
        messages.append({
            "role": "function",
            "name": "search_google",
            "content": web_results
        })
        response2 = client.chat.completions.create(
            model="gpt-4.1",
            messages=messages
        )
        return response2.choices[0].message.content
    else:
        return msg.content