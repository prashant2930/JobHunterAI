from abc import ABC, abstractmethod
from typing import List, Dict, Optional

class BaseJobSource(ABC):
    """
    Provider-neutral interface for external job discovery.
    Ensures consistent signatures for search queries.
    """
    
    @abstractmethod
    async def search_jobs(
        self, 
        query: str, 
        location: Optional[str] = None, 
        remote: Optional[str] = None, 
        page: int = 1, 
        limit: int = 10
    ) -> List[Dict]:
        """
        Search external job board and returns a list of raw job dictionaries.
        """
        pass
