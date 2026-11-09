"""Initialize tables and apply the supported additive upgrades at app startup."""

from sqlalchemy import inspect, literal
from sqlalchemy.schema import CreateColumn

from .database import Base
from .models import Item, WorkSession


# Keep the upgrade scope explicit; types and defaults come from the model.
ADDITIVE_ITEM_COLUMNS = (
    "priority", "estimated_minutes", "tiny_action", "if_then_plan", "subtasks", "duplicate_of_id",
)


def initialize_schema(engine):
    with engine.begin() as connection:
        Base.metadata.create_all(bind=connection)
        existing = {column["name"] for column in inspect(connection).get_columns(Item.__tablename__)}
        table = connection.dialect.identifier_preparer.quote(Item.__tablename__)
        for name in ADDITIVE_ITEM_COLUMNS:
            if name in existing:
                continue
            column = Item.__table__.c[name]
            definition = str(CreateColumn(column).compile(dialect=connection.dialect))
            if not column.nullable and column.server_default is None:
                if column.default is None or not column.default.is_scalar:
                    raise RuntimeError(f"A constant default is required to add {name} safely.")
                default = literal(column.default.arg, type_=column.type).compile(
                    dialect=connection.dialect, compile_kwargs={"literal_binds": True},
                )
                definition += f" DEFAULT {default}"
            connection.exec_driver_sql(f"ALTER TABLE {table} ADD COLUMN {definition}")
        # create_all does not add indexes to tables that already exist.
        for index in WorkSession.__table__.indexes:
            index.create(bind=connection, checkfirst=True)
