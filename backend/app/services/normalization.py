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
    def normalize_skills(skills: List) -> List[str]:
        if not skills:
            return []
            
        aliases = {
            "js": "javascript",
            "ts": "typescript",
            "py": "python",
            "postgres": "postgresql",
            "aws": "amazon web services",
            "reactjs": "react",
            "vuejs": "vue",
            "nodejs": "node"
        }
        
        cleaned = []
        def _process_item(item):
            if isinstance(item, (list, tuple)):
                for sub in item:
                    _process_item(sub)
            elif isinstance(item, str):
                s_clean = item.strip().lower()
                if s_clean:
                    cleaned.append(aliases.get(s_clean, s_clean))
            elif item is not None:
                s_clean = str(item).strip().lower()
                if s_clean:
                    cleaned.append(aliases.get(s_clean, s_clean))

        _process_item(skills)
        return list(set(cleaned))

    @staticmethod
    def extract_experience_years(title: str = "", description: str = "") -> float | None:
        """
        Parses title and text to estimate required experience years if not provided.
        """
        t_low = title.lower()
        d_low = description.lower()[:1000]

        # Explicit regex matches like "3-5 years" or "2+ yrs"
        match = re.search(r'(\d+)\s*(?:\+|\-|to)?\s*(\d+)?\s*(?:years?|yrs?|yr)\b', d_low + " " + t_low)
        if match:
            try:
                val = float(match.group(1))
                return val
            except Exception:
                pass

        # Title keyword heuristics for level / seniority
        if any(w in t_low for w in ["fresher", "graduate", "junior", "jr.", "jr ", "intern", "entry level", "trainee", "associate engineer"]):
            return 0.5
        if re.search(r'\b(?:iii|iv|v|level 3|level 4|l3|l4|l5|sr\.?|senior|lead|principal|staff|architect|head of|director|manager)\b', t_low):
            return 5.0
        if re.search(r'\b(?:ii|level 2|l2)\b', t_low):
            return 3.0

        return None

    @staticmethod
    def is_job_relevant(
        title: str,
        query: str = "",
        max_exp: float | None = None,
        min_exp: float | None = None,
        job_exp: float | None = None
    ) -> bool:
        """
        Deterministic, fast relevance filter:
        - Excludes senior/lead/level II/level III titles when max_exp <= 2.0 (entry level/fresher).
        - Excludes completely unrelated roles (billing, hr, sales, infanteer, etc.) when tech query is specified.
        """
        t_low = title.lower().strip()
        q_low = query.lower().strip()

        # Seniority / Level exclusion for entry level / fresher filter (max_exp <= 2)
        if max_exp is not None and max_exp <= 2.0:
            if re.search(r'\b(?:iii|ii|iv|v|l2|l3|l4|level 2|level 3|sr\.?|senior|lead|principal|staff|architect|head of|director|manager|vp)\b', t_low):
                return False
            if job_exp is not None and job_exp > 2.5:
                return False


        # Tech query relevance filter
        tech_keywords = ["software", "developer", "engineer", "backend", "frontend", "fullstack", "python", "react", "java", "node", "web", "data", "cloud", "devops"]
        is_tech_query = any(k in q_low for k in tech_keywords)

        if is_tech_query:
            unrelated_titles = [
                "billing", "hr", "human resources", "sales", "marketing", "editor",
                "infanteer", "maintenance planner", "flight attendant", "receptionist",
                "nurse", "accountant", "driver", "cleaner", "housekeeper", "cook", "chef"
            ]
            if any(unrel in t_low for unrel in unrelated_titles):
                return False

        return True


