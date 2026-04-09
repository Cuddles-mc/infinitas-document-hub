"""Chat page — natural language queries over the Infinitas intelligence database.

Team members ask questions in plain English. The RAG pipeline searches
structured data + embeddings and returns sourced answers via Claude.
Includes autocomplete entity search and full document drill-down.
"""

import streamlit as st
from rag import chat_stream, _get_supabase


POSITION_TYPES = [
    "Chair", "Deputy Chair", "CEO", "CFO", "COO", "CTO", "CIO",
    "CHRO", "CMO", "CRO", "CLO", "Other C-Suite", "GM",
    "Director", "Independent Director", "Executive Director",
    "Company Secretary",
]


def _load_entities():
    """Load company and people names for autocomplete. Cached per session."""
    if "chat_entities" not in st.session_state:
        sb = _get_supabase()
        companies = sb.table("companies").select("id, name").order("name").execute()
        people = sb.table("people").select(
            "id, full_name, current_title, current_company_name"
        ).order("full_name").execute()

        st.session_state.chat_company_map = {c["name"]: c["id"] for c in (companies.data or [])}
        st.session_state.chat_people_map = {p["full_name"]: p["id"] for p in (people.data or [])}

        st.session_state.chat_company_names = [c["name"] for c in (companies.data or [])]
        st.session_state.chat_people_names = [
            f"{p['full_name']} --- {p.get('current_title', '?')} at {p.get('current_company_name', '?')}"
            for p in (people.data or [])
        ]
    return True


def _find_matching_document(query: str) -> dict | None:
    """Check if the query matches a company or person that has a full document."""
    sb = _get_supabase()

    company_map = st.session_state.get("chat_company_map", {})
    for name, cid in company_map.items():
        if name.lower() in query.lower():
            doc = sb.table("documents").select(
                "id, title, slug, content_md, document_type, last_researched, confidence, metadata"
            ).eq("company_id", cid).eq("document_type", "company-brief").is_(
                "deleted_at", "null"
            ).limit(1).execute()
            if doc.data:
                return doc.data[0]

    people_map = st.session_state.get("chat_people_map", {})
    for name, pid in people_map.items():
        if name.lower() in query.lower():
            doc = sb.table("documents").select(
                "id, title, slug, content_md, document_type, last_researched, confidence, metadata"
            ).eq("person_id", pid).eq("document_type", "person-profile").is_(
                "deleted_at", "null"
            ).limit(1).execute()
            if doc.data:
                return doc.data[0]

    return None


def _find_company_leaders(query: str) -> list[dict]:
    """Find leadership team for a matched company, for drill-down buttons."""
    sb = _get_supabase()
    company_map = st.session_state.get("chat_company_map", {})
    for name, cid in company_map.items():
        if name.lower() in query.lower():
            leaders = sb.table("leadership_positions").select(
                "person_name, position_type, title"
            ).eq("company_id", cid).eq("is_current", True).order("position_type").execute()
            return leaders.data or []
    return []


def _extract_people_from_response(response_text: str) -> list[str]:
    """Extract person names from the AI response that exist in our database.

    Matches against the known people list to avoid false positives.
    Returns unique names found, max 12.
    """
    people_map = st.session_state.get("chat_people_map", {})
    if not people_map:
        return []

    found = []
    seen = set()
    for name in people_map:
        if name in response_text and name not in seen:
            found.append(name)
            seen.add(name)
        if len(found) >= 12:
            break
    return found


