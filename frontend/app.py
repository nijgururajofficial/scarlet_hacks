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

# This configures the page before any visible elements are rendered.
st.set_page_config(
    page_title="Day 1 Brain",
    page_icon=":books:",
    layout="wide",
    initial_sidebar_state="expanded",
)

# This keeps styling minimal so the app mostly inherits Streamlit's built-in dark theme.
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

# This backend role stays compatible with the current backend while the UI presents it as software engineer.
BACKEND_ROLE = "junior engineer"
# This label is what the frontend shows everywhere instead of exposing role choices.
DISPLAY_ROLE = "Software Engineer"
# This keeps the app limited to the two product experiences the user asked for.
NAV_OPTIONS = (
    "Briefing Agent",
    "Conversational Agent",
)
# This stores a few starter prompts so the chatbot page feels usable immediately.
QUICK_PROMPTS = (
    "How do I get DB access?",
    "How do I run tests locally?",
    "Who should I contact if I get blocked?",
)

# This initializes chat history once so the conversation persists across reruns.
if "chat_messages" not in st.session_state:
    # This stores user and assistant turns for the conversational agent page.
    st.session_state.chat_messages = []

# This initializes the latest role brief so the briefing page can render cached results.
if "role_brief" not in st.session_state:
    # This stores the most recently generated Agent 1 brief payload.
    st.session_state.role_brief = None

# This initializes the latest ingest summary so upload results can be shown across pages.
if "ingest_result" not in st.session_state:
    # This stores document and chunk totals after ingestion.
    st.session_state.ingest_result = None

# This initializes backend health once so the status can be reused across the layout.
if "health_payload" not in st.session_state:
    # This stores the latest backend status response when reachable.
    st.session_state.health_payload = None

# This keeps the selected navigation tab stable across reruns.
if "active_page" not in st.session_state:
    # This defaults the app to the conversational page because that is the main daily-use flow.
    st.session_state.active_page = "Conversational Agent"


def render_sources(source_docs: list[str]) -> None:
    # This skips the section when there are no source docs to show.
    if not source_docs:
        # This exits early because an empty source section adds noise without value.
        return

    # This labels the source list so the user can inspect grounding details when needed.
    st.caption("Sources")
    for source_doc in source_docs:
        # This renders each source as a simple bullet line to keep the layout clean.
        st.write(f"- `{source_doc}`")


def render_brief(role_brief: dict[str, object] | None) -> None:
    # This shows a helpful empty state until the brief is generated.
    if not role_brief:
        # This prompts the user to run the briefing flow before expecting content.
        st.info("Generate the brief to see onboarding context here.")
        return

    # This lays out the brief content in two simple columns.
    left_column, right_column = st.columns([1.0, 1.15], gap="large")

    with left_column:
        # This groups must-knows into the first card.
        with st.container(border=True):
            # This labels the must-know section for the brief.
            st.subheader("Must-Knows")
            for item in role_brief.get("must_knows", []):
                # This renders each must-know as a readable bullet line.
                st.write(f"- {item}")

        # This groups tools into the second card.
        with st.container(border=True):
            # This labels the tools section for the brief.
            st.subheader("Essential Tools")
            for item in role_brief.get("tools", []):
                # This renders each tool item as a readable bullet line.
                st.write(f"- {item}")

        # This groups contacts into the third card.
        with st.container(border=True):
            # This labels the contacts section for the brief.
            st.subheader("Key Contacts")
            for contact in role_brief.get("contacts", []):
                # This reads the contact name once so the display stays concise.
                contact_name = contact.get("name", "unknown")
                # This reads the contact reason once so the display stays concise.
                contact_reason = contact.get("reason", "")
                # This renders the contact name in bold for easier scanning.
                st.write(f"**{contact_name}**")
                # This renders the reason in lighter text beneath the name.
                st.caption(contact_reason)

    with right_column:
        # This groups the roadmap into one main card to keep the page simple.
        with st.container(border=True):
            # This labels the roadmap section for the brief.
            st.subheader("30-Day Roadmap")
            roadmap = role_brief.get("roadmap", {})
            roadmap_columns = st.columns(3)

            with roadmap_columns[0]:
                # This labels the first roadmap window.
                st.markdown("**Week 1**")
                for item in roadmap.get("week_1", []):
                    # This renders each week 1 item as a readable bullet line.
                    st.write(f"- {item}")

            with roadmap_columns[1]:
                # This labels the second roadmap window.
                st.markdown("**Week 2**")
                for item in roadmap.get("week_2", []):
                    # This renders each week 2 item as a readable bullet line.
                    st.write(f"- {item}")

            with roadmap_columns[2]:
                # This labels the later roadmap window.
                st.markdown("**Week 3-4**")
                for item in roadmap.get("week_3_4", []):
                    # This renders each week 3-4 item as a readable bullet line.
                    st.write(f"- {item}")

        # This groups supporting sources into a separate simple card.
        with st.container(border=True):
            # This labels the grounded sources section for the brief.
            st.subheader("Grounded Sources")
            # This renders the supporting source list for the brief.
            render_sources(role_brief.get("sources", []))


