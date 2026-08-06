# ============================================================
# Role-Based Access Control (RBAC) System
# ============================================================

from enum import Enum
from typing import Callable, Optional, List, Set
from functools import wraps
import streamlit as st


# ============================================================
# Role Definitions
# ============================================================

class Role(str, Enum):
    """Available roles in the application"""
    ADMIN = "admin"                    # Full access to all features
    RESEARCH = "research"              # Access to design, optimization, analysis
    EDUCATOR = "educator"              # Access to tutorials, quiz, materials
    STUDENT = "student"                # Limited access for learning
    VIEWER = "viewer"                  # Read-only access


# ============================================================
# Permission Definitions
# ============================================================

class Permission(str, Enum):
    """Fine-grained permissions"""
    # Design permissions
    VIEW_DESIGN = "view_design"
    CREATE_DESIGN = "create_design"
    EDIT_DESIGN = "edit_design"
    DELETE_DESIGN = "delete_design"
    SHARE_DESIGN = "share_design"
    
    # Optimization permissions
    VIEW_OPTIMIZATION = "view_optimization"
    RUN_OPTIMIZATION = "run_optimization"
    EXPORT_RESULTS = "export_results"
    
    # Analysis permissions
    VIEW_ANALYSIS = "view_analysis"
    GENERATE_REPORTS = "generate_reports"
    ACCESS_AI = "access_ai"
    
    # Admin permissions
    MANAGE_USERS = "manage_users"
    VIEW_AUDIT_LOG = "view_audit_log"
    CONFIGURE_SYSTEM = "configure_system"
    
    # Educational permissions
    VIEW_MATERIALS = "view_materials"
    VIEW_PROTOCOLS = "view_protocols"
    TAKE_QUIZ = "take_quiz"


# ============================================================
# Role-to-Permissions Mapping
# ============================================================

ROLE_PERMISSIONS: dict[Role, Set[Permission]] = {
    Role.ADMIN: {
        # All permissions
        Permission.VIEW_DESIGN, Permission.CREATE_DESIGN, Permission.EDIT_DESIGN, 
        Permission.DELETE_DESIGN, Permission.SHARE_DESIGN,
        Permission.VIEW_OPTIMIZATION, Permission.RUN_OPTIMIZATION, Permission.EXPORT_RESULTS,
        Permission.VIEW_ANALYSIS, Permission.GENERATE_REPORTS, Permission.ACCESS_AI,
        Permission.MANAGE_USERS, Permission.VIEW_AUDIT_LOG, Permission.CONFIGURE_SYSTEM,
        Permission.VIEW_MATERIALS, Permission.VIEW_PROTOCOLS, Permission.TAKE_QUIZ,
    },
    
    Role.RESEARCH: {
        # Can design, optimize, analyze
        Permission.VIEW_DESIGN, Permission.CREATE_DESIGN, Permission.EDIT_DESIGN, 
        Permission.DELETE_DESIGN, Permission.SHARE_DESIGN,
        Permission.VIEW_OPTIMIZATION, Permission.RUN_OPTIMIZATION, Permission.EXPORT_RESULTS,
        Permission.VIEW_ANALYSIS, Permission.GENERATE_REPORTS, Permission.ACCESS_AI,
        Permission.VIEW_MATERIALS, Permission.VIEW_PROTOCOLS,
    },
    
    Role.EDUCATOR: {
        # Can view materials, create designs, run optimizations
        Permission.VIEW_DESIGN, Permission.CREATE_DESIGN, Permission.EDIT_DESIGN,
        Permission.VIEW_OPTIMIZATION, Permission.RUN_OPTIMIZATION, Permission.EXPORT_RESULTS,
        Permission.VIEW_ANALYSIS, Permission.GENERATE_REPORTS,
        Permission.VIEW_MATERIALS, Permission.VIEW_PROTOCOLS, Permission.TAKE_QUIZ,
    },
    
    Role.STUDENT: {
        # Limited access - mainly viewing and learning
        Permission.VIEW_DESIGN, Permission.CREATE_DESIGN, Permission.EDIT_DESIGN,
        Permission.VIEW_OPTIMIZATION, Permission.RUN_OPTIMIZATION,
        Permission.VIEW_ANALYSIS, Permission.GENERATE_REPORTS,
        Permission.VIEW_MATERIALS, Permission.VIEW_PROTOCOLS, Permission.TAKE_QUIZ,
    },
    
    Role.VIEWER: {
        # Read-only access
        Permission.VIEW_DESIGN, Permission.VIEW_OPTIMIZATION,
        Permission.VIEW_ANALYSIS, Permission.VIEW_MATERIALS, Permission.VIEW_PROTOCOLS,
    },
}


# ============================================================
# Tab Definitions with Role Requirements
# ============================================================

ROLE_TAB_ACCESS: dict[str, Set[Role]] = {
    "🏠 Home": {Role.ADMIN, Role.RESEARCH, Role.EDUCATOR, Role.STUDENT, Role.VIEWER},
    "🧱 Materials": {Role.ADMIN, Role.RESEARCH, Role.EDUCATOR, Role.STUDENT, Role.VIEWER},
    "🎨 Design": {Role.ADMIN, Role.RESEARCH, Role.EDUCATOR, Role.STUDENT},
    "📈 Delivery": {Role.ADMIN, Role.RESEARCH, Role.EDUCATOR, Role.STUDENT},
    "☣️ Toxicity": {Role.ADMIN, Role.RESEARCH, Role.EDUCATOR, Role.STUDENT},
    "💰 Cost": {Role.ADMIN, Role.RESEARCH, Role.EDUCATOR, Role.STUDENT},
    "🧾 Protocol": {Role.ADMIN, Role.RESEARCH, Role.EDUCATOR, Role.STUDENT, Role.VIEWER},
    "🎯 Quiz": {Role.ADMIN, Role.RESEARCH, Role.EDUCATOR, Role.STUDENT},
    "🔬 3D View": {Role.ADMIN, Role.RESEARCH, Role.EDUCATOR, Role.STUDENT},
    "🤖 AI Optimize": {Role.ADMIN, Role.RESEARCH, Role.EDUCATOR},
    "⚙️ Admin": {Role.ADMIN},
}


