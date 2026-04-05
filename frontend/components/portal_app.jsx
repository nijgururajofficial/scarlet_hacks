"use client";

import Link from "next/link";
import { useEffect, useMemo, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";

const backend_role = "junior engineer";

async function read_error_message(response) {
  try {
    const payload = await response.json();
    return payload.detail || "Request failed.";
  } catch {
    return "Request failed.";
  }
}

function get_backend_url() {
  return process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8000";
}

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
  const file_input_ref = useRef(null);
  const [selected_files, set_selected_files] = useState([]);
  const [health_payload, set_health_payload] = useState(null);
  const [brief_payload, set_brief_payload] = useState(null);
  const [chat_messages, set_chat_messages] = useState([]);
  const [question_text, set_question_text] = useState("");
  const [is_bootstrapping, set_is_bootstrapping] = useState(true);
  const [is_uploading, set_is_uploading] = useState(false);
  const [is_loading_brief, set_is_loading_brief] = useState(false);
  const [is_answering, set_is_answering] = useState(false);
  const [sidebar_notice, set_sidebar_notice] = useState("");
  const [page_notice, set_page_notice] = useState("");
  const [has_requested_initial_brief, set_has_requested_initial_brief] = useState(false);

  const search_placeholder = useMemo(() => {
    return active_view === "brief" ? "Search knowledge..." : "Search insights...";
  }, [active_view]);
  const is_brief_view = active_view === "brief";
  const brief_sources = brief_payload?.sources || [];
  const roadmap_sections = build_roadmap_sections(brief_payload?.roadmap);
  const must_know_items = brief_payload?.must_knows || [];
  const tool_items = brief_payload?.tools || [];
  const contact_items = brief_payload?.contacts || [];
  const upload_summary = health_payload
    ? `${health_payload.docs_loaded} documents ingested - ${health_payload.chunks_loaded} chunks indexed`
    : "Connect the backend to load live data.";

  useEffect(() => {
    let is_active = true;

    async function bootstrap_app() {
      try {
        const next_health_payload = await fetch_health_payload();

        if (!is_active) {
          return;
        }

        if (is_brief_view && next_health_payload?.has_knowledge_base) {
          await fetch_brief_payload(true);
        }
      } catch (error) {
        if (is_active) {
          set_sidebar_notice(error.message);
        }
      } finally {
        if (is_active) {
          set_is_bootstrapping(false);
        }
      }
    }

    bootstrap_app();

    return () => {
      is_active = false;
    };
  }, [is_brief_view]);

  async function fetch_health_payload() {
    const response = await fetch(`${get_backend_url()}/health`);

    if (!response.ok) {
      throw new Error(await read_error_message(response));
    }

    const next_health_payload = await response.json();
    set_health_payload(next_health_payload);
    return next_health_payload;
  }

  async function fetch_brief_payload(silence_error = false) {
    if (has_requested_initial_brief && silence_error) {
      return;
    }

    set_is_loading_brief(true);

    try {
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
        throw new Error(await read_error_message(response));
      }

      const next_brief_payload = await response.json();
      set_brief_payload(next_brief_payload);
      set_has_requested_initial_brief(true);
      set_page_notice("");
    } catch (error) {
      set_has_requested_initial_brief(true);

      if (!silence_error) {
        set_page_notice(error.message);
      }
    } finally {
      set_is_loading_brief(false);
    }
  }

  function open_file_picker() {
    file_input_ref.current?.click();
  }

  function handle_file_selection(event) {
    const next_selected_files = Array.from(event.target.files || []);
    set_selected_files(next_selected_files);
  }

  async function upload_selected_files() {
    if (!selected_files.length || is_uploading) {
      return;
    }

    set_is_uploading(true);
    set_sidebar_notice("");

    try {
      const form_data = new FormData();

      selected_files.forEach((selected_file) => {
        form_data.append("files", selected_file);
      });

      const response = await fetch(`${get_backend_url()}/ingest`, {
        method: "POST",
        body: form_data,
      });

      if (!response.ok) {
        throw new Error(await read_error_message(response));
      }

      const ingest_result = await response.json();
      await fetch_health_payload();
      set_brief_payload(null);
      set_chat_messages([]);
      set_sidebar_notice(
        `Loaded ${ingest_result.docs} documents and ${ingest_result.chunks} chunks.`,
      );

      if (is_brief_view) {
        await fetch_brief_payload();
      }
    } catch (error) {
      set_sidebar_notice(error.message);
    } finally {
      set_is_uploading(false);
    }
  }

  async function submit_question(question_override) {
    const next_question = (question_override || question_text).trim();

    if (!next_question || is_answering) {
      return;
    }

    set_chat_messages((current_messages) => [
      ...current_messages,
      {
        role: "user",
        content: next_question,
      },
    ]);
    set_question_text("");
    set_is_answering(true);
    set_page_notice("");

    try {
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
        throw new Error(await read_error_message(response));
      }

      const answer_payload = await response.json();
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
            onClick={() => fetch_brief_payload()}
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
            event.preventDefault();
            submit_question();
          }}
        >
          <button className="form_icon_button" onClick={open_file_picker} type="button">
            +
          </button>

          <input
            className="question_input"
            onChange={(event) => set_question_text(event.target.value)}
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
