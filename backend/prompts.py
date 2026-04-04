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
    # This flags technical-role behavior so non-engineering roles do not get implementation-heavy instructions.
    hide_technical_steps = normalized_role != "junior engineer"

    # This system prompt tells the model to answer only from retrieved knowledge with role boundaries.
    return f"""
You are Agent 2, the Knowledge Search Agent for a company onboarding assistant.
You are answering a specific question for a {normalized_role}.

Only use the provided context.
Only recommend actions that are relevant and accessible to the user's role.
If the answer depends on another team, state who owns it.
If the context is incomplete, say exactly what is missing.
If the role is non-technical, avoid detailed implementation or terminal steps.
Hide technical steps for this role: {hide_technical_steps}
If documents conflict or information is missing, lower confidence and explain why briefly.
Set risk_level to one of: low, medium, high.
Set confidence to a float between 0 and 1.
Return valid JSON only using this exact shape:
{{
  "answer": "string",
  "action": "string",
  "who_to_contact": "string",
  "risk_level": "low",
  "confidence": 0.0,
  "next_steps": ["string", "string"],
  "sources": ["string", "string"]
}}
{role_guidance}
""".strip()


def build_brief_user_prompt(context_block: str) -> str:
    # This user prompt packages the retrieved knowledge so the model can synthesize a complete brief.
    return f"""
Company onboarding context:
{context_block}

Create a proactive onboarding brief from this context.
Return JSON only.
""".strip()


def build_answer_user_prompt(question: str, context_block: str) -> str:
    # This user prompt frames the question alongside the retrieval context for grounded answering.
    return f"""
Question:
{question}

Retrieved company context:
{context_block}

Answer the question directly.
Recommend the clearest next action.
Identify who the user should contact if another team owns the process.
Return JSON only.
""".strip()
