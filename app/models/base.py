from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Dict, List, Optional, TypeVar, Generic
from bson import ObjectId

T = TypeVar('T', bound=Dict[str, Any])


class BaseModel(ABC):
    def __init__(self, mongo_db, collection_name: str):
        self.db = mongo_db
        self.collection = mongo_db[collection_name]
        self._indexes_created = False
    
    def ensure_indexes(self) -> None:
        if not self._indexes_created:
            self._create_indexes()
            self._indexes_created = True
    
    @abstractmethod
    def _create_indexes(self) -> None:
        pass
    
    def _get_utc_now(self) -> datetime:
        return datetime.utcnow()
    
    def _to_object_id(self, id_str: str) -> Optional[ObjectId]:
        try:
            return ObjectId(id_str)
        except Exception:
            return None
    
    def _format_datetime(self, dt: Optional[datetime]) -> Optional[str]:
        if dt and isinstance(dt, datetime):
            return dt.isoformat() + 'Z'
        return None
    
    def _format_document(self, doc: Optional[Dict], 
                         id_field: str = 'id',
                         datetime_fields: Optional[List[str]] = None) -> Optional[Dict]:
        if not doc:
            return None
        
        formatted = doc.copy()
        
        # Convert ObjectId to string
        if '_id' in formatted:
            formatted[id_field] = str(formatted.pop('_id'))
        
        # Format datetime fields
        if datetime_fields:
            for field in datetime_fields:
                if field in formatted and formatted[field]:
                    formatted[field] = self._format_datetime(formatted[field])
        
        return formatted
    
    def find_one_by_id(self, doc_id: str, id_field: str = '_id') -> Optional[Dict]:
        try:
            if id_field == '_id':
                query = {'_id': self._to_object_id(doc_id)}
            else:
                query = {id_field: doc_id}
            return self.collection.find_one(query)
        except Exception:
            return None
    
    def count_documents(self, query: Dict) -> int:
        return self.collection.count_documents(query)


class OperationResult:
    __slots__ = ('success', 'data', 'error', 'error_code')
    
    def __init__(self, success: bool, data: Any = None, 
                 error: Optional[str] = None, error_code: Optional[str] = None):
        self.success = success
        self.data = data
        self.error = error
        self.error_code = error_code
    
    def to_dict(self) -> Dict[str, Any]:
        result = {'success': self.success}
        if self.data is not None:
            result['data'] = self.data
        if self.error:
            result['error'] = self.error
        if self.error_code:
            result['error_code'] = self.error_code
        return result
    
    @classmethod
    def ok(cls, data: Any = None) -> 'OperationResult':
        return cls(success=True, data=data)
    
    @classmethod
    def fail(cls, error: str, error_code: str = 'error') -> 'OperationResult':
        return cls(success=False, error=error, error_code=error_code)
