"""RAG pipeline — natural language queries over the Infinitas intelligence database.

Combines vector search (document_embeddings) with structured SQL lookups
to answer questions about people, companies, leadership, career history,
and market intelligence.
"""

import json
from typing import Optional

import streamlit as st
from anthropic import Anthropic
from openai import OpenAI
from supabase import create_client


def _get_supabase():
    """Get or create Supabase client from Streamlit secrets."""
    if "rag_supabase" not in st.session_state:
        st.session_state.rag_supabase = create_client(
            st.secrets["SUPABASE_URL"],
            st.secrets["SUPABASE_SERVICE_KEY"],
        )
    return st.session_state.rag_supabase


def _get_openai():
    """Get or create OpenAI client for embeddings."""
    if "rag_openai" not in st.session_state:
        st.session_state.rag_openai = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
    return st.session_state.rag_openai


def _get_anthropic():
    """Get or create Anthropic client for chat."""
    if "rag_anthropic" not in st.session_state:
        st.session_state.rag_anthropic = Anthropic(api_key=st.secrets["ANTHROPIC_API_KEY"])
    return st.session_state.rag_anthropic


def embed_query(text: str) -> list[float]:
    """Embed a search query using OpenAI text-embedding-3-small."""
    client = _get_openai()
    response = client.embeddings.create(
        model="text-embedding-3-small",
        input=[text],
    )
    return response.data[0].embedding


def vector_search(query: str, top_k: int = 8) -> list[dict]:
    """Search document_embeddings via the search_research RPC."""
    sb = _get_supabase()
    query_embedding = embed_query(query)
    result = sb.rpc("search_research", {
        "query_embedding": str(query_embedding),
        "query_text": query,
        "top_k": top_k,
    }).execute()
    return result.data or []


def _person_context(sb, person: dict) -> list[str]:
    """Build rich context lines for a single person, including links."""
    lines = []
    pid = person["id"]
    name = person["full_name"]

    # Main line with LinkedIn
    line = f"- **{name}**: {person.get('current_title', '?')} at {person.get('current_company_name', '?')}"
    if person.get("seniority"):
        line += f" ({person['seniority']})"
    if person.get("base_region"):
        line += f", {person['base_region']}"
    lines.append(line)

    # Contact & links
    links = []
    if person.get("linkedin_url"):
        links.append(f"[LinkedIn]({person['linkedin_url']})")
    if person.get("email"):
        links.append(f"Email: {person['email']}")
    if person.get("relationship_type"):
        links.append(f"Relationship: {person['relationship_type']}")
    if links:
        lines.append(f"  Links: {' | '.join(links)}")

    # Career history
    career = sb.table("career_history").select(
        "title, company_name, start_date, end_date, is_current, function, sector, seniority"
    ).eq("person_id", pid).order("start_date", desc=True).limit(12).execute()

    if career.data:
        lines.append(f"  Career history:")
        for c in career.data:
            dates = ""
            if c.get("start_date"):
                dates = f" ({c['start_date'][:7]}"
                if c.get("end_date"):
                    dates += f" — {c['end_date'][:7]}"
                elif c.get("is_current"):
                    dates += " — present"
                dates += ")"
            extras = []
            if c.get("function"):
                extras.append(c["function"])
            if c.get("sector"):
                extras.append(c["sector"])
            extra_str = f" [{', '.join(extras)}]" if extras else ""
            lines.append(f"    - {c.get('title', '?')} at {c.get('company_name', '?')}{dates}{extra_str}")

    # Leadership / board positions
    leadership = sb.table("leadership_positions").select(
        "position_type, title, is_current, appointed_date, departed_date, companies(name)"
    ).eq("person_id", pid).order("is_current", desc=True).limit(10).execute()

    if leadership.data:
        lines.append(f"  Board & leadership positions:")
        for lp in leadership.data:
            co_name = lp.get("companies", {}).get("name", "?") if lp.get("companies") else "?"
            status = "CURRENT" if lp.get("is_current") else "former"
            appt = f", appointed {lp['appointed_date']}" if lp.get("appointed_date") else ""
            lines.append(f"    - {lp.get('position_type', '?')}: {lp.get('title', '?')} at {co_name} ({status}{appt})")

    return lines


