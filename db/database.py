from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.exc import IntegrityError
from fastapi import HTTPException

DATABASE_URL = "postgresql+psycopg2://sadcfreightlinkdb_owner:GMdNaWop7m0t@ep-curly-dust-a2hm4g9c.eu-central-1.aws.neon.tech/sadcfreightlinkdb?sslmode=require"  # Replace with your database URL

engine = create_engine(
    DATABASE_URL,
    connect_args={
        "sslmode": "require",
        "connect_timeout": 10, # Disable excessive SQL echo logging in production
    },
    echo=False
)

# Intercept queries
def before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
    print("Executing SQL Statement: ", statement)
    print("With Parameters: ", parameters)

# Attach the event listener
event.listen(engine, "before_cursor_execute", before_cursor_execute)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine, info={})
Base = declarative_base()

def handle_database_commit(db):
    try:
        db.commit()
    except IntegrityError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail="A database constraint was violated. Check input for uniqueness.")