# ============================================================
# Helper Functions
# ============================================================

def get_user_role() -> Optional[Role]:
    """Get current user's role from session state"""
    role_str = st.session_state.get("role")
    if not role_str:
        return None
    try:
        return Role(role_str)
    except ValueError:
        return None


def has_permission(permission: Permission) -> bool:
    """Check if current user has a specific permission"""
    role = get_user_role()
    if not role:
        return False
    
    return permission in ROLE_PERMISSIONS.get(role, set())


def has_role(role: Role) -> bool:
    """Check if current user has a specific role"""
    user_role = get_user_role()
    if not user_role:
        return False
    return user_role == role


def has_any_role(*roles: Role) -> bool:
    """Check if current user has any of the specified roles"""
    user_role = get_user_role()
    if not user_role:
        return False
    return user_role in roles


def can_access_tab(tab_name: str) -> bool:
    """Check if current user can access a specific tab"""
    role = get_user_role()
    if not role:
        return False
    
    allowed_roles = ROLE_TAB_ACCESS.get(tab_name, set())
    return role in allowed_roles


def get_available_tabs(all_tabs: List[str]) -> List[str]:
    """Filter tabs based on current user's role"""
    return [tab for tab in all_tabs if can_access_tab(tab)]


def require_permission(permission: Permission) -> Callable:
    """Decorator to require a specific permission"""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            if not has_permission(permission):
                st.error(f"❌ Access Denied: You do not have the '{permission}' permission.")
                st.info(f"📋 Your role ({get_user_role()}) does not have access to this feature.")
                st.stop()
            return func(*args, **kwargs)
        return wrapper
    return decorator


def require_role(*roles: Role) -> Callable:
    """Decorator to require specific roles"""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            if not has_any_role(*roles):
                role_names = ", ".join([r.value for r in roles])
                st.error(f"❌ Access Denied: You need one of these roles: {role_names}")
                st.info(f"📋 Your current role is: {get_user_role()}")
                st.stop()
            return func(*args, **kwargs)
        return wrapper
    return decorator


def show_permission_warning(feature: str):
    """Display a warning about insufficient permissions"""
    st.warning(
        f"⚠️ **Limited Access**: {feature} is restricted to higher-level roles. "
        f"Your current role ({get_user_role()}) has limited access to this feature."
    )


def show_role_badge():
    """Display current role as a styled badge in sidebar"""
    role = get_user_role()
    if not role:
        return
    
    # Color mapping for roles
    role_colors = {
        Role.ADMIN: "#FF4444",      # Red
        Role.RESEARCH: "#4444FF",   # Blue
        Role.EDUCATOR: "#44FF44",   # Green
        Role.STUDENT: "#FFAA44",    # Orange
        Role.VIEWER: "#CCCCCC",     # Gray
    }
    
    color = role_colors.get(role, "#CCCCCC")
    st.markdown(
        f"""
        <div style='
            background-color: {color};
            color: white;
            padding: 8px 12px;
            border-radius: 6px;
            text-align: center;
            font-weight: bold;
            margin: 10px 0;
        '>
        🔐 {role.value.upper()}
        </div>
        """,
        unsafe_allow_html=True
    )


# ============================================================
# Role Information Display
# ============================================================

def show_role_info():
    """Display information about current role's permissions"""
    role = get_user_role()
    if not role:
        return
    
    st.subheader(f"📋 Role: {role.value.upper()}")
    
    permissions = ROLE_PERMISSIONS.get(role, set())
    
    # Group permissions by category
    categories = {
        "Design": [p for p in permissions if "DESIGN" in p.value],
        "Optimization": [p for p in permissions if "OPTIMIZATION" in p.value],
        "Analysis": [p for p in permissions if "ANALYSIS" in p.value or "REPORT" in p.value],
        "Administration": [p for p in permissions if "MANAGE" in p.value or "AUDIT" in p.value or "CONFIGURE" in p.value],
        "Education": [p for p in permissions if p.value in ["VIEW_MATERIALS", "VIEW_PROTOCOLS", "TAKE_QUIZ"]],
    }
    
    for category, perms in categories.items():
        if perms:
            st.write(f"**{category}:**")
            for perm in perms:
                st.write(f"- ✅ {perm.value}")
    
    # Show inaccessible features
    all_permissions = set()
    for perms in ROLE_PERMISSIONS.values():
        all_permissions.update(perms)
    
    missing_permissions = all_permissions - permissions
    if missing_permissions:
        st.write("**Restricted Features:**")
        for perm in missing_permissions:
            st.write(f"- ❌ {perm.value}")


# ============================================================
# Role Assignment Helper (for admin)
# ============================================================

def get_role_description(role: Role) -> str:
    """Get a human-readable description of a role"""
    descriptions = {
        Role.ADMIN: "Full system access - can manage users, view audit logs, configure system settings",
        Role.RESEARCH: "Research access - can design, optimize, analyze, and export results",
        Role.EDUCATOR: "Educator access - can teach with materials, protocols, and design tools",
        Role.STUDENT: "Student access - can learn through design and optimization with limited features",
        Role.VIEWER: "Viewer access - read-only access to designs, materials, and protocols",
    }
    return descriptions.get(role, "Unknown role")
