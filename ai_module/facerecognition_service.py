import numpy as np
import logging
from typing import List, Optional, Tuple, Union

try:
    from insightface.app import FaceAnalysis
except ImportError:
    FaceAnalysis = None  # type: ignore

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class FaceRecognitionService:
    """
    A flexible, production-ready class for InsightFace operations.
    Supports multiple models, CPU/GPU execution, and comprehensive error handling.
    """
    
    _instance = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super(FaceRecognitionService, cls).__new__(cls)
        return cls._instance

    def __init__(self,
                 model_name: str = "buffalo_sc",
                 provider: str = "CPU",
                 det_size: Tuple[int, int] = (640, 640),
                 ctx_id: int = 0):
        """
        Initialize the Face Recognition service.
        
        Args:
            model_name: InsightFace model name ('buffalo_sc', 'buffalo_l', etc.)
            provider: 'CPU' or 'GPU'
            det_size: Detection size as (width, height)
            ctx_id: GPU context ID (for GPU provider)
        """
        
        # Avoid reinitialization
        if hasattr(self, "initialized") and self.initialized:
            logger.info("FaceRecognitionService already initialized")
            return

        if FaceAnalysis is None:
            logger.warning("insightface is not installed. Face recognition features will be unavailable.")
            logger.warning("Install it with: pip install insightface")
            self.app = None
            self.initialized = False
            return

        self.model_name = model_name
        self.provider = provider.upper()
        self.det_size = det_size
        self.ctx_id = ctx_id
        
        # Configure providers
        if self.provider == "GPU":
            self.providers = ["CUDAExecutionProvider"]
        else:
            self.providers = ["CPUExecutionProvider"]

        try:
            logger.info(f"Loading model {model_name} with {self.provider} provider")
            
            self.app = FaceAnalysis(
                name=model_name,
                providers=self.providers
            )
            self.app.prepare(ctx_id=ctx_id, det_size=det_size)
            
            self.initialized = True
            logger.info("FaceRecognitionService initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize FaceRecognitionService: {e}")
            self.app = None
            self.initialized = False
            raise

    def detect_faces(self, image: np.ndarray) -> List:
        """Detect all faces in the image."""
        if not hasattr(self, 'app') or self.app is None:
            logger.warning("FaceRecognitionService not initialized. Install insightface to use face recognition.")
            return []
        try:
            faces = self.app.get(image)
            logger.debug(f"Detected {len(faces)} faces")
            return faces
        except Exception as e:
            logger.error(f"Error in face detection: {e}")
            return []

    def get_embedding(self, image: np.ndarray, face_index: int = 0) -> Optional[np.ndarray]:
        """Get embedding for a single face from the image."""
        faces = self.detect_faces(image)
        
        if not faces or len(faces) <= face_index:
            return None
        
        return faces[face_index].embedding

    def compute_similarity(self, embedding1: np.ndarray, embedding2: np.ndarray) -> float:
        """Compute cosine similarity between two embeddings."""
        # Ensure embeddings are normalized
        norm1 = np.linalg.norm(embedding1)
        norm2 = np.linalg.norm(embedding2)
        
        if norm1 == 0 or norm2 == 0:
            return 0.0
            
        return float(np.dot(embedding1, embedding2) / (norm1 * norm2))

    def get_embeddings_multi(self, image: np.ndarray) -> List[np.ndarray]:
        """Get embeddings for all faces in the image."""
        faces = self.detect_faces(image)
        embeddings = [face.embedding for face in faces]
        logger.debug(f"Extracted {len(embeddings)} embeddings")
        return embeddings

    def get_detailed_faces(self, image: np.ndarray) -> List[dict]:
        """Get detailed information for all detected faces."""
        faces = self.detect_faces(image)
        detailed_faces = []
        
        for i, face in enumerate(faces):
            face_info = {
                'index': i,
                'embedding': face.embedding,
                'bbox': face.bbox,
                'landmarks': face.kps if hasattr(face, 'kps') else None,
                'det_score': face.det_score,
                'gender': face.sex if hasattr(face, 'sex') else None,
                'age': face.age if hasattr(face, 'age') else None
            }
            detailed_faces.append(face_info)
            
        return detailed_faces

    @staticmethod
    def cosine_similarity(emb1: np.ndarray, emb2: np.ndarray) -> float:
        """Compute cosine similarity between two embeddings."""
        try:
            emb1 = np.array(emb1).flatten()
            emb2 = np.array(emb2).flatten()
            
            if emb1.shape != emb2.shape:
                raise ValueError(f"Embedding shape mismatch: {emb1.shape} vs {emb2.shape}")
                
            similarity = np.dot(emb1, emb2) / (np.linalg.norm(emb1) * np.linalg.norm(emb2))
            return float(similarity)
            
        except Exception as e:
            logger.error(f"Error computing cosine similarity: {e}")
            return 0.0

    def match_face(self, query_embedding: np.ndarray, 
                   db_embeddings: List[np.ndarray], 
                   threshold: float = 0.6) -> Tuple[Optional[int], float]:
        """Find the best matching face from database embeddings."""
        if not db_embeddings:
            return None, 0.0
            
        best_similarity = -1.0
        best_index = None
        
        for i, db_emb in enumerate(db_embeddings):
            similarity = self.cosine_similarity(query_embedding, db_emb)
            
            if similarity > best_similarity and similarity >= threshold:
                best_similarity = similarity
                best_index = i
                
        return best_index, best_similarity

    def get_model_info(self) -> dict:
        """Get information about the loaded model."""
        return {
            'model_name': self.model_name,
            'provider': self.provider,
            'detection_size': self.det_size,
            'initialized': self.initialized
        }

