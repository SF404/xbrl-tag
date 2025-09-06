def _import_sentence_transformers():
    try:
        from sentence_transformers import SentenceTransformer, CrossEncoder
        return SentenceTransformer, CrossEncoder
    except Exception as e:
        raise RuntimeError(
            "sentence-transformers is required to load models. Install with `pip install sentence-transformers`."
        ) from e
    
class ModelDownloadService:
    def __init__(self):
        self.SentenceTransformer, self.CrossEncoder = _import_sentence_transformers()

    def download_embedder(self, model_name: str):
        try:
            print(f"[ModelDownloadService] Downloading embedder model: {model_name}")
            embedder = self.SentenceTransformer(model_name)
            print(f"[ModelDownloadService] Successfully loaded embedder model: {model_name}")
            return embedder
        except Exception as e:
            print(f"[ModelDownloadService] Error loading embedder model '{model_name}': {e}")
            return None

    def download_reranker(self, model_name: str):
        try:
            print(f"[ModelDownloadService] Downloading reranker model: {model_name}")
            reranker = self.CrossEncoder(model_name)
            print(f"[ModelDownloadService] Successfully loaded reranker model: {model_name}")
            return reranker
        except Exception as e:
            print(f"[ModelDownloadService] Error loading reranker model '{model_name}': {e}")
            return None