def _company_context(sb, company: dict) -> list[str]:
    """Build rich context lines for a single company, including links."""
    lines = []
    cid = company["id"]
    name = company["name"]

    lines.append(f"- **{name}**")

    if company.get("registered_name") and company["registered_name"].lower() != name.lower():
        lines.append(f"  Registered name: {company['registered_name']}")

    # Key facts
    facts = []
    if company.get("ownership"):
        facts.append(f"Ownership: {company['ownership']}")
    if company.get("headquarters"):
        facts.append(f"HQ: {company['headquarters']}")
    if company.get("employee_count"):
        facts.append(f"~{company['employee_count']} employees")
    if company.get("revenue_estimate"):
        facts.append(f"Revenue est: {company['revenue_estimate']}")
    if facts:
        lines.append(f"  {' | '.join(facts)}")

    if company.get("description"):
        lines.append(f"  Description: {company['description'][:300]}")

    # Links
    links = []
    if company.get("website"):
        links.append(f"[Website]({company['website']})")
    if company.get("linkedin_slug"):
        links.append(f"[LinkedIn](https://www.linkedin.com/company/{company['linkedin_slug']}/)")
    if company.get("nzbn"):
        links.append(f"[CompanyHub](https://www.companyhub.nz/companyDetails.cfm?nzbn={company['nzbn']})")
    elif company.get("companies_office_number"):
        links.append(f"[Companies Office](https://app.companiesoffice.govt.nz/companies/app/ui/pages/companies/{company['companies_office_number']})")
    if links:
        lines.append(f"  Links: {' | '.join(links)}")

    # Intelligence fields
    intel = []
    if company.get("uses_agencies") is True:
        agencies = company.get("agency_names") or []
        if agencies:
            intel.append(f"Uses agencies: {', '.join(agencies)}")
        else:
            intel.append("Uses recruitment agencies: Yes")
    elif company.get("uses_agencies") is False:
        intel.append("Uses recruitment agencies: No")
    if company.get("internal_ta") is True:
        intel.append("Has internal TA team")
    if company.get("email_pattern"):
        intel.append(f"Email pattern: {company['email_pattern']}")
    if intel:
        lines.append(f"  Recruitment intel: {' | '.join(intel)}")

    # Current leadership with LinkedIn, email, tenure
    leaders = sb.table("leadership_positions").select(
        "person_name, position_type, title, person_id, appointed_date, "
        "people(linkedin_url, email)"
    ).eq("company_id", cid).eq("is_current", True).order("position_type").execute()

    if leaders.data:
        lines.append(f"  Current leadership team (include as a table with Name, Title, LinkedIn, Email, Appointed columns):")
        for ldr in leaders.data:
            person_name = ldr.get("person_name", "?")
            title = ldr.get("title", ldr.get("position_type", "?"))
            people_data = ldr.get("people") or {}
            linkedin = people_data.get("linkedin_url", "")
            email = people_data.get("email", "")
            appointed = ldr.get("appointed_date", "")

            linkedin_md = f"[LinkedIn]({linkedin})" if linkedin else "—"
            email_md = email if email else "—"
            appointed_md = appointed[:7] if appointed else "—"

            lines.append(
                f"    | {person_name} | {title} | {linkedin_md} | {email_md} | {appointed_md} |"
            )

        # Career history for leadership team members (enriched context)
        leader_ids = [ldr.get("person_id") for ldr in leaders.data if ldr.get("person_id")]
        if leader_ids:
            for lid in leader_ids[:5]:  # Cap at 5 leaders to avoid massive context
                person_info = sb.table("people").select("full_name").eq("id", lid).limit(1).execute()
                if not person_info.data:
                    continue
                pname = person_info.data[0]["full_name"]
                career = sb.table("career_history").select(
                    "title, company_name, start_date, end_date, is_current, function, sector"
                ).eq("person_id", lid).eq("is_current", False).order("start_date", desc=True).limit(5).execute()
                if career.data:
                    lines.append(f"  Prior career — {pname}:")
                    for c in career.data:
                        dates = ""
                        if c.get("start_date"):
                            dates = f" ({c['start_date'][:7]}"
                            if c.get("end_date"):
                                dates += f" — {c['end_date'][:7]}"
                            dates += ")"
                        lines.append(f"    - {c.get('title', '?')} at {c.get('company_name', '?')}{dates}")

    # Recent events
    events = sb.table("events").select(
        "event_type, headline, event_date, detail, status"
    ).eq("company_id", cid).is_("deleted_at", "null").order(
        "event_date", desc=True
    ).limit(8).execute()

    if events.data:
        lines.append(f"  Recent events/signals:")
        for ev in events.data:
            detail = f" — {ev['detail'][:150]}" if ev.get("detail") else ""
            lines.append(
                f"    - [{ev.get('event_date', '?')}] **{ev.get('event_type', '?')}**: {ev.get('headline', '?')}{detail}"
            )

    # Financials
    fins = sb.table("company_financials").select(
        "fiscal_year, revenue_display, employee_count, source"
    ).eq("company_id", cid).order("fiscal_year", desc=True).limit(3).execute()

    if fins.data:
        lines.append(f"  Financials:")
        for f in fins.data:
            parts = [f"FY{f.get('fiscal_year', '?')}"]
            if f.get("revenue_display"):
                parts.append(f"Revenue: {f['revenue_display']}")
            if f.get("employee_count"):
                parts.append(f"{f['employee_count']} employees")
            if f.get("source"):
                parts.append(f"Source: {f['source']}")
            lines.append(f"    - {', '.join(parts)}")

    return lines