def render_assistant_details(chat_message: dict[str, object]) -> None:
    # This reads the optional next action once so the rendering logic stays concise.
    action = chat_message.get("action")
    # This reads the optional contact once so the rendering logic stays concise.
    who_to_contact = chat_message.get("who_to_contact")
    # This reads the optional risk level once so the rendering logic stays concise.
    risk_level = chat_message.get("risk_level")
    # This reads next steps once so the rendering logic stays concise.
    next_steps = chat_message.get("next_steps", [])
    # This reads sources once so the rendering logic stays concise.
    source_docs = chat_message.get("sources", [])

    # This renders extra answer metadata inside an expander so the chat stays GPT-like and uncluttered.
    if action or who_to_contact or risk_level or next_steps or source_docs:
        with st.expander("Details"):
            if action:
                # This labels the next action field when it exists.
                st.caption("Next action")
                # This renders the action text returned by the backend.
                st.write(action)

            if who_to_contact:
                # This labels the contact field when it exists.
                st.caption("Who to contact")
                # This renders the contact text returned by the backend.
                st.write(who_to_contact)

            if risk_level:
                # This labels the risk field when it exists.
                st.caption("Risk")
                # This renders the risk value returned by the backend.
                st.write(risk_level)

            if next_steps:
                # This labels the next-step list when it exists.
                st.caption("Next steps")
                for next_step in next_steps:
                    # This renders each next step as a readable bullet line.
                    st.write(f"- {next_step}")

            if source_docs:
                # This renders the answer sources beneath the action metadata.
                render_sources(source_docs)


def render_briefing_page(backend_url: str) -> None:
    # This introduces the briefing experience in simple language.
    st.subheader("Briefing Agent")
    st.caption("Generate onboarding brief from the uploaded company documents.")

    # This gives the user an inline action to generate the brief from the main page.
    if st.button("Generate brief", use_container_width=True):
        try:
            # This calls the backend briefing route using the hardcoded backend role.
            st.session_state.role_brief = generate_brief(
                role=BACKEND_ROLE,
                base_url=backend_url,
            )
        except BackendApiError as exc:
            # This shows backend-side validation issues in a readable way.
            st.error(str(exc))
        except Exception as exc:
            # This shows connection-level failures in a readable way.
            st.error(f"Failed to generate brief: {exc}")

    # This renders the cached software engineer brief beneath the heading.
    render_brief(st.session_state.role_brief)


