# ui/styling.py
"""
CSS Styling Configuration & Management Tool
Centralized styling for font sizes, colors, spacing, and other visual properties
"""

import streamlit as st

# Font size configuration (in rem units - easily adjustable)
FONT_SIZES = {
    "body": 1.0,           # Main body text
    "small": 0.85,         # Small text, captions
    "medium": 1.1,         # Medium text
    "large": 1.25,         # Large text
    "heading_1": 2.0,      # h1 headers
    "heading_2": 1.75,     # h2 headers
    "heading_3": 1.5,      # h3 headers
    "heading_4": 1.3,      # h4 headers
    "button": 0.7,        # Button text
    "input": 0.95,         # Input field text
    "label": 0.9,          # Input labels
}

# Color scheme
COLORS = {
    "primary": "#FF6B35",
    "secondary": "#004E89",
    "success": "#28a745",
    "error": "#dc3545",
    "warning": "#ffc107",
    "info": "#17a2b8",
}

# Spacing configuration (in rem units)
SPACING = {
    "xs": 0.25,
    "sm": 0.5,
    "md": 1.0,
    "lg": 1.5,
    "xl": 2.0,
}


def apply_custom_css(font_size_multiplier: float = 1.0):
    """
    Apply custom CSS styling to the entire app.
    
    Args:
        font_size_multiplier: Multiply all font sizes by this value (default 1.0)
                             Use 0.9 to reduce by 10%, 1.1 to increase by 10%
    
    Example:
        apply_custom_css(font_size_multiplier=0.95)  # Slightly smaller fonts
    """
    
    # Calculate adjusted font sizes
    adjusted_sizes = {k: v * font_size_multiplier for k, v in FONT_SIZES.items()}
    
    css = f"""
    <style>
    /* ========== GLOBAL FONT SIZING ========== */
    html, body, [data-baseweb], [data-testid="stAppViewContainer"] {{
        font-size: {adjusted_sizes['body']}rem !important;
    }}
    
    /* ========== HEADERS ========== */
    h1 {{
        font-size: {adjusted_sizes['heading_1']}rem !important;
        margin-bottom: 0.5rem !important;
    }}
    h2 {{
        font-size: {adjusted_sizes['heading_2']}rem !important;
        margin-bottom: 0.4rem !important;
    }}
    h3 {{
        font-size: {adjusted_sizes['heading_3']}rem !important;
        margin-bottom: 0.3rem !important;
    }}
    h4 {{
        font-size: {adjusted_sizes['heading_4']}rem !important;
        margin-bottom: 0.2rem !important;
    }}
    h5, h6 {{
        font-size: {adjusted_sizes['body']}rem !important;
    }}
    
    /* ========== TEXT ELEMENTS ========== */
    p, span, div, li {{
        font-size: {adjusted_sizes['body']}rem !important;
    }}
    
    small, .small {{
        font-size: {adjusted_sizes['small']}rem !important;
    }}
    
    .stCaption {{
        font-size: {adjusted_sizes['small']}rem !important;
    }}
    
    /* ========== BUTTONS ========== */
    button {{
        font-size: {adjusted_sizes['button']}rem !important;
        padding: {SPACING['sm']}rem {SPACING['md']}rem !important;
    }}
    
    button[data-testid="stBaseButton-secondary"],
    button[data-testid="stBaseButton-primary"],
    button[data-testid="stBaseButton-tertiary"] {{
        font-size: {adjusted_sizes['button']}rem !important;
    }}
    
    /* ========== INPUT FIELDS ========== */
    input, textarea, select {{
        font-size: {adjusted_sizes['input']}rem !important;
    }}
    
    label {{
        font-size: {adjusted_sizes['label']}rem !important;
    }}
    
    [data-testid="stSelectbox"] label,
    [data-testid="stNumberInput"] label,
    [data-testid="stTextInput"] label,
    [data-testid="stSlider"] label {{
        font-size: {adjusted_sizes['label']}rem !important;
    }}
    
    /* ========== NAVIGATION ========== */
    [data-testid="stNavigation"] button {{
        font-size: {adjusted_sizes['button']}rem !important;
    }}
    
    /* ========== TABS ========== */
    [data-testid="stTabs"] button {{
        font-size: {adjusted_sizes['button']}rem !important;
    }}
    
    /* ========== METRICS ========== */
    [data-testid="metric-container"] {{
        font-size: {adjusted_sizes['body']}rem !important;
    }}
    
    /* ========== SIDEBAR ========== */
    [data-testid="stSidebar"] {{
        font-size: {adjusted_sizes['body']}rem !important;
    }}
    
    [data-testid="stSidebar"] button {{
        font-size: {adjusted_sizes['button']}rem !important;
    }}
    
    /* ========== TABLES & DATAFRAMES ========== */
    [data-testid="stDataFrame"] {{
        font-size: {adjusted_sizes['small']}rem !important;
    }}
    
    tbody td, thead th {{
        font-size: {adjusted_sizes['small']}rem !important;
    }}
    
    /* ========== EXPANDERS ========== */
    [data-testid="stExpander"] button {{
        font-size: {adjusted_sizes['body']}rem !important;
    }}
    
    /* ========== ALERTS & MESSAGES ========== */
    [data-testid="stAlert"] {{
        font-size: {adjusted_sizes['body']}rem !important;
    }}
    
    /* ========== CODE BLOCKS ========== */
    pre, code {{
        font-size: {adjusted_sizes['small']}rem !important;
    }}
    
    /* ========== HELP TEXT ========== */
    [role="tooltip"],
    .stHelp {{
        font-size: {adjusted_sizes['small']}rem !important;
    }}
    
    /* ========== CONSISTENCY FIXES ========== */
    /* Ensure text doesn't overflow buttons */
    button {{
        white-space: normal !important;
        word-break: break-word !important;
        overflow-wrap: break-word !important;
    }}
    
    /* Improve column layout */
    [data-testid="column"] {{
        overflow: hidden !important;
    }}
    
    </style>
    """
    
    st.markdown(css, unsafe_allow_html=True)


