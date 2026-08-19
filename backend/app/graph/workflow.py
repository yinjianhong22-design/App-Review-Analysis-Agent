from typing import Literal

from langgraph.graph import StateGraph, END

from app.graph.state import PipelineState
from app.graph.nodes import (
    fetch_and_clean_node,
    classify_node,
    evaluate_node,
    plan_node,
    prd_node,
    testgen_node,
    verify_node,
    present_node,
)


def _has_error(state: PipelineState) -> bool:
    return state.error is not None


def _error_router(state: PipelineState) -> Literal["next", "end"]:
    return "end" if _has_error(state) else "next"


def _route_after_verify(state: PipelineState) -> Literal["prd", "present"]:
    if _has_error(state):
        return "present"
    if state.validation_status == "NEEDS_RETRY":
        return "prd"
    return "present"


def build_workflow():
    workflow = StateGraph(PipelineState)

    workflow.add_node("fetch_and_clean", fetch_and_clean_node)
    workflow.add_node("classify", classify_node)
    workflow.add_node("evaluate", evaluate_node)
    workflow.add_node("plan", plan_node)
    workflow.add_node("prd", prd_node)
    workflow.add_node("testgen", testgen_node)
    workflow.add_node("verify", verify_node)
    workflow.add_node("present", present_node)

    workflow.set_entry_point("fetch_and_clean")

    # Error-aware routing after each major node
    for node, next_node in [
        ("fetch_and_clean", "classify"),
        ("classify", "evaluate"),
        ("evaluate", "plan"),
        ("plan", "prd"),
        ("prd", "testgen"),
        ("testgen", "verify"),
    ]:
        workflow.add_conditional_edges(
            node,
            _error_router,
            {"next": next_node, "end": "present"},
        )

    workflow.add_conditional_edges(
        "verify",
        _route_after_verify,
        {
            "prd": "prd",
            "present": "present",
        },
    )

    workflow.add_edge("present", END)

    return workflow.compile()


app_graph = build_workflow()
