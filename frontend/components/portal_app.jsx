"use client";

import Link from "next/link";
import { useEffect, useMemo, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";

// This keeps the backend role fixed to the supported value required by the FastAPI contract.
const backend_role = "junior engineer";
// This normalizes backend errors so the UI can show readable messages consistently.
async function read_error_message(response) {
  try {
    // This attempts to parse the backend's structured error payload first.
    const payload = await response.json();
    // This prefers the backend detail field when one is present.
    return payload.detail || "Request failed.";
  } catch {
    // This falls back to a generic message when the response body is not JSON.
    return "Request failed.";
  }
}

// This keeps all backend calls pointed at the local FastAPI server by default.
function get_backend_url() {
  return process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8000";
}

// This reusable badge list keeps sources rendered consistently across both pages.
function render_sources_list(source_docs) {
  if (!source_docs?.length) {
    return null;
  }

  return (
    <div className="source_badges">
      {source_docs.map((source_doc) => (
        <span className="source_badge" key={source_doc}>
          {source_doc}
        </span>
      ))}
    </div>
  );
}

// This helper keeps roadmap cards consistent even when the backend returns fewer items.
function build_roadmap_sections(roadmap) {
  return [
    {
      label: "Week 1",
      items: roadmap?.week_1 || [],
    },
    {
      label: "Week 2",
      items: roadmap?.week_2 || [],
    },
    {
      label: "Week 3-4",
      items: roadmap?.week_3_4 || [],
    },
  ];
}

export default function PortalApp({ active_view }) {
  // This keeps the hidden file picker available from both sidebar variants.
  const file_input_ref = useRef(null);
  // This tracks any locally selected files before they are uploaded to the backend.
  const [selected_files, set_selected_files] = useState([]);
  // This stores backend health so the sidebar can show document and chunk counts.
  const [health_payload, set_health_payload] = useState(null);
  // This stores the live brief response when the backend can generate one.
  const [brief_payload, set_brief_payload] = useState(null);
  // This stores real user and assistant messages for the analysis screen.
  const [chat_messages, set_chat_messages] = useState([]);
  // This tracks the current question typed into the chat input.
  const [question_text, set_question_text] = useState("");
  // This controls the initial loading state while the app checks backend health.
  const [is_bootstrapping, set_is_bootstrapping] = useState(true);
  // This disables upload actions while the files are being sent to the backend.
  const [is_uploading, set_is_uploading] = useState(false);
  // This disables the refresh brief action while the brief request is in flight.
  const [is_loading_brief, set_is_loading_brief] = useState(false);
  // This disables chat submission while the assistant answer is loading.
  const [is_answering, set_is_answering] = useState(false);
  // This surfaces upload and health messages close to the sidebar controls.
  const [sidebar_notice, set_sidebar_notice] = useState("");
  // This surfaces page-specific failures without breaking the rest of the layout.
  const [page_notice, set_page_notice] = useState("");
  // This prevents duplicate auto-brief requests during development re-renders.
  const [has_requested_initial_brief, set_has_requested_initial_brief] = useState(false);

  // This memo keeps the page-specific placeholder text stable across renders.
  const search_placeholder = useMemo(() => {
    return active_view === "brief" ? "Search knowledge..." : "Search insights...";
  }, [active_view]);
  // This memo keeps the screen title aligned with the active route.
  const is_brief_view = active_view === "brief";
  // This memo keeps the brief source list stable even before the first brief is generated.
  const brief_sources = brief_payload?.sources || [];
  // This memo keeps the roadmap sections easy to render as cards.
  const roadmap_sections = build_roadmap_sections(brief_payload?.roadmap);
  // This memo keeps must-know rendering simple when the backend has not returned a brief yet.
  const must_know_items = brief_payload?.must_knows || [];
  // This memo keeps tool rendering simple when the backend has not returned a brief yet.
  const tool_items = brief_payload?.tools || [];
  // This memo keeps contact rendering simple when the backend has not returned a brief yet.
  const contact_items = brief_payload?.contacts || [];
  // This memo keeps the status summary readable without repeating string assembly in JSX.
  const upload_summary = health_payload
    ? `${health_payload.docs_loaded} documents ingested - ${health_payload.chunks_loaded} chunks indexed`
    : "Connect the backend to load live data.";

  useEffect(() => {
    let is_active = true;

    async function bootstrap_app() {
      try {
        // This loads the backend health first so the UI knows whether live data is available.
        const next_health_payload = await fetch_health_payload();

        if (!is_active) {
          return;
        }

        // This auto-loads the brief on the brief page so the screen matches the target mockup better.
        if (is_brief_view && next_health_payload?.has_knowledge_base) {
          // This requests the live onboarding brief when the backend is ready.
          await fetch_brief_payload(true);
        }
      } catch (error) {
        if (is_active) {
          // This keeps failures visible while still allowing the rest of the UI to render.
          set_sidebar_notice(error.message);
        }
      } finally {
        if (is_active) {
          // This removes the initial loading state once the first health check is finished.
          set_is_bootstrapping(false);
        }
      }
    }

    // This starts the initial health and brief bootstrap flow after the component mounts.
    bootstrap_app();

    return () => {
      // This avoids state updates if the user leaves the page before async work finishes.
      is_active = false;
    };
  }, [is_brief_view]);

  async function fetch_health_payload() {
    // This calls the health route so the UI can show backend readiness and document counts.
    const response = await fetch(`${get_backend_url()}/health`);

    if (!response.ok) {
      // This converts backend failures into a readable UI message.
      throw new Error(await read_error_message(response));
    }

    // This parses the health payload so the sidebar can show current backend status.
    const next_health_payload = await response.json();
    // This stores the latest backend status for sidebar badges and refresh logic.
    set_health_payload(next_health_payload);
    return next_health_payload;
  }

  async function fetch_brief_payload(silence_error = false) {
    if (has_requested_initial_brief && silence_error) {
      return;
    }

    // This marks the brief request as in-flight so duplicate clicks are avoided.
    set_is_loading_brief(true);

    try {
      // This posts the backend role so the brief endpoint can generate the onboarding summary.
      const response = await fetch(`${get_backend_url()}/brief`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          role: backend_role,
        }),
      });

      if (!response.ok) {
        // This turns structured backend errors into a standard thrown error.
        throw new Error(await read_error_message(response));
      }

      // This parses the generated brief so the cards can be replaced with live content.
      const next_brief_payload = await response.json();
      // This stores the live brief for the rest of the page to render.
      set_brief_payload(next_brief_payload);
      // This records the auto-brief attempt so Strict Mode does not repeat it.
      set_has_requested_initial_brief(true);
      // This clears any stale page error after a successful brief request.
      set_page_notice("");
    } catch (error) {
      // This still records the auto-brief attempt so development re-renders stay quiet.
      set_has_requested_initial_brief(true);

      if (!silence_error) {
        // This exposes manual brief refresh failures without crashing the rest of the page.
        set_page_notice(error.message);
      }
    } finally {
      // This re-enables the brief action once the request has completed.
      set_is_loading_brief(false);
    }
  }

  function open_file_picker() {
    // This opens the hidden file input so the styled button can trigger file selection.
    file_input_ref.current?.click();
  }

  function handle_file_selection(event) {
    // This converts the FileList into an array so it can be rendered and uploaded easily.
    const next_selected_files = Array.from(event.target.files || []);
    // This stores the selected files for the upload controls and request payload.
    set_selected_files(next_selected_files);
  }

  async function upload_selected_files() {
    if (!selected_files.length || is_uploading) {
      return;
    }

    // This marks the upload flow as busy so the button and picker do not double-submit.
    set_is_uploading(true);
    // This clears older sidebar feedback before the new upload starts.
    set_sidebar_notice("");

    try {
      // This builds multipart form data because the ingest route expects uploaded files.
      const form_data = new FormData();

      selected_files.forEach((selected_file) => {
        // This appends each file under the backend's expected `files` field name.
        form_data.append("files", selected_file);
      });

      // This sends the selected files to the backend so the knowledge base can be rebuilt.
      const response = await fetch(`${get_backend_url()}/ingest`, {
        method: "POST",
        body: form_data,
      });

      if (!response.ok) {
        // This turns ingest failures into a readable message near the upload controls.
        throw new Error(await read_error_message(response));
      }

      // This reads the ingest summary so the sidebar can confirm the new totals immediately.
      const ingest_result = await response.json();
      // This refreshes backend health so the live document and chunk counts stay accurate.
      await fetch_health_payload();
      // This clears the previous brief so the new documents can generate a fresh one.
      set_brief_payload(null);
      // This clears the old chat because those answers may not match the new documents anymore.
      set_chat_messages([]);
      // This confirms the updated totals using the backend's ingest response.
      set_sidebar_notice(
        `Loaded ${ingest_result.docs} documents and ${ingest_result.chunks} chunks.`,
      );

      if (is_brief_view) {
        // This refreshes the live brief so the new document set is reflected on screen.
        await fetch_brief_payload();
      }
    } catch (error) {
      // This shows upload failures inline without breaking the rest of the interface.
      set_sidebar_notice(error.message);
    } finally {
      // This re-enables the upload controls after the request finishes.
      set_is_uploading(false);
    }
  }

  async function submit_question(question_override) {
    // This prefers quick prompts when provided, otherwise it uses the typed input.
    const next_question = (question_override || question_text).trim();

    if (!next_question || is_answering) {
      return;
    }

    // This adds the user's message immediately so the conversation feels responsive.
    set_chat_messages((current_messages) => [
      ...current_messages,
      {
        role: "user",
        content: next_question,
      },
    ]);
    // This clears the input after the question has been submitted.
    set_question_text("");
    // This marks the answer request as busy so duplicate sends are prevented.
    set_is_answering(true);
    // This clears the prior page-level error before a new chat request starts.
    set_page_notice("");

    try {
      // This posts the fixed role and question to the backend so the answer stays compatible.
      const response = await fetch(`${get_backend_url()}/search`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          role: backend_role,
          question: next_question,
        }),
      });

      if (!response.ok) {
        // This converts backend chat failures into a readable assistant-style message.
        throw new Error(await read_error_message(response));
      }

      // This parses the assistant payload so the analysis page can render answer details and sources.
      const answer_payload = await response.json();
      // This appends the assistant response after the user message for a normal chat flow.
      set_chat_messages((current_messages) => [
        ...current_messages,
        {
          role: "assistant",
          content: answer_payload.answer,
          action: answer_payload.action,
          who_to_contact: answer_payload.who_to_contact,
          risk_level: answer_payload.risk_level,
          next_steps: answer_payload.next_steps || [],
          sources: answer_payload.sources || [],
          freshness: answer_payload.freshness || [],
        },
      ]);
    } catch (error) {
      // This appends failures as assistant output so the conversation layout remains stable.
      set_chat_messages((current_messages) => [
        ...current_messages,
        {
          role: "assistant",
          content: error.message,
          action: null,
          who_to_contact: null,
          risk_level: "medium",
          next_steps: [],
          sources: [],
          freshness: [],
        },
      ]);
    } finally {
      // This re-enables question submission when the backend finishes responding.
      set_is_answering(false);
    }
  }

  function render_sidebar_upload_panel() {
    if (!is_brief_view) {
      return (
        <button
          className="secondary_upload_button"
          disabled={is_uploading}
          onClick={open_file_picker}
          type="button"
        >
          {is_uploading ? "Uploading..." : "Upload Files"}
        </button>
      );
    }

    return (
      <section className="upload_card">
        <p className="upload_card_title">Upload Files (.pdf, .md, .txt)</p>

        <button className="dropzone" onClick={open_file_picker} type="button">
          <span className="dropzone_icon">+</span>
          <span>Drag or click to add files</span>
        </button>

        <button
          className="primary_upload_button"
          disabled={!selected_files.length || is_uploading}
          onClick={upload_selected_files}
          type="button"
        >
          {is_uploading ? "Uploading..." : "Upload Files"}
        </button>

        <p className="upload_meta">
          {selected_files.length
            ? `${selected_files.length} file${selected_files.length > 1 ? "s" : ""} selected`
            : upload_summary}
        </p>
      </section>
    );
  }

  function render_sidebar_notice() {
    if (!sidebar_notice) {
      return null;
    }

    return <p className="sidebar_notice">{sidebar_notice}</p>;
  }

  function render_brief_view() {
    return (
      <main className="page_body">
        <section className="hero_copy">
          <div>
            <h1 className="page_title">Welcome.</h1>
            <p className="page_subtitle">
              Here&apos;s what you need to know to get started.
            </p>
          </div>

          <button
            className="outline_button"
            disabled={is_loading_brief}
            onClick={() => {
              // This manually refreshes the live brief when the user wants current backend content.
              fetch_brief_payload();
            }}
            type="button"
          >
            {is_loading_brief ? "Loading brief..." : "Refresh Brief"}
          </button>
        </section>

        {page_notice ? <div className="page_notice">{page_notice}</div> : null}

        {!brief_payload ? (
          <div className="preview_notice">
            Upload documents and refresh the brief to load real onboarding content.
          </div>
        ) : null}

        <section className="brief_grid">
          <article className="panel large_panel">
            <div className="panel_header">
              <span className="panel_icon blue">i</span>
              <h2>Top things to know</h2>
            </div>

            {must_know_items.length ? (
              <div className="numbered_list">
                {must_know_items.map((item, index) => (
                  <div className="numbered_item" key={`${item}-${index}`}>
                    <span className="number_badge">{index + 1}</span>
                    <div>
                      <p className="numbered_title">
                        {item.split(".")[0]}
                        {item.includes(".") ? "." : ""}
                      </p>
                      <p className="numbered_copy">{item}</p>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <p className="numbered_copy">No onboarding brief has been generated yet.</p>
            )}
          </article>

          <aside className="panel tools_panel">
            <h2>Tools checklist</h2>

            {tool_items.length ? (
              <div className="checklist">
                {tool_items.map((tool_name, index) => (
                  <div className="checklist_item" key={`${tool_name}-${index}`}>
                    <span className="check_icon checked">✓</span>
                    <span>{tool_name}</span>
                  </div>
                ))}
              </div>
            ) : (
              <p className="numbered_copy">Tool setup details will appear here after the brief loads.</p>
            )}
          </aside>
        </section>

        <section className="contacts_section">
          <h2>Key contacts</h2>

          {contact_items.length ? (
            <div className="contacts_grid">
              {contact_items.map((contact, index) => (
                <article className="contact_card" key={`${contact.name}-${index}`}>
                  <div className="avatar_circle">{contact.name?.slice(0, 1) || "?"}</div>
                  <div>
                    <p className="contact_name">{contact.name}</p>
                    <p className="contact_role">{contact.reason || "Owner"}</p>
                    <p className="contact_handle">{contact.source || "Referenced in source docs"}</p>
                  </div>
                </article>
              ))}
            </div>
          ) : (
            <div className="preview_notice">Key contacts will appear here after the brief loads.</div>
          )}
        </section>

        <section className="roadmap_section">
          <h2>30-day roadmap</h2>

          <div className="roadmap_grid">
            {roadmap_sections.map((section) => (
              <article className="roadmap_card" key={section.label}>
                <p className="roadmap_label">{section.label}</p>
                <p className="roadmap_title">
                  {section.items[0] || `${section.label} priorities`}
                </p>

                {section.items.length ? (
                  <ul className="roadmap_list">
                    {section.items.map((item, index) => (
                      <li className="roadmap_item" key={`${item}-${index}`}>
                        <span className={`roadmap_dot ${index === 1 ? "active" : ""}`} />
                        <span>{item}</span>
                      </li>
                    ))}
                  </ul>
                ) : (
                  <p className="numbered_copy">No roadmap items available yet.</p>
                )}
              </article>
            ))}
          </div>
        </section>

        <section className="sources_row">
          <span className="sources_label">Sources:</span>
          {brief_sources.length ? (
            render_sources_list(brief_sources)
          ) : (
            <span className="numbered_copy">No sources yet.</span>
          )}
        </section>
      </main>
    );
  }

  function render_chat_details(chat_message) {
    const has_details =
      chat_message.action ||
      chat_message.who_to_contact ||
      chat_message.risk_level ||
      chat_message.next_steps?.length ||
      chat_message.freshness?.length ||
      chat_message.sources?.length;

    if (!has_details) {
      return null;
    }

    return (
      <details className="details_panel">
        <summary>Sources ({chat_message.sources?.length || 0})</summary>

        {chat_message.action ? (
          <p className="detail_line">
            <strong>Next action:</strong> {chat_message.action}
          </p>
        ) : null}

        {chat_message.who_to_contact ? (
          <p className="detail_line">
            <strong>Who to contact:</strong> {chat_message.who_to_contact}
          </p>
        ) : null}

        {chat_message.risk_level ? (
          <p className="detail_line">
            <strong>Risk:</strong> {chat_message.risk_level}
          </p>
        ) : null}

        {chat_message.next_steps?.length ? (
          <div className="detail_block">
            <strong>Next steps</strong>
            <ul className="detail_list">
              {chat_message.next_steps.map((next_step, index) => (
                <li key={`${next_step}-${index}`}>{next_step}</li>
              ))}
            </ul>
          </div>
        ) : null}

        {chat_message.freshness?.length ? (
          <div className="detail_block">
            <strong>Freshness</strong>
            <ul className="detail_list">
              {chat_message.freshness.map((freshness_item, index) => (
                <li key={`${freshness_item.source}-${index}`}>
                  {freshness_item.source}: {freshness_item.freshness}
                </li>
              ))}
            </ul>
          </div>
        ) : null}

        {render_sources_list(chat_message.sources || [])}
      </details>
    );
  }

  function render_analysis_messages() {
    if (chat_messages.length) {
      return chat_messages.map((chat_message, index) => (
        <div
          className={`chat_row ${chat_message.role === "user" ? "user_row" : "assistant_row"}`}
          key={`${chat_message.role}-${index}`}
        >
          <div className={chat_message.role === "user" ? "question_bubble" : "answer_card"}>
            {chat_message.role === "user" ? (
              <p>{chat_message.content}</p>
            ) : (
              <>
                <div className="markdown_body">
                  <ReactMarkdown>{chat_message.content}</ReactMarkdown>
                </div>
                {render_chat_details(chat_message)}
              </>
            )}
          </div>
        </div>
      ));
    }

    return (
      <div className="chat_row assistant_row">
        <div className="answer_card">
          <p className="numbered_copy">
            Ask a question after documents are loaded to see grounded answers here.
          </p>
        </div>
      </div>
    );
  }

  function render_analysis_view() {
    return (
      <main className="page_body analysis_body">
        <section className="analysis_intro">
          <h1 className="analysis_title">How can I help with the data?</h1>
          <p className="analysis_subtitle">
            Ask questions across the documents currently loaded in the backend.
          </p>
        </section>

        {page_notice ? <div className="page_notice">{page_notice}</div> : null}

        <section className="analysis_conversation">{render_analysis_messages()}</section>

        {is_answering ? (
          <div className="loading_stub">Generating grounded answer...</div>
        ) : null}

        <form
          className="question_form"
          onSubmit={(event) => {
            // This prevents the browser reload so the chat can submit client-side.
            event.preventDefault();
            // This submits the typed question through the shared chat request flow.
            submit_question();
          }}
        >
          <button className="form_icon_button" onClick={open_file_picker} type="button">
            +
          </button>

          <input
            className="question_input"
            onChange={(event) => {
              // This keeps the input controlled so the send action always reads the latest text.
              set_question_text(event.target.value);
            }}
            placeholder="Ask a question about your documents..."
            value={question_text}
          />

          <button className="send_button" disabled={!question_text.trim() || is_answering} type="submit">
            →
          </button>
        </form>
      </main>
    );
  }

  return (
    <div className="app_shell">
      <input
        accept=".pdf,.md,.txt,text/markdown,text/plain,application/pdf"
        hidden
        multiple
        onChange={handle_file_selection}
        ref={file_input_ref}
        type="file"
      />

      <aside className="sidebar">
        <div>
          <div className="brand_block">
            <div className="brand_mark">D</div>
            <div>
              <p className="brand_name">Day1 Brain</p>
              <p className="brand_subtitle">ONBOARDING PORTAL</p>
            </div>
          </div>

          {render_sidebar_upload_panel()}
          {render_sidebar_notice()}

          <nav className="sidebar_nav">
            <Link className="nav_link" href="#">
              Documents
            </Link>
            <Link className={`nav_link ${is_brief_view ? "active" : ""}`} href="/">
              Onboarding
            </Link>
            <Link className={`nav_link ${!is_brief_view ? "active" : ""}`} href="/analysis">
              Analysis
            </Link>
            <Link className="nav_link" href="#">
              Settings
            </Link>
          </nav>
        </div>

        <div className="sidebar_footer">
          <Link className="footer_link" href="#">
            Help Center
          </Link>
          <Link className="footer_link" href="#">
            Account
          </Link>
        </div>
      </aside>

      <section className={`content_shell ${!is_brief_view ? "analysis_shell" : ""}`}>
        <header className="topbar">
          <div className="search_shell">
            <span className="search_icon">⌕</span>
            <input className="search_input" placeholder={search_placeholder} readOnly />
          </div>

          <nav className="top_tabs">
            <Link className={`top_tab ${is_brief_view ? "active" : ""}`} href="/">
              Brief
            </Link>
            <Link className={`top_tab ${!is_brief_view ? "active" : ""}`} href="/analysis">
              Ask Anything
            </Link>
          </nav>

          <div className="topbar_actions">
            <button className="deploy_button" type="button">
              Deploy AI
            </button>
            <span className="status_dot">◦</span>
            <span className="status_dot">↻</span>
            <span className="profile_chip">NJ</span>
          </div>
        </header>

        {is_bootstrapping ? (
          <div className="boot_panel">Loading portal...</div>
        ) : is_brief_view ? (
          render_brief_view()
        ) : (
          render_analysis_view()
        )}
      </section>
    </div>
  );
}