def _intent_queries(query: str) -> str:
    """Detect query intent and run appropriate SQL for analytical questions."""
    sb = _get_supabase()
    q = query.lower()
    context_parts = []

    # --- Position/role queries ---
    position_keywords = {
        "chair": ["Chair", "Deputy Chair"],
        "chairman": ["Chair"],
        "deputy chair": ["Deputy Chair"],
        "ceo": ["CEO"],
        "chief executive": ["CEO"],
        "cfo": ["CFO"],
        "coo": ["COO"],
        "cto": ["CTO"],
        "cio": ["CIO"],
        "chro": ["CHRO"],
        "cmo": ["CMO"],
        "cro": ["CRO"],
        "clo": ["CLO"],
        "director": ["Director", "Independent Director", "Executive Director"],
        "independent director": ["Independent Director"],
        "company secretary": ["Company Secretary"],
        "gm": ["GM"],
        "general manager": ["GM"],
    }

    matched_positions = []
    for keyword, pos_types in position_keywords.items():
        if keyword in q:
            matched_positions.extend(pos_types)

    if matched_positions:
        # Remove duplicates
        matched_positions = list(dict.fromkeys(matched_positions))

        results = sb.table("leadership_positions").select(
            "person_name, position_type, title, appointed_date, is_current, "
            "companies(name, ownership, headquarters), "
            "people(linkedin_url, email)"
        ).in_("position_type", matched_positions).eq(
            "is_current", True
        ).order("position_type").execute()

        if results.data:
            context_parts.append(f"=== All current {'/'.join(matched_positions)} positions ({len(results.data)} results) ===")
            context_parts.append("Format as a markdown table with columns: Name, Title, Company, Ownership, HQ, LinkedIn, Appointed")
            for r in results.data:
                co = r.get("companies") or {}
                ppl = r.get("people") or {}
                linkedin = ppl.get("linkedin_url", "")
                linkedin_md = f"[LinkedIn]({linkedin})" if linkedin else "---"
                appointed = r.get("appointed_date", "")[:7] if r.get("appointed_date") else "---"
                context_parts.append(
                    f"| {r.get('person_name', '?')} | {r.get('title', '?')} | "
                    f"{co.get('name', '?')} | {co.get('ownership', '?')} | "
                    f"{co.get('headquarters', '?')} | {linkedin_md} | {appointed} |"
                )

    # --- Ownership queries ---
    ownership_keywords = {
        "pe-backed": "PE-Backed", "pe backed": "PE-Backed", "private equity": "PE-Backed",
        "listed": "NZX-Listed", "nzx": "NZX-Listed",
        "soe": "SOE", "state owned": "SOE",
        "cooperative": "Cooperative", "co-op": "Cooperative",
        "subsidiary": "Subsidiary",
        "iwi": "Iwi-Owned",
        "not for profit": "NFP", "nfp": "NFP", "not-for-profit": "NFP",
        "vc-backed": "VC-Backed", "venture": "VC-Backed",
    }

    matched_ownership = None
    for keyword, ownership_val in ownership_keywords.items():
        if keyword in q:
            matched_ownership = ownership_val
            break

    if matched_ownership:
        cos = sb.table("companies").select(
            "name, ownership, headquarters, employee_count, website, linkedin_slug"
        ).eq("ownership", matched_ownership).eq("status", "Active").order("name").execute()

        if cos.data:
            context_parts.append(f"\n=== {matched_ownership} companies ({len(cos.data)} results) ===")
            context_parts.append("Format as a markdown table with columns: Company, HQ, Employees, Website, LinkedIn")
            for co in cos.data:
                linkedin = f"[LinkedIn](https://www.linkedin.com/company/{co['linkedin_slug']}/)" if co.get("linkedin_slug") else "---"
                website = f"[Website]({co['website']})" if co.get("website") else "---"
                context_parts.append(
                    f"| {co['name']} | {co.get('headquarters', '?')} | "
                    f"{co.get('employee_count') or '?'} | {website} | {linkedin} |"
                )

    # --- Sector/function career queries ---
    # "CFOs with FMCG experience", "finance people in healthcare"
    function_keywords = {
        "finance": "Finance", "cfo": "Finance", "financial": "Finance",
        "marketing": "Marketing", "cmo": "Marketing",
        "sales": "Sales", "commercial": "Commercial",
        "operations": "Operations", "coo": "Operations",
        "technology": "Technology", "cto": "Technology", "it": "Technology",
        "hr": "People & Culture", "people": "People & Culture", "chro": "People & Culture",
        "legal": "Legal", "clo": "Legal",
        "governance": "Governance",
    }
    sector_keywords = [
        "fmcg", "healthcare", "banking", "financial services", "technology",
        "construction", "retail", "logistics", "transport", "dairy",
        "agriculture", "energy", "insurance", "professional services",
        "manufacturing", "property", "telecommunications", "media",
        "education", "automotive", "infrastructure",
    ]

    matched_function = None
    matched_sector = None
    for kw, func in function_keywords.items():
        if kw in q and ("experience" in q or "background" in q or "sector" in q or "with" in q):
            matched_function = func
            break
    for sector in sector_keywords:
        if sector in q:
            matched_sector = sector.title()
            break

    if matched_function and matched_sector:
        career = sb.table("career_history").select(
            "person_id, title, company_name, sector, function, "
            "people(full_name, current_title, current_company_name, linkedin_url)"
        ).eq("function", matched_function).ilike("sector", f"%{matched_sector}%").execute()

        if career.data:
            # Deduplicate by person
            seen = set()
            unique = []
            for c in career.data:
                ppl = c.get("people") or {}
                name = ppl.get("full_name", "?")
                if name not in seen:
                    seen.add(name)
                    unique.append(c)

            context_parts.append(
                f"\n=== People with {matched_function} experience in {matched_sector} ({len(unique)} people) ==="
            )
            context_parts.append("Format as a markdown table with columns: Name, Current Role, Current Company, Relevant Role, At Company, LinkedIn")
            for c in unique[:30]:
                ppl = c.get("people") or {}
                linkedin = ppl.get("linkedin_url", "")
                linkedin_md = f"[LinkedIn]({linkedin})" if linkedin else "---"
                context_parts.append(
                    f"| {ppl.get('full_name', '?')} | {ppl.get('current_title', '?')} | "
                    f"{ppl.get('current_company_name', '?')} | {c.get('title', '?')} | "
                    f"{c.get('company_name', '?')} | {linkedin_md} |"
                )

    # --- Agency usage queries ---
    if "agenc" in q or "recruitment" in q or "recruiter" in q:
        agency_cos = sb.table("companies").select(
            "name, headquarters, agency_names, uses_agencies, internal_ta"
        ).eq("uses_agencies", True).order("name").execute()

        if agency_cos.data:
            context_parts.append(f"\n=== Companies using recruitment agencies ({len(agency_cos.data)} results) ===")
            for co in agency_cos.data:
                agencies = ", ".join(co.get("agency_names") or ["Unknown"])
                internal = "Yes" if co.get("internal_ta") else "No"
                context_parts.append(
                    f"| {co['name']} | {co.get('headquarters', '?')} | {agencies} | Internal TA: {internal} |"
                )

    # --- Recent events queries ---
    if "recent" in q and ("change" in q or "signal" in q or "event" in q or "departure" in q or "appointment" in q):
        events = sb.table("events").select(
            "event_type, headline, event_date, company_name, person_name"
        ).is_("deleted_at", "null").not_.in_(
            "event_type", ["job_posting", "watchlist_entry"]
        ).order("event_date", desc=True).limit(20).execute()

        if events.data:
            context_parts.append(f"\n=== Recent events ({len(events.data)} most recent) ===")
            for ev in events.data:
                context_parts.append(
                    f"| {ev.get('event_date', '?')} | {ev.get('event_type', '?')} | "
                    f"{ev.get('headline', '?')} | {ev.get('company_name', '?')} | {ev.get('person_name', '') or ''} |"
                )

    return "\n".join(context_parts) if context_parts else ""


