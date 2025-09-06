from typing import List
from tqdm import tqdm
from langchain.schema import Document
from langchain_community.vectorstores import FAISS
from app.jobs.manager import job_set, job_update
from app.core.config import get_config
from app.core.index_cache import index_cache


def build_index_async(job_id: str, docs: List[Document], embeddings, taxonomy: str) -> FAISS:
    if not docs:
        raise ValueError("No documents provided for indexing")
    
    config = get_config()
    texts = [d.page_content for d in docs]
    metas = [d.metadata for d in docs]
    vectors = []
    total = len(docs)
    
    # Initialize job tracking
    job_set(job_id, {
        "status": "running", 
        "progress": 0, 
        "total": total, 
        "done": 0,
        "taxonomy": taxonomy
    })
    
    # Generate embeddings with progress tracking
    try:
        for i, doc in enumerate(tqdm(docs, desc=f"Embedding {taxonomy} docs")):
            vec = embeddings.embed_documents([doc.page_content])[0]
            vectors.append(vec)
            job_update(job_id, done=i + 1, progress=int(((i + 1) / total) * 100))
        
        # Create FAISS index
        vs = FAISS.from_embeddings(
            text_embeddings=list(zip(texts, vectors)),
            embedding=embeddings,
            metadatas=metas,
        )
        
        # Save to disk
        vs.save_local(f"{config.index_path}/{taxonomy}")
        
        index_cache.set(taxonomy, vs)
        
        job_update(job_id, status="completed")
        return vs
        
    except Exception as e:
        job_update(job_id, status="failed", error=str(e))
        raise