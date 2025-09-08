import logging
from typing import List, Optional
from pathlib import Path
from sqlalchemy.orm import Session
from langchain_community.vectorstores import FAISS

from app.core.config import get_config
from app.core.index_cache import index_cache
from app.db.session import SessionLocal
from app.repositories.taxonomy import TaxonomyRepository
from app.repositories.taxonomy_entry import TaxonomyEntryRepository
from app.jobs.manager import JobsManager


logger = logging.getLogger(__name__)


def build_index_async(job_id: str, taxonomy: str, registry, jobs: JobsManager) -> Optional[FAISS]:
    config = get_config()
    db: Session = SessionLocal()
    try:
        logger.info("Index build started", extra={"job_id": job_id, "taxonomy": taxonomy})

        tax_repo = TaxonomyRepository(db)
        entry_repo = TaxonomyEntryRepository(db)

        t = tax_repo.get_by_taxonomy(taxonomy)
        if not t:
            logger.warning("Taxonomy not found", extra={"job_id": job_id, "taxonomy": taxonomy})
            jobs.update(job_id, status="failed", error=f"Taxonomy '{taxonomy}' not found")
            return None

        total = entry_repo.count_by_taxonomy(t.id)
        if total == 0:
            logger.warning("No entries found for taxonomy", extra={"job_id": job_id, "taxonomy": taxonomy})
            jobs.update(job_id, status="failed", error=f"No entries found for taxonomy '{taxonomy}'")
            return None

        BATCH = 200
        jobs.update(job_id, status="running", total=total, done=0, progress=0)
        logger.info("Index build running", extra={"job_id": job_id, "taxonomy": taxonomy, "total": total, "batch": BATCH})

        done = 0
        vs: Optional[FAISS] = None
        offset = 0

        while True:
            entries = entry_repo.list_by_taxonomy(t.id, offset=offset, limit=BATCH)
            if not entries:
                break

            texts: List[str] = []
            metas: List[dict] = []
            for e in entries:
                # texts.append(f"{e.tag} {e.reference or ''}".strip())
                texts.append(f"{e.reference or ''}".strip())
                metas.append({
                    "tag": e.tag,
                    "datatype": e.datatype or "",
                    "reference": e.reference or "",
                    "taxonomy": taxonomy
                })

            vectors = registry.embedder.embed_documents(texts)
            batch_index = FAISS.from_embeddings(
                text_embeddings=list(zip(texts, vectors)),
                embedding=registry.embedder,
                metadatas=metas,
            )
            if vs is None:
                vs = batch_index
            else:
                vs.merge_from(batch_index)

            done += len(entries)
            offset += len(entries)
            jobs.update(job_id, done=done, progress=int(done * 100 / total))

        if vs is None:
            logger.warning("No documents were indexed", extra={"job_id": job_id, "taxonomy": taxonomy})
            jobs.update(job_id, status="failed", error="No documents were indexed")
            return None

        out_dir = Path(config.index_path) / taxonomy
        out_dir.mkdir(parents=True, exist_ok=True)
        vs.save_local(str(out_dir))
        index_cache.set(taxonomy, vs)

        jobs.update(job_id, status="completed")
        logger.info("Index build completed", extra={"job_id": job_id, "taxonomy": taxonomy, "indexed": done, "path": str(out_dir)})
        return vs

    except Exception:
        logger.error("Index build failed", extra={"job_id": job_id, "taxonomy": taxonomy}, exc_info=True)
        jobs.update(job_id, status="failed", error="Unexpected error during indexing")
        return None
    finally:
        db.close()