def render_conversational_page(backend_url: str) -> None:
    # This introduces the conversational experience in simple language.
    st.subheader("Conversational Agent")
    st.caption("Chat with the onboarding assistant using the uploaded documents as context.")

    # This offers a few starter prompts so the chat does not feel empty on first load.
    prompt_columns = st.columns(3)
    quick_prompt = ""

    with prompt_columns[0]:
        if st.button(QUICK_PROMPTS[0], use_container_width=True):
            # This seeds the first starter prompt when the button is clicked.
            quick_prompt = QUICK_PROMPTS[0]

    with prompt_columns[1]:
        if st.button(QUICK_PROMPTS[1], use_container_width=True):
            # This seeds the second starter prompt when the button is clicked.
            quick_prompt = QUICK_PROMPTS[1]

    with prompt_columns[2]:
        if st.button(QUICK_PROMPTS[2], use_container_width=True):
            # This seeds the third starter prompt when the button is clicked.
            quick_prompt = QUICK_PROMPTS[2]

    # This captures the next user question using Streamlit's built-in chat input for a familiar chatbot feel.
    typed_question = st.chat_input("Ask about setup, tooling, process, access, or ownership")
    # This prefers typed input but lets quick prompt buttons trigger the same chat flow.
    question = typed_question or quick_prompt

    if question:
        # This appends the user question first so the transcript stays chronological.
        st.session_state.chat_messages.append(
            {
                "role": "user",
                "content": question,
            }
        )

        try:
            # This calls the backend search route using the hardcoded backend role.
            search_result = search_knowledge(
                role=BACKEND_ROLE,
                question=question,
                base_url=backend_url,
            )

            # This stores the assistant response so the transcript persists across reruns.
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
            # This stores backend failures as assistant messages so the chat layout stays consistent.
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
            # This stores unexpected request failures as assistant messages so the chat layout stays consistent.
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

    # This bounds chat history so it behaves more like a dedicated chat window.
    chat_panel = st.container(height=560, border=True)

    with chat_panel:
        # This shows a small assistant greeting before the first message exists.
        if not st.session_state.chat_messages:
            with st.chat_message("assistant", avatar="🤖"):
                # This introduces the chat in a simple GPT-like style.
                st.markdown(
                    "I'm ready to help with onboarding questions"
                    "Try a starter prompt above or ask your own question."
                )

        # This replays the full transcript inside the bounded chat panel.
        for chat_message in st.session_state.chat_messages:
            with st.chat_message(
                chat_message["role"],
                avatar="🤖" if chat_message["role"] == "assistant" else "🧑",
            ):
                # This renders the message body as markdown like a normal chatbot.
                st.markdown(chat_message["content"])

                if chat_message["role"] == "assistant":
                    # This renders optional metadata below assistant answers without cluttering the main response.
                    render_assistant_details(chat_message)


# This renders the top-level title before the page-specific content below.
st.title("Day 1 Brain")
st.caption("A simple onboarding workspace")

# This keeps app controls in the sidebar so the main content stays focused.
with st.sidebar:
    # This labels the app in the sidebar.
    st.markdown("## Day 1 Brain")

    backend_url = DEFAULT_BACKEND_URL

    try:
        # This refreshes backend health so the sidebar status stays current.
        st.session_state.health_payload = get_health(base_url=backend_url)
        st.success(
            f"{st.session_state.health_payload['docs_loaded']} docs • "
            f"{st.session_state.health_payload['chunks_loaded']} chunks"
        )
    except Exception:
        # This clears stale backend state when the API cannot be reached.
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
            # This sends the uploaded files to the backend so the in-memory index is rebuilt.
            st.session_state.ingest_result = ingest_documents(
                uploaded_files=uploaded_files or [],
                base_url=backend_url,
            )
            # This clears the cached brief because the document set changed.
            st.session_state.role_brief = None
            # This clears the chat transcript because old answers may no longer match the new docs.
            st.session_state.chat_messages = []
            # This refreshes backend health after a successful ingest.
            st.session_state.health_payload = get_health(base_url=backend_url)
            st.success(
                f"Loaded {st.session_state.ingest_result['docs']} docs and "
                f"{st.session_state.ingest_result['chunks']} chunks."
            )
        except BackendApiError as exc:
            # This shows backend validation failures in a readable way.
            st.error(str(exc))
        except Exception as exc:
            # This shows connection-level failures in a readable way.
            st.error(f"Failed to upload docs: {exc}")

    if st.session_state.ingest_result:
        # This surfaces the latest ingest totals in the sidebar.
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

    if active_page == "Conversational Agent":
        if st.button("Clear chat", use_container_width=True):
            # This resets the chat transcript so the conversational page can start clean.
            st.session_state.chat_messages = []

# This shows a small warning when the backend is offline so the user understands why actions may fail.
if not st.session_state.health_payload:
    st.warning("The backend is offline, so upload, briefing, and chat actions may fail.")

# This routes between the two simplified product experiences.
if active_page == "Briefing Agent":
    render_briefing_page(backend_url=backend_url)
else:
    render_conversational_page(backend_url=backend_url)
