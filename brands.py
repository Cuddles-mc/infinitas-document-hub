"""Multi-brand configuration for Document Hub.

Auto-detects brand from the signed-in user's email domain.
Generates per-brand CSS for dynamic Streamlit theming.
"""

BRANDS = {
    "infinitas.co.nz": {
        "name": "Infinitas Talent",
        "short_name": "Infinitas",
        "domain": "infinitas.co.nz",
        "logo_url": "https://infinitas.co.nz/wp-content/uploads/2024/11/Infinitas-Logo-HRZ-2.svg",
        "colors": {
            "primary": "#004899",
            "accent": "#72A1E5",
            "dark": "#0E2841",
            "text": "#374151",
            "sidebar_bg": "#0E2841",
            "sidebar_text": "#FFFFFF",
            "button_hover": "#003670",
        },
        "contact": {
            "address": "Ground Floor, Princes Court, 2 Princes Street, Auckland CBD, 1010",
            "phone": "+64 9 218 6127",
            "email": "info@infinitas-talent.co.nz",
            "website": "infinitas.co.nz",
        },
    },
    "luminoustalent.co.nz": {
        "name": "Luminous Talent",
        "short_name": "Luminous",
        "domain": "luminoustalent.co.nz",
        "logo_url": "https://luminoustalent.co.nz/wp-content/uploads/2024/11/LT_Luminous-Horizontal-Icon-Sandy-Brown.svg",
        "colors": {
            "primary": "#C9A46B",
            "accent": "#A87424",
            "dark": "#1C1610",
            "text": "#374151",
            "sidebar_bg": "#1C1610",
            "sidebar_text": "#FFFFFF",
            "button_hover": "#A87424",
        },
        "contact": {
            "address": "",
            "phone": "",
            "email": "",
            "website": "luminoustalent.co.nz",
        },
    },
    "origintalent.co.nz": {
        "name": "Origin Talent",
        "short_name": "Origin",
        "domain": "origintalent.co.nz",
        "logo_url": "https://origintalent.co.nz/wp-content/uploads/elementor/thumbs/OriginTalentLogo-ra35007ms5mqe7apg4ju028gr104pz5o2kvwnmnfyq.png",
        "colors": {
            "primary": "#FF7759",
            "accent": "#F7E4DF",
            "dark": "#1A1214",
            "text": "#374151",
            "sidebar_bg": "#1A1214",
            "sidebar_text": "#FFFFFF",
            "button_hover": "#E5583A",
        },
        "contact": {
            "address": "",
            "phone": "",
            "email": "",
            "website": "origintalent.co.nz",
        },
    },
}

DEFAULT_BRAND = "infinitas.co.nz"

# Aliases for domains with alternate spellings
DOMAIN_ALIASES = {
    "orgintalent.co.nz": "origintalent.co.nz",
}


def get_brand(email: str) -> dict:
    """Get brand config from user email domain."""
    if not email or "@" not in email:
        return BRANDS[DEFAULT_BRAND]
    domain = email.split("@")[-1].lower()
    domain = DOMAIN_ALIASES.get(domain, domain)
    return BRANDS.get(domain, BRANDS[DEFAULT_BRAND])


def get_brand_css(brand: dict) -> str:
    """Generate CSS that themes the entire Streamlit app to a brand."""
    c = brand["colors"]
    return f"""<style>
    /* --- Sidebar --- */
    section[data-testid="stSidebar"] {{
        background-color: {c['sidebar_bg']};
    }}
    section[data-testid="stSidebar"] * {{
        color: {c['sidebar_text']} !important;
    }}
    section[data-testid="stSidebar"] hr {{
        border-color: rgba(255,255,255,0.2) !important;
    }}
    section[data-testid="stSidebar"] .stButton > button {{
        background-color: transparent;
        border: 1px solid rgba(255,255,255,0.3);
        color: {c['sidebar_text']} !important;
    }}
    section[data-testid="stSidebar"] .stButton > button:hover {{
        background-color: rgba(255,255,255,0.1);
        border-color: rgba(255,255,255,0.5);
    }}

    /* --- Headers --- */
    .main h1 {{
        color: {c['dark']} !important;
    }}
    .main h2, .main h3 {{
        color: {c['primary']} !important;
    }}

    /* --- Primary buttons --- */
    .main .stButton > button[kind="primary"],
    .main .stButton > button[data-testid="stBaseButton-primary"] {{
        background-color: {c['primary']};
        border-color: {c['primary']};
        color: white !important;
    }}
    .main .stButton > button[kind="primary"]:hover,
    .main .stButton > button[data-testid="stBaseButton-primary"]:hover {{
        background-color: {c['button_hover']};
        border-color: {c['button_hover']};
    }}

    /* --- Download buttons --- */
    .main .stDownloadButton > button {{
        border-color: {c['primary']} !important;
        color: {c['primary']} !important;
    }}
    .main .stDownloadButton > button:hover {{
        background-color: {c['primary']} !important;
        color: white !important;
    }}
    .main .stDownloadButton > button[kind="primary"],
    .main .stDownloadButton > button[data-testid="stBaseButton-primary"] {{
        background-color: {c['primary']} !important;
        color: white !important;
    }}

    /* --- Links --- */
    .main a {{
        color: {c['primary']} !important;
    }}

    /* --- Dividers --- */
    .main hr {{
        border-color: {c['accent']} !important;
        opacity: 0.4;
    }}

    /* --- Link buttons (Outlook compose) --- */
    .main .stLinkButton > a {{
        background-color: {c['primary']} !important;
        color: white !important;
        border-color: {c['primary']} !important;
    }}
    .main .stLinkButton > a:hover {{
        background-color: {c['button_hover']} !important;
        border-color: {c['button_hover']} !important;
    }}

    /* --- Tabs --- */
    .stTabs [data-baseweb="tab"] {{
        color: {c['text']} !important;
    }}
    .stTabs [aria-selected="true"] {{
        color: {c['primary']} !important;
        border-bottom-color: {c['primary']} !important;
    }}
</style>"""
