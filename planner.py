import streamlit as st
from web_agent import search_google
from dotenv import load_dotenv
from config import client

load_dotenv()

def plan_research(query):
    """Ask the LLM to generate a step-by-step research plan for the query."""
    plan_prompt = (
        "You are an expert research agent. "
        "Given the following user query, create a clear, step-by-step research plan. "
        "Each step should be actionable and focused on gathering or synthesizing information needed to answer the query. "
        "Do not add unnecessary steps. Return the plan as a numbered list.\n\n"
        f"User Query: {query}"
    )
    response = client.chat.completions.create(
        model="gpt-4.1",
        messages=[
            {"role": "system", "content": "You are a research planning assistant."},
            {"role": "user", "content": plan_prompt}
        ]
    )
    plan_text = response.choices[0].message.content
    steps = [step[2:].strip() for step in plan_text.split("\n") if step.strip() and step[0].isdigit()]
    return steps