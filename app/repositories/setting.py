from typing import Optional
from .base import BaseRepository
from app.models.entities import Setting


class SettingRepository(BaseRepository):
    def get_current(self) -> Optional[Setting]:
        return (
            self.db.query(Setting)
            .order_by(Setting.updated_at.desc())
            .limit(1)
            .one_or_none()
        )

    def set_active(self, embedder_id: int | None, reranker_id: int | None) -> Setting:
        setting = Setting(active_embedder_id=embedder_id, active_reranker_id=reranker_id)
        return self.add(setting)
