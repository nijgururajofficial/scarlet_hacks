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

# This configures the Streamlit page before any UI elements are rendered.
st.set_page_config(
    page_title="Day 1 Brain",
    page_icon=":books:",
    layout="wide",
)

# This injects light styling so the second agent feels more like a dedicated chat component.
st.markdown(
    """
    <style>
    .main .block-container {
        max-width: 1320px;
        padding-top: 2rem;
    }
    .chat-shell {
        border: 1px solid rgba(120, 120, 120, 0.22);
        border-radius: 18px;
        padding: 1rem 1.2rem;
        background: linear-gradient(180deg, rgba(34, 41, 57, 0.92), rgba(20, 24, 33, 0.96));
        margin-bottom: 1rem;
    }
    .chat-shell h3 {
        margin: 0 0 0.35rem 0;
        color: #f8fafc;
        font-size: 1.2rem;
    }
    .chat-shell p {
        margin: 0;
        color: #cbd5e1;
        font-size: 0.95rem;
    }
    .status-pill {
        display: inline-block;
        border: 1px solid rgba(148, 163, 184, 0.35);
        border-radius: 999px;
        padding: 0.22rem 0.65rem;
        margin-right: 0.45rem;
        margin-top: 0.55rem;
        color: #e2e8f0;
        font-size: 0.82rem;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# This initializes the chat history once so messages persist across reruns.
if "chat_messages" not in st.session_state:
    # This stores prior user and assistant messages for the chat transcript.
    st.session_state.chat_messages = []

# This initializes the latest role brief so the cards can persist after generation.
if "role_brief" not in st.session_state:
    # This stores the most recently generated brief payload.
    st.session_state.role_brief = None

# This initializes the last ingest result so the UI can show ingestion counts after reruns.
if "ingest_result" not in st.session_state:
    # This stores the latest ingest summary from the backend.
    st.session_state.ingest_result = None

# This initializes backend health so the page can render a status banner on first load.
if "health_payload" not in st.session_state:
    # This stores the most recent backend health response when available.
    st.session_state.health_payload = None


def render_answer_details(chat_message: dict[str, object]) -> None:
    # This skips the detail card when the message has no structured assistant metadata.
    if not chat_message.get("sources"):
        # This exits early because plain error messages do not need decision details.
        return

    # This renders the answer metadata in a bordered card so assistant responses feel more productized.
    with st.container(border=True):
        # This lays out the top summary fields in compact columns so they scan like chatbot metadata.
        summary_columns = st.columns(3)

        with summary_columns[0]:
            # This labels the recommended action field inside the response card.
            st.caption("recommended action")
            # This shows the clearest next action from Agent 2.
            st.write(chat_message.get("action", ""))

        with summary_columns[1]:
            # This labels the contact field inside the response card.
            st.caption("who to contact")
            # This shows the team or person the user should contact when needed.
            st.write(chat_message.get("who_to_contact", ""))

        with summary_columns[2]:
            # This labels the risk and confidence field group inside the response card.
            st.caption("risk and confidence")
            # This shows a compact line with risk level and confidence so trust is easy to judge.
            st.write(
                f"{chat_message.get('risk_level', 'medium')} risk • "
                f"{chat_message.get('confidence', 0.0):.2f} confidence"
            )

        # This labels the next step section so the user can act immediately after reading the answer.
        st.caption("next steps")
        for next_step in chat_message.get("next_steps", []):
            # This renders each suggested next step as a readable bullet line.
            st.write(f"- {next_step}")

    # This keeps sources tucked away so the main chat bubble stays clean but citations remain accessible.
    with st.expander("view sources"):
        # This labels the sources subsection inside the expandable citation area.
        st.caption("sources")
        for source_name in chat_message.get("sources", []):
            # This renders each cited source on its own line.
            st.write(f"- {source_name}")

        # This labels the freshness subsection inside the expandable citation area.
        st.caption("freshness")
        for freshness_item in chat_message.get("freshness", []):
            # This reads the source name once so the line stays readable.
            source_name = freshness_item.get("source", "unknown")
            # This reads the freshness label once so the line stays readable.
            freshness_label = freshness_item.get("freshness", "unknown")
            # This renders the freshness summary for each cited source.
            st.write(f"- {source_name}: {freshness_label}")


def render_role_brief(role_brief: dict[str, object] | None) -> None:
    # This handles the empty state so the side panel stays informative before any brief is generated.
    if not role_brief:
        # This nudges the user to create a brief without taking over the main chat surface.
        st.info("generate a role brief to pin onboarding context next to the chat")
        return

    # This labels the brief with the active role so the supporting panel stays grounded.
    st.caption(f"brief for {role_brief['role']}")

    # This groups must-knows inside a compact card so the panel remains readable.
    with st.container(border=True):
        # This labels the must-know section.
        st.markdown("**must knows**")
        for item in role_brief.get("must_knows", []):
            # This renders each must-know as a readable bullet line.
            st.write(f"- {item}")

    # This groups tools inside a second compact card so setup items stay easy to scan.
    with st.container(border=True):
        # This labels the tools section.
        st.markdown("**tools checklist**")
        for item in role_brief.get("tools", []):
            # This renders each setup item as a readable bullet line.
            st.write(f"- {item}")

    # This groups contacts inside a third compact card so the user can find owners quickly.
    with st.container(border=True):
        # This labels the contacts section.
        st.markdown("**key contacts**")
        for contact in role_brief.get("contacts", []):
            # This extracts the person name once so the display line stays readable.
            contact_name = contact.get("name", "unknown")
            # This extracts the reason once so the display line stays readable.
            contact_reason = contact.get("reason", "")
            # This extracts the source once so the display line stays readable.
            contact_source = contact.get("source", "")
            # This renders the contact line in a compact readable format.
            st.write(f"- **{contact_name}** - {contact_reason} ({contact_source})")

    # This groups the roadmap inside a fourth card so the onboarding timeline stays nearby.
    with st.container(border=True):
        # This labels the roadmap section.
        st.markdown("**30-day roadmap**")
        # This reads the roadmap once so week sections can be rendered from the same payload.
        roadmap = role_brief.get("roadmap", {})
        for roadmap_label, roadmap_key in [
            ("week 1", "week_1"),
            ("week 2", "week_2"),
            ("week 3-4", "week_3_4"),
        ]:
            # This prints the week header before its associated actions.
            st.caption(roadmap_label)
            for item in roadmap.get(roadmap_key, []):
                # This renders each roadmap item as a readable bullet line.
                st.write(f"- {item}")

    # This groups sources inside a final card so provenance stays visible without crowding the chat.
    with st.container(border=True):
        # This labels the source section.
        st.markdown("**sources**")
        for source_name in role_brief.get("sources", []):
            # This renders each source name on its own line for quick scanning.
            st.write(f"- {source_name}")


# This renders the top-level title and framing copy for the product demo.
st.title("Day 1 Brain")
# This explains the product value in one line before the user starts interacting with it.
st.caption("Upload company docs, choose a role, and chat with a role-aware onboarding assistant.")

# This keeps the backend URL configurable without hardcoding it in multiple places.
with st.sidebar:
    # This labels the settings area so backend connection state is easy to find.
    st.header("Backend")
    # This lets the user override the API address when running the backend elsewhere.
    backend_url = st.text_input(
        "Backend URL",
        value=DEFAULT_BACKEND_URL,
        help="Local FastAPI backend address.",
    ).rstrip("/")

    try:
        # This pings the backend so the UI can show live status before any actions are taken.
        st.session_state.health_payload = get_health(base_url=backend_url)
        # This shows a positive status when the backend is reachable.
        st.success(
            f"backend online • {st.session_state.health_payload['docs_loaded']} docs • "
            f"{st.session_state.health_payload['chunks_loaded']} chunks"
        )
    except Exception:
        # This clears stale health state when the backend cannot be reached.
        st.session_state.health_payload = None
        # This warns the user that the frontend cannot talk to the API yet.
        st.warning("backend offline • start FastAPI on port 8000")

    # This draws a divider so connection settings are visually separated from role and upload controls.
    st.divider()

    # This defines the supported roles so the frontend and backend stay aligned.
    role_options = [
        "junior engineer",
        "product manager",
        "marketing",
        "hr",
    ]

    # This labels the role controls so it is obvious what persona shapes the chat.
    st.header("Role")
    # This lets the user choose the role that should shape both the brief and chat answers.
    selected_role = st.selectbox("Choose a role", options=role_options)

    if st.button("Generate role brief", use_container_width=True):
        try:
            # This requests a fresh Agent 1 brief for the currently selected role.
            st.session_state.role_brief = generate_brief(
                role=selected_role,
                base_url=backend_url,
            )
        except BackendApiError as exc:
            # This shows backend-side validation or missing-doc errors to the user.
            st.error(str(exc))
        except Exception as exc:
            # This catches connection errors so the page remains usable.
            st.error(f"failed to generate brief: {exc}")

    if st.button("Clear chat", use_container_width=True):
        # This resets the conversation transcript so the user can start a clean chat.
        st.session_state.chat_messages = []

    # This draws a divider so role controls are separated from document ingestion controls.
    st.divider()
    # This labels the upload section where the knowledge base is managed.
    st.header("Documents")

    # This lets the user choose one or more supported documents to ingest.
    uploaded_files = st.file_uploader(
        "Upload company docs",
        type=["pdf", "md", "txt"],
        accept_multiple_files=True,
    )

    if st.button("Ingest documents", use_container_width=True):
        try:
            # This sends the selected documents to the backend so the FAISS index is rebuilt.
            st.session_state.ingest_result = ingest_documents(
                uploaded_files=uploaded_files or [],
                base_url=backend_url,
            )
            # This clears stale brief data because the knowledge base has changed.
            st.session_state.role_brief = None
            # This clears chat history because prior answers may no longer match the new docs.
            st.session_state.chat_messages = []
            # This refreshes health after ingest so the sidebar status stays accurate.
            st.session_state.health_payload = get_health(base_url=backend_url)
            # This confirms the new knowledge base size after a successful upload.
            st.success(
                f"loaded {st.session_state.ingest_result['docs']} docs and "
                f"{st.session_state.ingest_result['chunks']} chunks"
            )
        except BackendApiError as exc:
            # This shows backend validation or processing failures directly to the user.
            st.error(str(exc))
        except Exception as exc:
            # This catches connection-level issues so the app does not crash on request failures.
            st.error(f"failed to ingest documents: {exc}")

    # This repeats the latest ingest summary so the user can still see it after reruns.
    if st.session_state.ingest_result:
        # This surfaces the current ingest totals in a compact sidebar summary.
        st.caption(
            f"{st.session_state.ingest_result['docs']} docs loaded • "
            f"{st.session_state.ingest_result['chunks']} chunks indexed"
        )

# This lays out the chat shell and the supporting context panel side by side.
chat_column, context_column = st.columns([1.7, 1.0], gap="large")

with chat_column:
    # This renders a styled shell header so the second agent feels like a dedicated chatbot component.
    st.markdown(
        f"""
        <div class="chat-shell">
            <h3>Agent 2 · Knowledge Search</h3>
            <p>Ask questions about onboarding, access, tools, process, or ownership and get a role-aware answer.</p>
            <span class="status-pill">role: {selected_role}</span>
            <span class="status-pill">chat-first mode</span>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # This offers quick prompts so the chatbot component feels interactive even before the first message.
    prompt_columns = st.columns(3)
    # This stores the selected starter prompt when a quick action button is clicked.
    quick_prompt = ""

    with prompt_columns[0]:
        if st.button("How do I get DB access?", use_container_width=True):
            # This seeds a realistic access question so the chat can start instantly.
            quick_prompt = "How do I get DB access?"

    with prompt_columns[1]:
        if st.button("Who should I ask for help?", use_container_width=True):
            # This seeds a common onboarding ownership question so the chat can start instantly.
            quick_prompt = "Who should I ask for help if I get blocked?"

    with prompt_columns[2]:
        if st.button("What should I do this week?", use_container_width=True):
            # This seeds a roadmap question so the chat can start instantly.
            quick_prompt = "What should I focus on during my first week?"

    # This captures a free-form chat input from the user at the bottom of the page.
    typed_question = st.chat_input("Ask agent 2 about onboarding, access, tools, or team processes")
    # This prefers the typed message but allows quick prompt buttons to trigger the same chat flow.
    question = typed_question or quick_prompt

    if question:
        # This appends the user message immediately so it appears in the transcript right away.
        st.session_state.chat_messages.append(
            {
                "role": "user",
                "content": question,
            }
        )

        try:
            # This sends the user question to Agent 2 for a grounded role-aware answer.
            search_result = search_knowledge(
                role=selected_role,
                question=question,
                base_url=backend_url,
            )

            # This stores the assistant message so it persists across reruns.
            assistant_message = {
                "role": "assistant",
                "content": search_result["answer"],
                "action": search_result.get("action", ""),
                "who_to_contact": search_result.get("who_to_contact", ""),
                "risk_level": search_result.get("risk_level", "medium"),
                "confidence": float(search_result.get("confidence", 0.0)),
                "next_steps": search_result.get("next_steps", []),
                "sources": search_result.get("sources", []),
                "freshness": search_result.get("freshness", []),
            }
            st.session_state.chat_messages.append(assistant_message)
        except BackendApiError as exc:
            # This stores the backend error in the chat so the failure remains visible in context.
            assistant_message = {
                "role": "assistant",
                "content": f"backend error: {exc}",
                "action": "",
                "who_to_contact": "",
                "risk_level": "medium",
                "confidence": 0.0,
                "next_steps": [],
                "sources": [],
                "freshness": [],
            }
            st.session_state.chat_messages.append(assistant_message)
        except Exception as exc:
            # This stores unexpected request failures so the conversation transcript remains coherent.
            assistant_message = {
                "role": "assistant",
                "content": f"request failed: {exc}",
                "action": "",
                "who_to_contact": "",
                "risk_level": "medium",
                "confidence": 0.0,
                "next_steps": [],
                "sources": [],
                "freshness": [],
            }
            st.session_state.chat_messages.append(assistant_message)

    # This creates a fixed-height panel so previous chats stay scrollable instead of stretching the page.
    chat_history_panel = st.container(height=560, border=True)

    with chat_history_panel:
        # This shows an assistant welcome card before the user has started the conversation.
        if not st.session_state.chat_messages:
            with st.chat_message("assistant", avatar="🤖"):
                # This introduces the chat experience so the user knows what kinds of questions to ask.
                st.markdown(
                    f"I’m ready to answer onboarding questions for a **{selected_role}**. "
                    "Try one of the quick prompts above or ask your own question below."
                )

        # This replays prior chat messages inside the scrollable panel so history stays contained.
        for chat_message in st.session_state.chat_messages:
            with st.chat_message(
                chat_message["role"],
                avatar="🤖" if chat_message["role"] == "assistant" else "🧑",
            ):
                # This renders the stored message body for each chat turn.
                st.markdown(chat_message["content"])

                # This renders assistant metadata in a structured response card when available.
                if chat_message["role"] == "assistant":
                    render_answer_details(chat_message)

with context_column:
    # This labels the supporting context area so the brief feels secondary to the main chat surface.
    st.subheader("Chat Context")

    # This shows lightweight session info so the user can see the active chat setup at a glance.
    with st.container(border=True):
        # This labels the active role line in the context panel.
        st.caption("active role")
        # This shows the selected role driving the chat responses.
        st.write(selected_role)
        # This labels the message count line in the context panel.
        st.caption("messages")
        # This shows the current transcript length so the user knows how much context exists.
        st.write(len(st.session_state.chat_messages))

    # This tucks the role brief into an expander so it supports the chat without competing with it.
    with st.expander("view role brief", expanded=bool(st.session_state.role_brief)):
        # This renders the cached role brief in a compact supporting panel.
        render_role_brief(st.session_state.role_brief)
