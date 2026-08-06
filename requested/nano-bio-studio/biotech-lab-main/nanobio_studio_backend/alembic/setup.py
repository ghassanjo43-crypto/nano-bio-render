"""
Alembic configuration for database migrations.
Generated script to initialize Alembic for NanoBio Studio.
"""
from pathlib import Path


def create_alembic_env():
    """Create alembic.ini file."""
    content = """# Alembic Configuration
# path to migration scripts
script_location = alembic

# template used to generate migration file names; The default value is %%(rev)s_%%(slug)s
# Uncomment the line below if you want the files to be prepended with date and time
#file_template = %%(rev)s_%%(slug)s_%%(ts)s

# sys.path path, will be prepended to sys.path if present
# defaults to the current directory
prepend_sys_path = .

# timezone to use when rendering the date within the migration file
# as well as the filename.
# string value is passed to the constructor of datetime.datetime
# leave blank for localtime
# timezone =

# max length of characters to apply to the
# "slug" field of the migration name.
# set to 0 to disable, omitting or negative value prevents truncation
# truncate_slug_length = 40

# set to 'true' to run the environment during
# the 'revision' command, regardless of autogenerate
# revision_environment = false

# set to 'true' to allow .pyc and .pyo files without
# a source .py file to be detected as revisions in the
# versions/ directory
# sourceless = false

# set dates of migrations to be rendered
# as rev.timestamp
# dated_revisions = false

# set to 'true' to detect common migration drift
# (modification of migration files in the versions
# directory outside of Alembic)
# detect_drift = true

# set to 'false' to skip the automatic
# generation of the initial empty migration
# include_object = include_object

# set to 'true' to enable the -x generic option to revision,
# which allows passing in arbitrary user defined vars
# to the environment.py file
# compare_type = false

# compare server default with offline mode
# compare_server_default = false

# Logging configuration
[loggers]
keys = root,sqlalchemy,alembic

[handlers]
keys = console

[formatters]
keys = generic

[logger_root]
level = WARN
handlers = console
qualname =

[logger_sqlalchemy]
level = WARN
handlers =
qualname = sqlalchemy.engine

[logger_alembic]
level = INFO
handlers =
qualname = alembic

[handler_console]
class = StreamHandler
args = (sys.stderr,)
level = NOTSET
formatter = generic

[formatter_generic]
format = %(levelname)-5.5s [%(name)s] %(message)s
datefmt = %H:%M:%S
"""
    return content


def create_alembic_env_py():
    """Create alembic/env.py."""
    content = '''"""Alembic environment configuration."""
from logging.config import fileConfig
from sqlalchemy import engine_from_config, pool
from alembic import context
import os
import sys

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from nanobio_studio.app.db.base import Base
from nanobio_studio.app.core.config import settings

# this is the Alembic Config object
config = context.config

# Interpret the config file for Python logging
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# set the sqlalchemy.url in the alembic.ini file
config.set_main_option("sqlalchemy.url", settings.database_url)

# model's MetaData object for 'autogenerate' support
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(url=url, target_metadata=target_metadata, literal_binds=True)

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    configuration = config.get_section(config.config_ini_section)
    configuration["sqlalchemy.url"] = settings.database_url

    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
'''
    return content


def create_alembic_script_py():
    """Create alembic/script.py.mako."""
    content = '''"""${message}

Revision ID: ${up_revision}
Revises: ${down_revision | comma,n}
Create Date: ${create_date}

"""
from alembic import op
import sqlalchemy as sa
${imports if imports else ""}

# revision identifiers, used by Alembic.
revision = ${repr(up_revision)}
down_revision = ${repr(down_revision)}
branch_labels = ${repr(branch_labels)}
depends_on = ${repr(depends_on)}


def upgrade() -> None:
    ${upgrades if upgrades else "pass"}


def downgrade() -> None:
    ${downgrades if downgrades else "pass"}
'''
    return content


if __name__ == "__main__":
    # Generate files
    print("Setup Alembic configuration files")
