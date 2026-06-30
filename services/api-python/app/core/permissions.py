"""Permission and authorization utilities."""

from enum import StrEnum


class Permission(StrEnum):
    """Global and project-level permission constants."""

    # Wildcard
    ALL = "*"

    # Users
    USERS_READ = "users.read"
    USERS_WRITE = "users.write"
    USERS_DELETE = "users.delete"

    # Global roles
    GLOBAL_ROLES_READ = "global_roles.read"
    GLOBAL_ROLES_WRITE = "global_roles.write"
    GLOBAL_ROLES_ASSIGN = "global_roles.assign"

    # Projects
    PROJECTS_CREATE = "projects.create"
    PROJECTS_READ = "projects.read"
    PROJECTS_WRITE = "projects.write"
    PROJECTS_DELETE = "projects.delete"

    # Project members
    PROJECT_MEMBERS_READ = "project_members.read"
    PROJECT_MEMBERS_WRITE = "project_members.write"

    # Project roles
    PROJECT_ROLES_READ = "project_roles.read"
    PROJECT_ROLES_WRITE = "project_roles.write"

    # Tasks
    TASKS_READ = "tasks.read"
    TASKS_WRITE = "tasks.write"

    # Sprints
    SPRINTS_READ = "sprints.read"
    SPRINTS_WRITE = "sprints.write"

    # Docs
    DOCS_READ = "docs.read"
    DOCS_WRITE = "docs.write"

    # Agents
    AGENTS_READ = "agents.read"
    AGENTS_WRITE = "agents.write"


def has_permission(user_permissions: dict, required: Permission) -> bool:
    """Check if the user's permission map grants the required permission."""
    # Wildcard grants everything
    if user_permissions.get("*"):
        return True

    # Direct match
    if user_permissions.get(required):
        return True

    # Category wildcard (e.g., "users.*" grants "users.read")
    parts = required.split(".")
    if len(parts) >= 2:
        category_wildcard = f"{parts[0]}.*"
        if user_permissions.get(category_wildcard):
            return True

    return False


# Default global role definitions
DEFAULT_GLOBAL_ROLES = [
    {
        "name": "SUPER_ADMIN",
        "permissions": {Permission.ALL: True},
    },
    {
        "name": "ADMIN",
        "permissions": {
            "users.*": True,
            "global_roles.*": True,
            "projects.*": True,
        },
    },
    {
        "name": "USER",
        "permissions": {
            Permission.USERS_READ: True,
            Permission.PROJECTS_CREATE: True,
        },
    },
]

# Default project role definitions
DEFAULT_PROJECT_ROLES = [
    {
        "name": "OWNER",
        "permissions": {Permission.ALL: True},
    },
    {
        "name": "ADMIN",
        "permissions": {
            "project_members.*": True,
            "project_roles.*": True,
            "tasks.*": True,
            "sprints.*": True,
            "docs.*": True,
            "agents.*": True,
            "projects.read": True,
            "projects.write": True,
        },
    },
    {
        "name": "MEMBER",
        "permissions": {
            Permission.PROJECT_MEMBERS_READ: True,
            Permission.PROJECT_ROLES_READ: True,
            Permission.TASKS_READ: True,
            Permission.TASKS_WRITE: True,
            Permission.SPRINTS_READ: True,
            Permission.SPRINTS_WRITE: True,
            Permission.DOCS_READ: True,
            Permission.DOCS_WRITE: True,
            Permission.AGENTS_READ: True,
            Permission.PROJECTS_READ: True,
        },
    },
    {
        "name": "VIEWER",
        "permissions": {
            Permission.PROJECT_MEMBERS_READ: True,
            Permission.TASKS_READ: True,
            Permission.SPRINTS_READ: True,
            Permission.DOCS_READ: True,
            Permission.PROJECTS_READ: True,
        },
    },
]
