import streamlit as st
from web_agent import search_google
from dotenv import load_dotenv
from config import client
import logging

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
            {"role": "user", "content": plan_prompt},
        ],
    )
    plan_text = response.choices[0].message.content
    steps = [
        step[2:].strip()
        for step in plan_text.split("\n")
        if step.strip() and step[0].isdigit()
    ]
    return steps


def replanner(context, steps, replan_rounds, max_replan_rounds, replan_limit_reached):
    """Handles replanning logic and returns updated steps, replan_rounds, and replan_limit_reached."""
    if replan_limit_reached:
        return steps, replan_rounds, replan_limit_reached

    replan_prompt = (
        f"Given the completed steps and results so far:\n{context}\n\n"
        "As an autonomous agent, do you need to add any new steps to fully answer the original query? "
        "If yes, list them as a numbered list. If not, reply 'No additional steps needed.'"
    )
    replan_response = client.chat.completions.create(
        model="gpt-4.1",
        messages=[
            {"role": "system", "content": "You are a research planning assistant."},
            {"role": "user", "content": replan_prompt},
        ],
    )
    replan_text = replan_response.choices[0].message.content.strip().lower()
    if "no additional steps needed" in replan_text:
        replan_rounds = 0  # Reset replan rounds if no new steps
        return steps, replan_rounds, replan_limit_reached

    # Parse new steps, avoid duplicates
    new_steps = [
        s[2:].strip() for s in replan_text.split("\n") if s.strip() and s[0].isdigit()
    ]
    new_unique_steps = [new_step for new_step in new_steps if new_step not in steps]
    if new_unique_steps:
        steps.extend(new_unique_steps)
        replan_rounds += 1
        if replan_rounds > max_replan_rounds:
            logging.info(
                "Maximum replanning rounds reached. Will finish executing current plan and stop replanning."
            )
            replan_limit_reached = True
    else:
        replan_rounds += 1
        if replan_rounds > max_replan_rounds:
            logging.info(
                "Maximum replanning rounds reached (no new unique steps). Will finish executing current plan and stop replanning."
            )
            replan_limit_reached = True
    return steps, replan_rounds, replan_limit_reached
