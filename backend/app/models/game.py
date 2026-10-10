from datetime import datetime, timezone

from sqlalchemy import ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

class Game(Base):
    __tablename__ = "games"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    max_turns: Mapped[int]
    status: Mapped[str] = mapped_column(String(20), default="active")  # active | finished
    created_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(timezone.utc))

    user: Mapped["User"] = relationship(back_populates="games")
    turns: Mapped[list["Turn"]] = relationship(
        back_populates="game", cascade="all, delete-orphan", order_by="Turn.number"
    )

class Turn(Base):
    __tablename__ = "turns"
    # Impede que duas ações enviadas ao mesmo tempo virem o mesmo turno
    __table_args__ = (UniqueConstraint("game_id", "number"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    game_id: Mapped[int] = mapped_column(ForeignKey("games.id"))
    number: Mapped[int]  # 0 = abertura da aventura
    action: Mapped[str | None] = mapped_column(Text)
    roll: Mapped[int | None]
    outcome: Mapped[str | None] = mapped_column(String(20))
    narration: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(timezone.utc))

    game: Mapped[Game] = relationship(back_populates="turns")
