import re
from typing import List

class JobNormalizationService:
    """
    Service to normalize job attributes (titles, companies, locations, skills)
    for index matching and comparison.
    Does NOT replace original source values.
    """
    
    @staticmethod
    def normalize_company(company: str) -> str:
        """
        Trims company suffixes (LLC, Inc, Corp, Ltd, etc.) and punctuation.
        """
        if not company:
            return ""
        c = company.lower().strip()
        # Strip common legal suffixes
        c = re.sub(r'\b(llc|inc|incorporated|corporation|corp|ltd|co|limited)\b\.?', '', c)
        # Remove punctuation except spaces
        c = re.sub(r'[^\w\s]', '', c)
        # Collapse multiple spaces
        return " ".join(c.split())

    @staticmethod
    def normalize_title(title: str) -> str:
        """
        Standardizes titles by lowercasing and removing punctuation.
        Preserves qualifiers like II, Senior, Jr., Lead.
        """
        if not title:
            return ""
        t = title.lower().strip()
        # Remove punctuation except dashes
        t = re.sub(r'[^\w\s\-]', '', t)
        # Collapse duplicate whitespace
        return " ".join(t.split())

    @staticmethod
    def normalize_location(location: str) -> str:
        """
        Standardizes locations. Trims whitespace and captures remote markers.
        """
        if not location:
            return "unspecified"
        loc = location.lower().strip()
        
        # Check if the location string is a known remote phrase
        remote_phrases = ["remote", "anywhere", "wfh", "work from home", "worldwide", "virtual"]
        if any(phrase in loc for phrase in remote_phrases):
            return "remote"
            
        loc = re.sub(r'[^\w\s,]', '', loc)
        return " ".join(loc.split())

    @staticmethod
    def normalize_skills(skills: List[str]) -> List[str]:
        """
        Resolves skill aliases to standard terms (e.g. JS -> JavaScript, Postgres -> PostgreSQL).
        """
        aliases = {
            "js": "javascript",
            "ts": "typescript",
            "postgres": "postgresql",
            "aws": "amazon web services",
            "reactjs": "react",
            "vuejs": "vue",
            "nodejs": "node"
        }
        
        cleaned = []
        for s in skills:
            s_clean = s.strip().lower()
            if s_clean in aliases:
                cleaned.append(aliases[s_clean])
            else:
                cleaned.append(s_clean)
        return list(set(cleaned))
