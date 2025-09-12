from sqlalchemy import Table
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from worker.database import Base
from worker.database import instruments


def get_all_instruments(db: Session):
    return db.scalars(select(instruments)).all()


def insert_list_of_dicts(items: list[dict], table: type[Base] | Table, session: Session):
    chunk_size = 1000
    total_inserted = 0

    if isinstance(table, Table):
        table_name = table.name
    else:
        table_name = table.__name__

    for i in range(0, len(items), chunk_size):
        chunk = items[i : i + chunk_size]

        try:
            stmt = insert(table).values(chunk)
            stmt = stmt.on_conflict_do_nothing()
            result = session.execute(stmt)
            session.commit()

            chunk_inserted = result.rowcount
            total_inserted += chunk_inserted

            print(
                f"Chunk {i // chunk_size + 1}: Inserted {chunk_inserted}/{len(chunk)} rows into {table_name} (Total: {total_inserted})"
            )

        except Exception as e:
            print(f"Error inserting chunk {i // chunk_size + 1}: {e}")
            session.rollback()
