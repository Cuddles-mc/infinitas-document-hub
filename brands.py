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

# Aliases for domains with alternate spellings or onmicrosoft.com tenant domains
DOMAIN_ALIASES = {
    "orgintalent.co.nz": "origintalent.co.nz",
    "origintalent.onmicrosoft.com": "origintalent.co.nz",
    "orgintalent.onmicrosoft.com": "origintalent.co.nz",
    "luminoustalent.onmicrosoft.com": "luminoustalent.co.nz",
    "infinitas.onmicrosoft.com": "infinitas.co.nz",
    "infinitastalent.onmicrosoft.com": "infinitas.co.nz",
}


def get_brand(email: str) -> dict:
    """Get brand config from user email domain."""
    if not email or "@" not in email:
        return BRANDS[DEFAULT_BRAND]
    domain = email.split("@")[-1].lower()
    domain = DOMAIN_ALIASES.get(domain, domain)
    return BRANDS.get(domain, BRANDS[DEFAULT_BRAND])


def get_brand_css(brand: dict) -> str:
    """Generate CSS that themes the entire Streamlit app to a brand.

    Modern, polished styling inspired by PandaDoc/Proposify.
    """
    c = brand["colors"]
    return f"""<style>
    /* ===== GLOBAL POLISH ===== */
    .main .block-container {{
        padding-top: 2rem;
        padding-bottom: 2rem;
        max-width: 1100px;
    }}

    /* ===== SIDEBAR ===== */
    section[data-testid="stSidebar"] {{
        background-color: {c['sidebar_bg']};
        border-right: none !important;
        box-shadow: 2px 0 12px rgba(0,0,0,0.08);
    }}
    section[data-testid="stSidebar"] * {{
        color: {c['sidebar_text']} !important;
    }}
    section[data-testid="stSidebar"] hr {{
        border-color: rgba(255,255,255,0.15) !important;
    }}
    /* Sidebar radio items */
    section[data-testid="stSidebar"] .stRadio label {{
        padding: 0.4rem 0.75rem !important;
        border-radius: 6px !important;
        transition: background 0.15s ease !important;
    }}
    section[data-testid="stSidebar"] .stRadio label:hover {{
        background: rgba(255,255,255,0.08) !important;
    }}
    section[data-testid="stSidebar"] .stButton > button {{
        background-color: transparent;
        border: 1px solid rgba(255,255,255,0.25);
        color: {c['sidebar_text']} !important;
        border-radius: 8px !important;
        transition: all 0.15s ease !important;
    }}
    section[data-testid="stSidebar"] .stButton > button:hover {{
        background-color: rgba(255,255,255,0.1);
        border-color: rgba(255,255,255,0.4);
    }}

    /* ===== TYPOGRAPHY ===== */
    .main h1 {{
        color: {c['dark']} !important;
        font-weight: 700 !important;
    }}
    .main h2, .main h3 {{
        color: {c['primary']} !important;
        font-weight: 600 !important;
    }}

    /* ===== CARDS (st.container with border) ===== */
    .main [data-testid="stVerticalBlockBorderWrapper"] {{
        border-radius: 12px !important;
        border-color: #E5E7EB !important;
        transition: border-color 0.2s ease, box-shadow 0.2s ease;
    }}
    .main [data-testid="stVerticalBlockBorderWrapper"]:hover {{
        border-color: {c['primary']} !important;
        box-shadow: 0 4px 12px rgba(0,0,0,0.06);
    }}

    /* ===== BUTTONS ===== */
    .main .stButton > button {{
        border-radius: 8px !important;
        font-weight: 500 !important;
        transition: all 0.15s ease !important;
        letter-spacing: 0.01em;
    }}
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
        transform: translateY(-1px);
        box-shadow: 0 2px 8px rgba(0,0,0,0.12);
    }}

    /* ===== DOWNLOAD BUTTONS ===== */
    .main .stDownloadButton > button {{
        border-radius: 8px !important;
        border-color: {c['primary']} !important;
        color: {c['primary']} !important;
        font-weight: 500 !important;
        transition: all 0.15s ease !important;
    }}
    .main .stDownloadButton > button:hover {{
        background-color: {c['primary']} !important;
        color: white !important;
        transform: translateY(-1px);
        box-shadow: 0 2px 8px rgba(0,0,0,0.12);
    }}
    .main .stDownloadButton > button[kind="primary"],
    .main .stDownloadButton > button[data-testid="stBaseButton-primary"] {{
        background-color: {c['primary']} !important;
        color: white !important;
    }}

    /* ===== INPUTS ===== */
    .main .stTextInput > div > div > input,
    .main .stTextArea > div > div > textarea {{
        border-radius: 8px !important;
        transition: border-color 0.15s ease, box-shadow 0.15s ease !important;
    }}
    .main .stTextInput > div > div > input:focus,
    .main .stTextArea > div > div > textarea:focus {{
        border-color: {c['primary']} !important;
        box-shadow: 0 0 0 2px {c['primary']}22 !important;
    }}
    .main .stSelectbox > div > div {{
        border-radius: 8px !important;
    }}

    /* ===== CHECKBOXES ===== */
    .main .stCheckbox label span[data-testid="stCheckboxLabel"] {{
        font-weight: 400;
    }}

    /* ===== EXPANDERS ===== */
    .main .streamlit-expanderHeader {{
        border-radius: 8px !important;
        font-weight: 500 !important;
    }}

    /* ===== LINKS ===== */
    .main a {{
        color: {c['primary']} !important;
    }}

    /* ===== LINK BUTTONS (Outlook compose) ===== */
    .main .stLinkButton > a {{
        background-color: {c['primary']} !important;
        color: white !important;
        border-color: {c['primary']} !important;
        border-radius: 8px !important;
        transition: all 0.15s ease !important;
    }}
    .main .stLinkButton > a:hover {{
        background-color: {c['button_hover']} !important;
        border-color: {c['button_hover']} !important;
        transform: translateY(-1px);
        box-shadow: 0 2px 8px rgba(0,0,0,0.12);
    }}

    /* ===== DIVIDERS ===== */
    .main hr {{
        border-color: #E5E7EB !important;
        opacity: 0.6;
        margin: 1.5rem 0 !important;
    }}

    /* ===== TABS ===== */
    .stTabs [data-baseweb="tab"] {{
        color: {c['text']} !important;
        font-weight: 500;
    }}
    .stTabs [aria-selected="true"] {{
        color: {c['primary']} !important;
        border-bottom-color: {c['primary']} !important;
    }}

    /* ===== INFO/WARNING/ERROR BOXES ===== */
    .main .stAlert {{
        border-radius: 8px !important;
    }}

    /* ===== FILE UPLOADER ===== */
    .main .stFileUploader {{
        border-radius: 8px !important;
    }}
    .main [data-testid="stFileUploaderDropzone"] {{
        border-radius: 8px !important;
    }}
</style>"""