def apply_navbar_css(font_size_multiplier: float = 0.85):
    """
    Apply CSS specifically for navigation bar (navbar).
    Good default is 0.85 to 0.95 to fit navigation items in their boxes.
    
    Args:
        font_size_multiplier: Font size multiplier for navbar (default 0.85)
    """
    adjusted_button_size = FONT_SIZES["button"] * font_size_multiplier
    
    css = f"""
    <style>
    /* ========== NAVBAR SPECIFIC ========== */
    button[key^="nav__"] {{
        font-size: {adjusted_button_size}rem !important;
        padding: 0.3rem 0.4rem !important;
        height: auto !important;
        min-height: 2.5rem !important;
        white-space: normal !important;
        word-break: break-word !important;
        overflow-wrap: break-word !important;
    }}
    
    [data-testid="stElementToolbar"] button {{
        font-size: {adjusted_button_size}rem !important;
    }}
    </style>
    """
    
    st.markdown(css, unsafe_allow_html=True)


def apply_sidebar_css(font_size_multiplier: float = 0.95):
    """
    Apply CSS specifically for sidebar elements.
    
    Args:
        font_size_multiplier: Font size multiplier for sidebar (default 0.95)
    """
    adjusted_sizes = {k: v * font_size_multiplier for k, v in FONT_SIZES.items()}
    
    css = f"""
    <style>
    /* ========== SIDEBAR SPECIFIC ========== */
    [data-testid="stSidebar"] {{
        font-size: {adjusted_sizes['body']}rem !important;
    }}
    
    [data-testid="stSidebar"] p {{
        font-size: {adjusted_sizes['body']}rem !important;
        margin: 0.3rem 0 !important;
    }}
    
    [data-testid="stSidebar"] button {{
        font-size: {adjusted_sizes['button']}rem !important;
    }}
    
    [data-testid="stSidebar"] label {{
        font-size: {adjusted_sizes['label']}rem !important;
    }}
    </style>
    """
    
    st.markdown(css, unsafe_allow_html=True)