def structured_lookup(query: str) -> str:
    """Run structured SQL lookups based on query intent."""
    sb = _get_supabase()
    context_parts = []

    # First: intent-based analytical queries
    intent_context = _intent_queries(query)
    if intent_context:
        context_parts.append(intent_context)

    # Then: name-based entity lookups
    people = sb.table("people").select(
        "id, full_name, current_title, current_company_name, seniority, "
        "base_region, email, linkedin_url, relationship_type"
    ).ilike("full_name", f"%{query}%").limit(5).execute()

    if people.data:
        context_parts.append("=== People matches ===")
        for p in people.data:
            context_parts.extend(_person_context(sb, p))

    companies = sb.table("companies").select(
        "id, name, registered_name, ownership, status, headquarters, website, "
        "description, employee_count, revenue_estimate, uses_agencies, agency_names, "
        "internal_ta, email_pattern, linkedin_slug, nzbn, companies_office_number"
    ).ilike("name", f"%{query}%").limit(5).execute()

    if companies.data:
        context_parts.append("\n=== Company matches ===")
        for co in companies.data:
            context_parts.extend(_company_context(sb, co))

    return "\n".join(context_parts) if context_parts else ""


def build_context(query: str) -> str:
    """Build combined context from vector search + structured lookups."""
    vector_results = vector_search(query, top_k=8)
    structured_context = structured_lookup(query)

    context_parts = []

    if structured_context:
        context_parts.append("## Structured Database Results\n" + structured_context)

    if vector_results:
        context_parts.append("\n## Semantic Search Results")
        for i, r in enumerate(vector_results, 1):
            source = r.get("source_type", "?")
            title = r.get("title", "Untitled")
            score = r.get("score", 0)
            content = r.get("content", "")[:2000]
            context_parts.append(f"\n### [{source}] {title} (relevance: {score:.2f})")
            context_parts.append(content)

    return "\n".join(context_parts)


