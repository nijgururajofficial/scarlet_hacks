from __future__ import annotations

# This keeps prompt-related helpers isolated so agent logic stays focused on orchestration.

# This tuple defines the only roles the backend currently supports.
SUPPORTED_ROLES = (
    "junior engineer",
    "product manager",
    "marketing",
    "hr",
)

# This central mapping keeps each role's context together so prompt updates stay easy to audit.
ROLE_GUIDANCE = {
    "junior engineer": (
        "Focus on engineering setup, codebase workflows, deployment paths, security boundaries, "
        "and the fastest path to a productive first month."
    ),
    "product manager": (
        "Focus on roadmap context, release processes, stakeholder communication, planning rhythms, "
        "and cross-functional dependencies."
    ),
    "marketing": (
        "Focus on approved messaging, brand rules, campaign processes, launch coordination, "
        "and what information is not accessible to this role."
    ),
    "hr": (
        "Focus on people operations, onboarding logistics, handbook policies, escalation paths, "
        "and who owns which process."
    ),
}


def normalize_role(role: str) -> str:
    # This normalizes loose UI input so callers can pass user-friendly role labels safely.
    normalized_role = role.strip().lower()

    # This blocks unsupported roles early so downstream prompts never drift into undefined behavior.
    if normalized_role not in SUPPORTED_ROLES:
        # This message shows the exact supported options so the caller can recover quickly.
        raise ValueError(
            f"Unsupported role '{role}'. Expected one of: {', '.join(SUPPORTED_ROLES)}"
        )

    # This returns the canonical role key used across all prompt builders.
    return normalized_role


def build_brief_system_prompt(role: str) -> str:
    # This validates the role before prompt construction so prompt wording stays consistent.
    normalized_role = normalize_role(role)

    # This pulls role-specific guidance so the model tailors the brief to actual onboarding needs.
    role_guidance = ROLE_GUIDANCE[normalized_role]

    # This system prompt pushes the model toward a structured, role-aware onboarding brief.
    return f"""
You are Agent 1, the Knowledge Transfer Agent for a company onboarding assistant.
You are proactively briefing a new {normalized_role}. They have not asked a question yet.

Use only the provided company context.
Prioritize practical onboarding details over generic advice.
If the context is missing a detail, say that it is not documented.
Highlight access limitations when the role should not have access to something.
{role_guidance}

Return valid JSON only using this exact shape:
{{
  "role": "{normalized_role}",
  "must_knows": ["string", "string"],
  "tools_checklist": ["string", "string"],
  "key_contacts": [
    {{
      "name": "string",
      "reason": "string",
      "source": "string"
    }}
  ],
  "roadmap": {{
    "week_1": ["string", "string"],
    "week_2": ["string", "string"],
    "week_3_4": ["string", "string"]
  }},
  "source_docs": ["string", "string"]
}}
""".strip()


def build_search_system_prompt(role: str) -> str:
    # This validates the role before prompt construction so the model uses a known persona.
    normalized_role = normalize_role(role)

    # This pulls role-specific guidance so the answer is role-aware instead of generic.
    role_guidance = ROLE_GUIDANCE[normalized_role]

    # This system prompt enforces markdown formatting per question type so answers never come out as flat paragraphs.
    return f"""You are Day 1 Brain, an onboarding assistant for a new {normalized_role}.
You answer questions strictly from the provided company documents.

ANSWER FORMATTING RULES — follow these exactly:
- Never write a plain paragraph. Always use markdown structure.
- For howto questions: use a numbered list. Each step is one sentence max.
- For factual questions: one bold key fact, then 1-2 sentences of context.
- For people questions: bold the person's name, then their role and contact on the same line.
- For policy questions: use bullet points, one rule per bullet.
- For unknown: single sentence saying the information is not in the available documents.

CITATION RULES — mandatory:
- After every key fact, command, name, or rule — add the source filename in brackets: [source.md]
- When the document contains an exact command, URL, Slack handle, or policy line —
  reproduce it verbatim wrapped in italic markdown like: *exact text from document*
- Do not paraphrase technical details, names, or commands. Copy them exactly.
- If two documents contradict each other, add a warning Conflict note explicitly.

ROLE FILTER:
- You are answering for a {normalized_role}.
- {role_guidance}
- If an access restriction applies to this role, lead with it in bold.
- Only mention who to contact if a specific person is named in the documents for this topic.

OUTPUT — respond only in this JSON format:
{{
  "query_type": "howto | factual | people | policy | unknown",
  "answer": "fully markdown-formatted answer with inline citations and verbatim italic quotes",
  "sources": ["doc1.md", "doc2.md"],
  "action": "one specific next step the user must take, or null",
  "who_to_contact": "Name (@slack) — reason, or null",
  "risk_level": "low | medium | high | null",
  "next_steps": []
}}

Only populate action, who_to_contact, and risk_level when genuinely relevant.
Leave them null for straightforward informational answers."""


def build_brief_user_prompt(context_block: str) -> str:
    # This user prompt packages the retrieved knowledge so the model can synthesize a complete brief.
    return f"""
Company onboarding context:
{context_block}

Create a proactive onboarding brief from this context.
Return JSON only.
""".strip()


def build_answer_user_prompt(question: str, context_block: str, role: str) -> str:
    # This user prompt reinforces markdown formatting and verbatim citations so the answer stays grounded.
    return f"""QUESTION (from a new {role}):
{question}

COMPANY DOCUMENTS:
{context_block}

INSTRUCTIONS:
- Structure the answer using markdown — no plain paragraphs.
- Copy exact commands, names, URLs, and policy lines verbatim in italics.
- Cite the source filename in brackets after each fact: [filename.md]
- Do not guess. If the answer is not in the documents, say so in one sentence.
- Keep the answer scannable — a new hire should be able to act on it in 30 seconds.
Return JSON only."""
