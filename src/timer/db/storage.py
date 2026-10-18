from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine


class SQLAlchemyStorage:
    def __init__(self, url: str) -> None:
        self.engine = create_async_engine(url)
        self.sessionmaker = async_sessionmaker(self.engine, expire_on_commit=False)

    def create_session(self) -> AsyncSession:
        return self.sessionmaker()

    async def close_connection(self) -> None:
        await self.engine.dispose()