SYSTEM_PROMPT = """You are the Infinitas Talent intelligence assistant. You help the team at Infinitas Talent (a New Zealand executive search firm) query their research database.

You have access to structured data about:
- People: executives, board members, candidates — with career history, seniority, function, sector
- Companies: NZ companies with leadership teams, ownership, financials, recruitment activity
- Leadership positions: who holds what board/executive role at which company
- Career history: full career trajectories with function and sector tags
- Events: leadership changes, departures, financial results, M&A, job postings, competitor placements
- Documents: company briefs and person profiles with detailed narrative research

When answering:
- Be direct and concise. Use short paragraphs and bullet points.
- Use NZ English (organisation, recognise).
- When listing people, include their current title and company.
- **Always include clickable links when available** — LinkedIn profile links for people, LinkedIn company page links, CompanyHub links, and website URLs. Format as markdown links: [Label](url).
- If the data doesn't contain the answer, say so clearly — don't make things up.
- If you can see relevant career history or board positions, include them.
- Cite the data source briefly (e.g. "from career history" or "from company brief").
- For BD-relevant questions, highlight signals (active hiring, leadership changes, uses agencies, PE-backed).
- **Always format leadership teams as a markdown table** with columns: Name, Title, LinkedIn, Email, Appointed. Make LinkedIn URLs clickable links.
- Use markdown tables where it makes the data clearer (e.g. career timelines, comparisons).
- Keep responses focused — executive summary style, not essays.
- When the context has structured data AND narrative docs, prefer the structured data for facts (it's verified). Use narrative docs for context and analysis only.

You are answering questions from Tate, Jason, or Kelsi at Infinitas Talent. They're executive search consultants — give them actionable intelligence, not generic summaries."""


def _is_complex_query(query: str) -> bool:
    """Detect whether a query needs Sonnet (complex) or Haiku (simple lookup)."""
    complex_signals = [
        "compare", "analyse", "analyze", "strategy", "recommend", "advise",
        "what should", "how can", "why", "assess", "evaluate", "suggest",
        "opportunities", "approach", "pitch", "angle", "bd ",
        "plausible mandates", "warm path", "connections between",
        "who could", "what if", "scenario", "trend",
    ]
    q_lower = query.lower()
    return any(signal in q_lower for signal in complex_signals)


def chat_stream(query: str, conversation_history: list[dict]):
    """Stream the RAG pipeline response for real-time display.

    Uses Haiku for simple entity lookups, Sonnet for complex analytical queries.
    """
    context = build_context(query)
    use_sonnet = _is_complex_query(query)
    model = "claude-sonnet-4-6" if use_sonnet else "claude-haiku-4-5-20251001"

    messages = []
    for msg in conversation_history[-10:]:
        messages.append(msg)

    user_message = f"""Question: {query}

--- Retrieved Context ---
{context if context else "No matching records found in the database."}
--- End Context ---

Answer the question using the context above. Include clickable markdown links for LinkedIn profiles, company websites, and CompanyHub where the data provides URLs. If the context doesn't contain enough information, say what you do know and what's missing."""

    messages.append({"role": "user", "content": user_message})

    client = _get_anthropic()
    with client.messages.stream(
        model=model,
        max_tokens=4096,
        system=SYSTEM_PROMPT,
        messages=messages,
    ) as stream:
        for text in stream.text_stream:
            yield text
