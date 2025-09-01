from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from worker.database import Base
from worker.database import Instrument


def get_all_instruments(db: Session):
    return db.scalars(select(Instrument)).all()


def insert_list_of_dicts(items: list[dict], table: type[Base], session: Session):
    chunk_size = 1000
    total_inserted = 0

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
                f"Chunk {i // chunk_size + 1}: Inserted {chunk_inserted}/{len(chunk)} rows into {table.__name__} (Total: {total_inserted})"
            )

        except Exception as e:
            print(f"Error inserting chunk {i // chunk_size + 1}: {e}")
            session.rollback()
