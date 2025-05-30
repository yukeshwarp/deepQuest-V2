import streamlit as st
from web_agent import search_google
from dotenv import load_dotenv
from config import client

load_dotenv()

st.title("deepQuest v2")

query = st.text_input("Enter your research query:")

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

def agentic_research(query, max_replan_rounds=3, max_total_steps=20):
    # 1. Plan
    steps = plan_research(query)
    # Sidebar for steps
    sidebar_steps = st.sidebar.empty()
    # plan_container = st.empty()
    # plan_lines = [f"**Step {idx+1}:** {step}\n" for idx, step in enumerate(steps)]
    # plan_container.write("\n".join(plan_lines))
    sidebar_steps.markdown("### Research Steps\n" + "\n".join([f"{idx+1}. {step}" for idx, step in enumerate(steps)]))

    # 2. Execute steps, allow dynamic replanning if needed
    context = ""
    completed_steps = []
    i = 0
    replan_rounds = 0
    replan_limit_reached = False
    while i < len(steps):
        if len(steps) > max_total_steps:
            st.warning("Maximum total steps reached. Completing available steps to prevent infinite loop.")
            break
        step = steps[i]
        result = execute_step(step, context)
        completed_steps.append((step, result))
        context += f"\nStep: {step}\nResult: {result}\n"

        # Update plan display to show completed steps (with checkmark)
        plan_lines = []
        for idx, s in enumerate(steps):
            if idx < len(completed_steps):
                plan_lines.append(f"✅ **Step {idx+1}:** {s}\n")
            else:
                plan_lines.append(f"**Step {idx+1}:** {s}\n")
        # plan_container.write("\n".join(plan_lines))
        sidebar_steps.markdown("### Research Steps\n" + "\n".join([
            f"✅ {idx+1}. {s}\n" if idx < len(completed_steps) else f"{idx+1}. {s}"
            for idx, s in enumerate(steps)
        ]))

        # Replanning: Only check after the last original or newly added step
        if not replan_limit_reached:
            replan_prompt = (
                f"Given the completed steps and results so far:\n{context}\n\n"
                "As an autonomous agent, do you need to add any new steps to fully answer the original query? "
                "If yes, list them as a numbered list. If not, reply 'No additional steps needed.'"
            )
            replan_response = client.chat.completions.create(
                model="gpt-4.1",
                messages=[
                    {"role": "system", "content": "You are a research planning assistant."},
                    {"role": "user", "content": replan_prompt}
                ]
            )
            replan_text = replan_response.choices[0].message.content.strip().lower()
            if "no additional steps needed" in replan_text:
                i += 1
                replan_rounds = 0  # Reset replan rounds if no new steps
                continue
            # Parse new steps, avoid duplicates
            new_steps = [s[2:].strip() for s in replan_text.split("\n") if s.strip() and s[0].isdigit()]
            new_unique_steps = [new_step for new_step in new_steps if new_step not in steps]
            if new_unique_steps:
                steps.extend(new_unique_steps)
                replan_rounds += 1
                if replan_rounds > max_replan_rounds:
                    st.warning("Maximum replanning rounds reached. Will finish executing current plan and stop replanning.")
                    replan_limit_reached = True
            else:
                replan_rounds += 1
                if replan_rounds > max_replan_rounds:
                    st.warning("Maximum replanning rounds reached (no new unique steps). Will finish executing current plan and stop replanning.")
                    replan_limit_reached = True
        i += 1  # Always increment to move to the next step

    # 3. Final synthesis/report
    report_prompt = (
        f"Given the following completed research steps and their results:\n{context}\n\n"
        "As an autonomous research agent, write a detailed, well-structured research report that answers the original query. "
        "Include attributions to sources where appropriate."
    )
    report_response = client.chat.completions.create(
        model="gpt-4.1",
        messages=[
            {"role": "system", "content": "You are a research report writing assistant."},
            {"role": "user", "content": report_prompt}
        ]
    )
    report = report_response.choices[0].message.content
    return report

if st.button("Research") and query:
    with st.spinner("Running agentic research..."):
        report = agentic_research(query)
        st.subheader("Final Research Report")
        st.write(report)
