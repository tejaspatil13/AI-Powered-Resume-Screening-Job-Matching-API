from typing import TypedDict

from langgraph.graph import StateGraph, START, END
from langchain_openai import ChatOpenAI

from app.schemas.screening import ScreeningResult
from dotenv import load_dotenv

load_dotenv(override=True)

class ScreeningState(TypedDict):
    resume_text: str
    jd_text: str
    result: ScreeningResult | None


llm = ChatOpenAI(
    model="gpt-4o-mini",
    temperature=0
)


structured_llm = llm.with_structured_output(ScreeningResult)


def screen_candidate(state: ScreeningState):

    prompt = f"""
You are an AI resume screening system.

Evaluate the candidate resume against the provided job description.

IMPORTANT RULES:
1. Do not invent skills, experience, projects, education, or achievements.
2. Use only information supported by the resume.
3. If information is unavailable, do not assume it exists.
4. Evaluate the candidate against the actual job requirements.
5. Return a score from 0 to 100.
6. Consider technical skills, relevant experience, project experience,
   education, and other job requirements.

SCORING GUIDELINES:
- Technical Skills: 40%
- Relevant Experience: 30%
- Project Experience: 15%
- Education: 10%
- Other Requirements: 5%

RECOMMENDATION:
- 80-100: Strong Match
- 65-79: Good Match
- 50-64: Partial Match
- 0-49: Poor Match

JOB DESCRIPTION:
----------------
{state["jd_text"]}

CANDIDATE RESUME:
----------------
{state["resume_text"]}
"""

    result = structured_llm.invoke(prompt)

    return {
        "result": result
    }


def validate_result(state: ScreeningState):

    result = state["result"]

    if result is None:
        raise ValueError("LLM did not return a screening result")

    if not 0 <= result.overall_score <= 100:
        raise ValueError("Invalid screening score")

    return {
        "result": result
    }


graph_builder = StateGraph(ScreeningState)

graph_builder.add_node("screen_candidate", screen_candidate)
graph_builder.add_node("validate_result", validate_result)

graph_builder.add_edge(START, "screen_candidate")
graph_builder.add_edge("screen_candidate", "validate_result")
graph_builder.add_edge("validate_result", END)

screening_graph = graph_builder.compile()