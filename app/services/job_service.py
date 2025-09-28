import logging
from datetime import datetime, timezone
from typing import List, Optional
from pathlib import Path
from sqlalchemy.orm import Session
from langchain_community.vectorstores import FAISS
from sentence_transformers import SentenceTransformer, CrossEncoder, InputExample, losses
from torch.utils.data import DataLoader

from app.core.errors import AppException, ErrorCode
from app.core.config import get_config
from app.managers.index_cache_manager import index_cache
from app.db.session import SessionLocal
from app.repositories.taxonomy import TaxonomyRepository
from app.repositories.taxonomy_entry import TaxonomyEntryRepository
from app.repositories.feedback import FeedbackRepository
from app.repositories.embedder import EmbedderRepository
from app.repositories.reranker import RerankerRepository
from app.managers.jobs_manager import JobsManager

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

        jobs.update(job_id, status="completed", done=done, total=total)
        logger.info("Index build completed", extra={"job_id": job_id, "taxonomy": taxonomy, "indexed": done, "path": str(out_dir)})
        return vs

    except Exception:
        logger.error("Index build failed", extra={"job_id": job_id, "taxonomy": taxonomy}, exc_info=True)
        jobs.update(job_id, status="failed", error="Unexpected error during indexing")
        return None
    finally:
        db.close()


def finetune_embedder_async(job_id, embedder_id, date_from, date_to, jobs: JobsManager) -> None:
    config = get_config()
    db: Session = SessionLocal()
    try:
        embedder_repo = EmbedderRepository(db)
        feedback_repo = FeedbackRepository(db)
        
        # Retrieve the target embedder from the repository
        target_embedder = embedder_repo.get(embedder_id)
        if not target_embedder or not Path(target_embedder.path).exists():
            raise AppException(ErrorCode.NOT_FOUND, "Embedder not found or path missing", status_code=404)
        
        # Retrieve feedback within the specified date range
        feedbacks = feedback_repo.list_filtered(taxonomy_id=None, date_from=date_from, date_to=date_to, pagination=False)
        
        # Prepare positive feedback pairs directly for training
        train_examples = [
            InputExample(texts=[r.query, r.reference], label=1.0)
            for r in feedbacks if r.is_correct
        ]

        if not train_examples:
            jobs.update(job_id, status="failed", error="No positive feedback pairs for embedder training.")
            return "No positive feedback pairs for embedder training."
        
        # Load the existing model for fine-tuning
        model = SentenceTransformer(target_embedder.path, device=config.DEVICE)
        
        # Create DataLoader for training
        train_dataloader = DataLoader(train_examples, shuffle=True, batch_size=16)
        
        # Define the loss function for training
        train_loss = losses.MultipleNegativesRankingLoss(model)

        # Train the model
        logger.info(f"Finetuning started for embedder {embedder_id}", extra={"job_id": job_id})
        
        model.fit(
            train_objectives=[(train_dataloader, train_loss)],
            epochs=5,
            warmup_steps=10,
            show_progress_bar=True,
        )
        
        version = f'v_{datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S%f")}'
                
        # Create save path and save the model
        save_path = config.model_path / "finetuned_embedder" / version
        save_path.mkdir(parents=True, exist_ok=True)
        model.save(save_path)
        
        # Update the embedder repository with the new finetuned embedder
        embedder_repo.create(
            name=f"brisk_bold_embedder_{version}",
            version=version,
            path=str(save_path),
            is_active=True
        )
        
        # Commit the changes to the database
        db.commit()
        
        # Successfully completed finetuning
        jobs.update(job_id, status="completed", done=len(train_examples), total=len(feedbacks))
        logger.info(f"Finetuning completed for embedder {embedder_id}", extra={"job_id": job_id})
        
    except AppException as e:
        logger.error(f"Finetuning failed for embedder {embedder_id}", exc_info=True, extra={"job_id": job_id})
        jobs.update(job_id, status="failed", error=str(e))
    except Exception as e:
        logger.error(f"Unexpected error during finetuning for embedder {embedder_id}", exc_info=True, extra={"job_id": job_id})
        jobs.update(job_id, status="failed", error="Unexpected error during finetuning")
    finally:
        db.close()


def finetune_reranker_async(job_id, reranker_id, date_from, date_to, jobs: JobsManager) -> None:
    config = get_config()
    db: Session = SessionLocal()
    try:
        reranker_repo = RerankerRepository(db)
        feedback_repo = FeedbackRepository(db)
        
        # Retrieve the target reranker from the repository
        target_reranker = reranker_repo.get(reranker_id)
        if not target_reranker or not Path(target_reranker.path).exists():
            raise AppException(ErrorCode.NOT_FOUND, "Reranker not found or path missing", status_code=404)
        
        # Retrieve feedback within the specified date range
        feedbacks = feedback_repo.list_filtered(taxonomy_id=None, date_from=date_from, date_to=date_to, pagination=False)
        
        # Prepare training pairs with both positive and negative feedback pairs
        train_examples = [
            InputExample(texts=[r.query, r.reference], label=1.0)  # Positive pairs (label = 1)
            for r in feedbacks if r.is_correct
        ]
        train_examples += [
            InputExample(texts=[r.query, r.reference], label=0.0)  # Negative pairs (label = 0)
            for r in feedbacks if not r.is_correct
        ]
        
        if not train_examples:
            jobs.update(job_id, status="failed", error="No feedback pairs for reranker training.")
            return "No feedback pairs for reranker training."
        
        # Load the existing CrossEncoder model for finetuning
        model = CrossEncoder(target_reranker.path, num_labels=1, device=config.DEVICE)
        
        # Create DataLoader for training
        train_dataloader = DataLoader(train_examples, shuffle=True, batch_size=16)
        
        # Train the model with the provided data
        logger.info(f"Finetuning started for reranker {reranker_id}", extra={"job_id": job_id})
        
        model.fit(
            train_dataloader=train_dataloader,
            epochs=5,
            warmup_steps=10,
            show_progress_bar=True,
        )
        
        # Generate a unique version using the current timestamp
        version = f'v_{datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S%f")}'
        
        # Create save path and save the model
        save_path = config.model_path / "finetuned_reranker" / version
        save_path.mkdir(parents=True, exist_ok=True)
        model.save(save_path)
        
        # Update the reranker repository with the new finetuned reranker
        reranker_repo.create(
            name=f"brisk_bold_reranker_{version}",
            version=version,
            path=str(save_path),
            normalize_method="softmax",
            is_active=True
        )
        
        # Commit the changes to the database
        db.commit()
        
        # Successfully completed finetuning
        jobs.update(job_id, status="completed", done=len(train_examples), total=len(feedbacks))
        logger.info(f"Finetuning completed for reranker {reranker_id}", extra={"job_id": job_id})
        
    except AppException as e:
        logger.error(f"Finetuning failed for reranker {reranker_id}", exc_info=True, extra={"job_id": job_id})
        jobs.update(job_id, status="failed", error=str(e))
    except Exception as e:
        logger.error(f"Unexpected error during finetuning for reranker {reranker_id}", exc_info=True, extra={"job_id": job_id})
        jobs.update(job_id, status="failed", error="Unexpected error during finetuning")
    finally:
        db.close()
