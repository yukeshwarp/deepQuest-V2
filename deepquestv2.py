import streamlit as st
from web_agent import search_google
from dotenv import load_dotenv
from config import client
from planner import plan_research
from stepexecutor import execute_step
# import pypandoc
from io import BytesIO
from docx import Document
# import tempfile

load_dotenv()
# pypandoc.download_pandoc()

st.title("deepQuest v2")

query = st.text_input("Enter your research query:")

def agentic_research(query, max_replan_rounds=3, max_total_steps=20):
    steps = plan_research(query)
    sidebar_steps = st.sidebar.empty()
    sidebar_steps.markdown("### Research Steps\n" + "\n".join([f"{idx+1}. {step}" for idx, step in enumerate(steps)]))

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

def generate_word_doc(report_text, filename="deepquest_report.docx"):
    doc = Document()
    doc.add_heading("DeepQuest Research Report", 0)
    for para in report_text.split('\n'):
        doc.add_paragraph(para)
    buffer = BytesIO()
    doc.save(buffer)
    buffer.seek(0)
    return buffer

# def generate_word_doc_from_markdown(markdown_text):
#     with tempfile.NamedTemporaryFile(suffix=".docx") as tmp:
#         pypandoc.convert_text(markdown_text, 'docx', format='md', outputfile=tmp.name)
#         tmp.seek(0)
#         return BytesIO(tmp.read())

if st.button("Research") and query:
    with st.spinner("Running agentic research..."):
        report = agentic_research(query)
        st.subheader("Final Research Report")
        st.write(report)
        # Download button for Word document
        word_buffer = generate_word_doc(report)
        st.download_button(
            label="Download Report as Word Document",
            data=word_buffer,
            file_name="deepquest_report.docx",
            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        )