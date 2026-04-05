from __future__ import annotations

import streamlit as st

from api_client import (
    DEFAULT_BACKEND_URL,
    BackendApiError,
    generate_brief,
    get_health,
    ingest_documents,
    search_knowledge,
)

st.set_page_config(
    page_title="Day 1 Brain",
    page_icon=":books:",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
    .main .block-container {
        max-width: 1100px;
        padding-top: 1.4rem;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

BACKEND_ROLE = "junior engineer"
DISPLAY_ROLE = "Software Engineer"
NAV_OPTIONS = (
    "Briefing Agent",
    "Conversational Agent",
)
QUICK_PROMPTS = (
    "How do I get DB access?",
    "How do I run tests locally?",
    "Who should I contact if I get blocked?",
)

if "chat_messages" not in st.session_state:
    st.session_state.chat_messages = []

if "role_brief" not in st.session_state:
    st.session_state.role_brief = None

if "ingest_result" not in st.session_state:
    st.session_state.ingest_result = None

if "health_payload" not in st.session_state:
    st.session_state.health_payload = None

if "active_page" not in st.session_state:
    st.session_state.active_page = "Conversational Agent"


def render_sources(source_docs: list[str]) -> None:
    if not source_docs:
        return

    st.caption("Sources")
    for source_doc in source_docs:
        st.write(f"- `{source_doc}`")


def render_brief(role_brief: dict[str, object] | None) -> None:
    if not role_brief:
        st.info("Generate the brief to see onboarding context here.")
        return

    left_column, right_column = st.columns([1.0, 1.15], gap="large")

    with left_column:
        with st.container(border=True):
            st.subheader("Must-Knows")
            for item in role_brief.get("must_knows", []):
                st.write(f"- {item}")

        with st.container(border=True):
            st.subheader("Essential Tools")
            for item in role_brief.get("tools", []):
                st.write(f"- {item}")

        with st.container(border=True):
            st.subheader("Key Contacts")
            for contact in role_brief.get("contacts", []):
                contact_name = contact.get("name", "unknown")
                contact_reason = contact.get("reason", "")
                st.write(f"**{contact_name}**")
                st.caption(contact_reason)

    with right_column:
        with st.container(border=True):
            st.subheader("30-Day Roadmap")
            roadmap = role_brief.get("roadmap", {})
            roadmap_columns = st.columns(3)

            with roadmap_columns[0]:
                st.markdown("**Week 1**")
                for item in roadmap.get("week_1", []):
                    st.write(f"- {item}")

            with roadmap_columns[1]:
                st.markdown("**Week 2**")
                for item in roadmap.get("week_2", []):
                    st.write(f"- {item}")

            with roadmap_columns[2]:
                st.markdown("**Week 3-4**")
                for item in roadmap.get("week_3_4", []):
                    st.write(f"- {item}")

        with st.container(border=True):
            st.subheader("Grounded Sources")
            render_sources(role_brief.get("sources", []))


def render_assistant_details(chat_message: dict[str, object]) -> None:
    action = chat_message.get("action")
    who_to_contact = chat_message.get("who_to_contact")
    risk_level = chat_message.get("risk_level")
    next_steps = chat_message.get("next_steps", [])
    source_docs = chat_message.get("sources", [])

    if action or who_to_contact or risk_level or next_steps or source_docs:
        with st.expander("Details"):
            if action:
                st.caption("Next action")
                st.write(action)

            if who_to_contact:
                st.caption("Who to contact")
                st.write(who_to_contact)

            if risk_level:
                st.caption("Risk")
                st.write(risk_level)

            if next_steps:
                st.caption("Next steps")
                for next_step in next_steps:
                    st.write(f"- {next_step}")

            if source_docs:
                render_sources(source_docs)


def render_briefing_page(backend_url: str) -> None:
    st.subheader("Briefing Agent")
    st.caption(f"Generate onboarding brief for a {DISPLAY_ROLE} from the uploaded documents.")

    if st.button("Generate brief", use_container_width=True):
        try:
            st.session_state.role_brief = generate_brief(
                role=BACKEND_ROLE,
                base_url=backend_url,
            )
        except BackendApiError as exc:
            st.error(str(exc))
        except Exception as exc:
            st.error(f"Failed to generate brief: {exc}")

    render_brief(st.session_state.role_brief)


def render_conversational_page(backend_url: str) -> None:
    st.subheader("Conversational Agent")
    st.caption("Chat with the onboarding assistant using the uploaded documents as context.")

    prompt_columns = st.columns(3)
    quick_prompt = ""

    with prompt_columns[0]:
        if st.button(QUICK_PROMPTS[0], use_container_width=True):
            quick_prompt = QUICK_PROMPTS[0]

    with prompt_columns[1]:
        if st.button(QUICK_PROMPTS[1], use_container_width=True):
            quick_prompt = QUICK_PROMPTS[1]

    with prompt_columns[2]:
        if st.button(QUICK_PROMPTS[2], use_container_width=True):
            quick_prompt = QUICK_PROMPTS[2]

    typed_question = st.chat_input("Ask about setup, tooling, process, access, or ownership")
    question = typed_question or quick_prompt

    if question:
        st.session_state.chat_messages.append(
            {
                "role": "user",
                "content": question,
            }
        )

        try:
            search_result = search_knowledge(
                role=BACKEND_ROLE,
                question=question,
                base_url=backend_url,
            )

            st.session_state.chat_messages.append(
                {
                    "role": "assistant",
                    "content": search_result["answer"],
                    "action": search_result.get("action"),
                    "who_to_contact": search_result.get("who_to_contact"),
                    "risk_level": search_result.get("risk_level"),
                    "next_steps": search_result.get("next_steps", []),
                    "sources": search_result.get("sources", []),
                    "freshness": search_result.get("freshness", []),
                }
            )
        except BackendApiError as exc:
            st.session_state.chat_messages.append(
                {
                    "role": "assistant",
                    "content": f"backend error: {exc}",
                    "action": None,
                    "who_to_contact": None,
                    "risk_level": None,
                    "next_steps": [],
                    "sources": [],
                    "freshness": [],
                }
            )
        except Exception as exc:
            st.session_state.chat_messages.append(
                {
                    "role": "assistant",
                    "content": f"request failed: {exc}",
                    "action": None,
                    "who_to_contact": None,
                    "risk_level": None,
                    "next_steps": [],
                    "sources": [],
                    "freshness": [],
                }
            )

    chat_panel = st.container(height=560, border=True)

    with chat_panel:
        if not st.session_state.chat_messages:
            with st.chat_message("assistant", avatar="🤖"):
                st.markdown(
                    "I'm ready to help with onboarding questions. "
                    "Try a starter prompt above or ask your own question."
                )

        for chat_message in st.session_state.chat_messages:
            with st.chat_message(
                chat_message["role"],
                avatar="🤖" if chat_message["role"] == "assistant" else "🧑",
            ):
                st.markdown(chat_message["content"])
                if chat_message["role"] == "assistant":
                    render_assistant_details(chat_message)


st.title("Day 1 Brain")
st.caption("A simple onboarding workspace")

with st.sidebar:
    st.markdown("## Day 1 Brain")

    backend_url = DEFAULT_BACKEND_URL

    try:
        st.session_state.health_payload = get_health(base_url=backend_url)
        st.success(
            f"{st.session_state.health_payload['docs_loaded']} docs • "
            f"{st.session_state.health_payload['chunks_loaded']} chunks"
        )
    except Exception:
        st.session_state.health_payload = None
        st.warning("backend offline")

    st.divider()
    st.subheader("Upload docs")

    uploaded_files = st.file_uploader(
        "PDF, Markdown, or Text",
        type=["pdf", "md", "txt"],
        accept_multiple_files=True,
    )

    if st.button("Upload and index", use_container_width=True):
        try:
            st.session_state.ingest_result = ingest_documents(
                uploaded_files=uploaded_files or [],
                base_url=backend_url,
            )
            st.session_state.role_brief = None
            st.session_state.chat_messages = []
            st.session_state.health_payload = get_health(base_url=backend_url)
            st.success(
                f"Loaded {st.session_state.ingest_result['docs']} docs and "
                f"{st.session_state.ingest_result['chunks']} chunks."
            )
        except BackendApiError as exc:
            st.error(str(exc))
        except Exception as exc:
            st.error(f"Failed to upload docs: {exc}")

    if st.session_state.ingest_result:
        st.caption(
            f"Current index: {st.session_state.ingest_result['docs']} docs, "
            f"{st.session_state.ingest_result['chunks']} chunks"
        )

    st.divider()

    active_page = st.radio(
        "View",
        options=NAV_OPTIONS,
        index=NAV_OPTIONS.index(st.session_state.active_page),
    )
    st.session_state.active_page = active_page

    if active_page == "Conversational Agent" and st.button("Clear chat", use_container_width=True):
        st.session_state.chat_messages = []

if not st.session_state.health_payload:
    st.warning("The backend is offline, so upload, briefing, and chat actions may fail.")

if active_page == "Briefing Agent":
    render_briefing_page(backend_url=backend_url)
else:
    render_conversational_page(backend_url=backend_url)