def apply_content_css(font_size_multiplier: float = 1.0):
    """
    Apply CSS specifically for main content area.
    
    Args:
        font_size_multiplier: Font size multiplier for content (default 1.0)
    """
    adjusted_sizes = {k: v * font_size_multiplier for k, v in FONT_SIZES.items()}
    
    css = f"""
    <style>
    /* ========== MAIN CONTENT SPECIFIC ========== */
    [data-testid="stAppViewContainer"] > section {{
        font-size: {adjusted_sizes['body']}rem !important;
    }}
    
    .stMetricLabel {{
        font-size: {adjusted_sizes['small']}rem !important;
    }}
    
    .stMetricValue {{
        font-size: {adjusted_sizes['large']}rem !important;
    }}
    
    .stMetricDelta {{
        font-size: {adjusted_sizes['small']}rem !important;
    }}
    </style>
    """
    
    st.markdown(css, unsafe_allow_html=True)


def show_font_size_configurator():
    """
    Display a visual configurator panel for font sizes in the sidebar.
    Call this in your sidebar to let users adjust font sizes on the fly.
    
    Example:
        with st.sidebar:
            show_font_size_configurator()
    """
    st.markdown("### 🎨 Font Size Adjuster")
    
    # Global multiplier
    global_multiplier = st.slider(
        "Global Font Size",
        min_value=0.7,
        max_value=1.4,
        value=1.0,
        step=0.05,
        help="Adjust all font sizes globally (0.7 = 30% smaller, 1.4 = 40% larger)"
    )
    
    col1, col2 = st.columns(2)
    with col1:
        navbar_multiplier = st.slider(
            "Navbar",
            min_value=0.6,
            max_value=1.2,
            value=0.85,
            step=0.05
        )
    
    with col2:
        content_multiplier = st.slider(
            "Content",
            min_value=0.8,
            max_value=1.4,
            value=1.0,
            step=0.05
        )
    
    # Save settings to session state
    if "css_settings" not in st.session_state:
        st.session_state.css_settings = {
            "global": global_multiplier,
            "navbar": navbar_multiplier,
            "content": content_multiplier
        }
    else:
        st.session_state.css_settings["global"] = global_multiplier
        st.session_state.css_settings["navbar"] = navbar_multiplier
        st.session_state.css_settings["content"] = content_multiplier
    
    # Show current settings
    st.caption(f"Global: {global_multiplier:.2f}x | Navbar: {navbar_multiplier:.2f}x | Content: {content_multiplier:.2f}x")
    
    return {
        "global": global_multiplier,
        "navbar": navbar_multiplier,
        "content": content_multiplier
    }


def get_css_settings():
    """Get current CSS settings from session state or return defaults."""
    if "css_settings" not in st.session_state:
        st.session_state.css_settings = {
            "global": 1.0,
            "navbar": 0.85,
            "content": 1.0
        }
    return st.session_state.css_settings


# Predefined CSS profiles for quick application
CSS_PROFILES = {
    "default": {
        "global": 1.0,
        "navbar": 0.85,
        "sidebar": 0.95,
        "content": 1.0,
        "name": "Default (Balanced)"
    },
    "compact": {
        "global": 0.9,
        "navbar": 0.75,
        "sidebar": 0.85,
        "content": 0.95,
        "name": "Compact (Space-saving)"
    },
    "readable": {
        "global": 1.15,
        "navbar": 1.0,
        "sidebar": 1.1,
        "content": 1.2,
        "name": "Readable (Larger fonts)"
    },
    "accessibility": {
        "global": 1.3,
        "navbar": 1.1,
        "sidebar": 1.2,
        "content": 1.35,
        "name": "Accessibility (Largest fonts)"
    }
}


def apply_css_profile(profile_name: str = "default"):
    """
    Apply a predefined CSS profile.
    
    Args:
        profile_name: One of 'default', 'compact', 'readable', 'accessibility'
    
    Example:
        apply_css_profile("compact")
    """
    if profile_name not in CSS_PROFILES:
        st.warning(f"Unknown profile: {profile_name}. Using 'default'.")
        profile_name = "default"
    
    profile = CSS_PROFILES[profile_name]
    
    # Store in session
    st.session_state.css_settings = {
        "global": profile.get("global", 1.0),
        "navbar": profile.get("navbar", 0.85),
        "sidebar": profile.get("sidebar", 0.95),
        "content": profile.get("content", 1.0),
    }
    
    # Apply CSS
    apply_custom_css(profile["global"])
    apply_navbar_css(profile["navbar"])
    apply_sidebar_css(profile["sidebar"])
    apply_content_css(profile["content"])