# Chat-specific CSS
CHAT_CSS = """<style>
.stChatMessage {
    font-size: 0.88rem !important;
    line-height: 1.55 !important;
}
.stChatMessage p {
    font-size: 0.88rem !important;
    margin-bottom: 0.4rem !important;
}
.stChatMessage h1 {
    font-size: 1.15rem !important;
    margin-top: 1rem !important;
    margin-bottom: 0.3rem !important;
}
.stChatMessage h2 {
    font-size: 1.05rem !important;
    margin-top: 0.8rem !important;
    margin-bottom: 0.25rem !important;
}
.stChatMessage h3 {
    font-size: 0.95rem !important;
    margin-top: 0.6rem !important;
    margin-bottom: 0.2rem !important;
}
.stChatMessage li {
    font-size: 0.88rem !important;
    margin-bottom: 0.15rem !important;
}
.stChatMessage ul, .stChatMessage ol {
    margin-top: 0.2rem !important;
    margin-bottom: 0.4rem !important;
    padding-left: 1.2rem !important;
}
.stChatMessage table {
    font-size: 0.82rem !important;
    margin: 0.5rem 0 !important;
}
.stChatMessage th, .stChatMessage td {
    padding: 4px 8px !important;
}
.stChatMessage code {
    font-size: 0.82rem !important;
}
.stChatMessage strong {
    font-weight: 600 !important;
}
.stChatMessage[data-testid="stChatMessageUser"] {
    background: #F0F4FF !important;
    border-radius: 12px !important;
    padding: 0.5rem 0.75rem !important;
}
.stChatMessage[data-testid="stChatMessageAssistant"] {
    background: #FAFAFA !important;
    border: 1px solid #E5E7EB !important;
    border-radius: 12px !important;
    padding: 0.6rem 0.85rem !important;
}
.chat-header {
    padding-bottom: 0.5rem;
    margin-bottom: 0.25rem;
    border-bottom: 1px solid #E5E7EB;
}
.chat-header h2 {
    font-size: 1.2rem !important;
    margin-bottom: 0.1rem !important;
    font-weight: 600 !important;
}
.chat-header p {
    font-size: 0.82rem !important;
    color: #9CA3AF !important;
    margin: 0 !important;
}
/* Snap selectbox dropdown to top of viewport */
.main .block-container {
    scroll-behavior: smooth;
}

/* Full page viewer */
.full-doc-container {
    font-size: 0.85rem !important;
    line-height: 1.6 !important;
    padding: 1rem !important;
    border: 1px solid #E5E7EB;
    border-radius: 12px;
    background: #FAFAFA;
    max-height: 70vh;
    overflow-y: auto;
}
.full-doc-container h1 { font-size: 1.2rem !important; }
.full-doc-container h2 { font-size: 1.05rem !important; }
.full-doc-container h3 { font-size: 0.95rem !important; }
.full-doc-container p, .full-doc-container li { font-size: 0.85rem !important; }
.full-doc-container table { font-size: 0.8rem !important; }

/* Stale doc warning */
.stale-warning {
    background: #FEF3C7;
    border: 1px solid #F59E0B;
    border-radius: 8px;
    padding: 0.4rem 0.75rem;
    font-size: 0.78rem;
    color: #92400E;
    margin: 0.4rem 0;
}
</style>

<script>
// Scroll to top when selectbox is clicked
document.addEventListener('click', function(e) {
    if (e.target.closest('[data-testid="stSelectbox"]')) {
        window.scrollTo({top: 0, behavior: 'smooth'});
    }
});
</script>
"""


def render():
    st.markdown(CHAT_CSS, unsafe_allow_html=True)
    st.markdown(
        '<div class="chat-header">'
        '<h2>Research Assistant</h2>'
        '<p>Search for a company or person, or ask any question below</p>'
        '</div>',
        unsafe_allow_html=True,
    )

    # Initialise state
    if "chat_messages" not in st.session_state:
        st.session_state.chat_messages = []
    if "viewing_doc" not in st.session_state:
        st.session_state.viewing_doc = None

    # Full document viewer mode
    if st.session_state.viewing_doc:
        doc = st.session_state.viewing_doc
        col1, col2 = st.columns([1, 5])
        with col1:
            if st.button("← Back"):
                st.session_state.viewing_doc = None
                st.rerun()
        with col2:
            meta = []
            if doc.get("confidence"):
                meta.append(f"Confidence: {doc['confidence']}")
            if doc.get("last_researched"):
                meta.append(f"Last researched: {doc['last_researched']}")
            if meta:
                st.markdown(
                    f'<p style="font-size: 0.75rem; color: #9CA3AF; margin: 0;">{" | ".join(meta)}</p>',
                    unsafe_allow_html=True,
                )

        # Stale warning in full view
        is_stale = doc.get("confidence") == "draft"
        doc_meta = doc.get("metadata") if isinstance(doc.get("metadata"), dict) else {}
        stale_reason = doc_meta.get("stale_reason") if doc_meta else None
        if is_stale:
            reason_text = f" Reason: {stale_reason}." if stale_reason else ""
            st.warning(
                f"This page may contain outdated information.{reason_text} "
                f"The structured database has newer data — check the AI summary for current facts."
            )

        st.markdown(doc.get("content_md", "No content available."))
        return

    # Search interface — shown when no active conversation
    if not st.session_state.chat_messages:
        _load_entities()
        company_names = st.session_state.get("chat_company_names", [])
        people_names = st.session_state.get("chat_people_names", [])

        # Three lookup cards in a row
        col_co, col_ppl, col_pos = st.columns(3)

        # --- Company lookup ---
        with col_co:
            with st.container(border=True):
                st.markdown(
                    '<p style="font-size: 0.82rem; font-weight: 600; color: #374151; margin: 0 0 0.3rem 0;">'
                    'Company</p>',
                    unsafe_allow_html=True,
                )
                company_sel = st.selectbox(
                    "Company",
                    options=[""] + company_names,
                    index=0,
                    placeholder="Type to search...",
                    label_visibility="collapsed",
                    key="sel_company",
                )
                if st.button("Go", type="primary", use_container_width=True, key="btn_company"):
                    if company_sel:
                        _handle_query(f"What do we know about {company_sel}?")
                        st.rerun()

        # --- People lookup ---
        with col_ppl:
            with st.container(border=True):
                st.markdown(
                    '<p style="font-size: 0.82rem; font-weight: 600; color: #374151; margin: 0 0 0.3rem 0;">'
                    'Person</p>',
                    unsafe_allow_html=True,
                )
                person_sel = st.selectbox(
                    "Person",
                    options=[""] + people_names,
                    index=0,
                    placeholder="Type to search...",
                    label_visibility="collapsed",
                    key="sel_person",
                )
                if st.button("Go", type="primary", use_container_width=True, key="btn_person"):
                    if person_sel:
                        clean = person_sel.split(" --- ")[0] if " --- " in person_sel else person_sel
                        _handle_query(f"What do we know about {clean}?")
                        st.rerun()

        # --- Position lookup ---
        with col_pos:
            with st.container(border=True):
                st.markdown(
                    '<p style="font-size: 0.82rem; font-weight: 600; color: #374151; margin: 0 0 0.3rem 0;">'
                    'Position</p>',
                    unsafe_allow_html=True,
                )
                position_sel = st.selectbox(
                    "Position",
                    options=[""] + POSITION_TYPES,
                    index=0,
                    placeholder="Select a role...",
                    label_visibility="collapsed",
                    key="sel_position",
                )
                if st.button("Go", type="primary", use_container_width=True, key="btn_position"):
                    if position_sel:
                        _handle_query(f"List all current {position_sel}s")
                        st.rerun()

        # --- Ask anything ---
        with st.container(border=True):
            st.markdown(
                '<p style="font-size: 0.82rem; font-weight: 600; color: #374151; margin: 0 0 0.3rem 0;">'
                'Ask anything</p>',
                unsafe_allow_html=True,
            )
            col_q, col_btn = st.columns([6, 1])
            with col_q:
                freeform = st.text_input(
                    "Question",
                    placeholder="e.g. Who has board experience in healthcare?",
                    label_visibility="collapsed",
                )
            with col_btn:
                st.markdown('<div style="height: 0.1rem;"></div>', unsafe_allow_html=True)
                if st.button("Ask", type="primary", use_container_width=True):
                    if freeform:
                        _handle_query(freeform)
                        st.rerun()

    # New search button when conversation is active
    if st.session_state.chat_messages:
        if st.button("← New search", type="secondary"):
            st.session_state.chat_messages = []
            st.rerun()

    # Display conversation history
    for i, msg in enumerate(st.session_state.chat_messages):
        with st.chat_message(msg["role"]):
            st.markdown(msg["display_content"])

        # After the last assistant message, show drill-down options
        if msg["role"] == "assistant" and i == len(st.session_state.chat_messages) - 1:
            user_query = st.session_state.chat_messages[i - 1]["content"] if i > 0 else ""

            # Drill-down buttons for people mentioned in the response
            leaders = _find_company_leaders(user_query)
            people_in_response = _extract_people_from_response(msg["display_content"])

            # Merge: leaders first (with position labels), then any others from the response
            drill_down = []
            leader_names = set()
            if leaders:
                for ldr in leaders:
                    name = ldr.get("person_name", "?")
                    drill_down.append({"name": name, "label": ldr.get("position_type", "")})
                    leader_names.add(name)
            for pname in people_in_response:
                if pname not in leader_names:
                    drill_down.append({"name": pname, "label": ""})

            if drill_down:
                st.markdown(
                    '<p style="font-size: 0.78rem; color: #6B7280; margin: 0.5rem 0 0.25rem;">'
                    'Look up a person:</p>',
                    unsafe_allow_html=True,
                )
                # Show in rows of 4
                for row_start in range(0, min(len(drill_down), 12), 4):
                    row_items = drill_down[row_start:row_start + 4]
                    cols = st.columns(4)
                    for j, item in enumerate(row_items):
                        with cols[j]:
                            btn_label = item["name"]
                            if item["label"]:
                                btn_label += f"\n{item['label']}"
                            if st.button(
                                btn_label,
                                key=f"drill_{i}_{row_start}_{j}",
                                use_container_width=True,
                            ):
                                _handle_query(f"What do we know about {item['name']}?")
                                st.rerun()

            matching_doc = _find_matching_document(user_query)
            if matching_doc:
                # Stale warning
                is_stale = matching_doc.get("confidence") == "draft"
                stale_reason = (matching_doc.get("metadata") or {}).get("stale_reason") if isinstance(matching_doc.get("metadata"), dict) else None
                last_researched = matching_doc.get("last_researched", "")

                if is_stale:
                    reason_text = f" ({stale_reason})" if stale_reason else ""
                    st.markdown(
                        f'<div class="stale-warning">⚠️ This research page may be outdated{reason_text}. '
                        f'Last researched: {last_researched or "unknown"}. '
                        f'Structured data above is current.</div>',
                        unsafe_allow_html=True,
                    )

                if st.button(
                    f"📄 View full research page: {matching_doc.get('title', 'Document')}",
                    key=f"viewdoc_{i}",
                    type="primary",
                ):
                    st.session_state.viewing_doc = matching_doc
                    st.rerun()

    # Chat input
    if prompt := st.chat_input("Ask about people, companies, or intelligence..."):
        _handle_query(prompt)
        st.rerun()


def _handle_query(query: str):
    """Process a query: add to history, run RAG, stream response."""
    st.session_state.chat_messages.append({
        "role": "user",
        "content": query,
        "display_content": query,
    })

    llm_history = [
        {"role": m["role"], "content": m["content"]}
        for m in st.session_state.chat_messages[:-1]
    ]

    full_response = ""
    try:
        for chunk in chat_stream(query, llm_history):
            full_response += chunk
    except Exception as e:
        full_response = f"Sorry, I hit an error: {e}"

    st.session_state.chat_messages.append({
        "role": "assistant",
        "content": full_response,
        "display_content": full_response,
    })
