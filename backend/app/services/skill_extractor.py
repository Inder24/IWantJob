"""
NLP service for extracting skills, job titles, and entities from resume text
"""
import spacy
import re
from typing import List, Set, Dict, Any


class SkillExtractionService:
    """Service for extracting skills and entities using NLP"""
    
    def __init__(self):
        # Load spaCy model
        try:
            self.nlp = spacy.load("en_core_web_sm")
        except OSError:
            print("spaCy model not found. Please run: python -m spacy download en_core_web_sm")
            self.nlp = None
        
        # Tech skills database (expanded list)
        self.tech_skills = {
            # Programming Languages
            "python", "java", "javascript", "typescript", "c++", "c#", "ruby", "go", "golang",
            "rust", "swift", "kotlin", "scala", "r", "matlab", "perl", "php", "shell", "bash",
            
            # Web Technologies
            "html", "css", "react", "angular", "vue", "vue.js", "next.js", "nuxt.js", "svelte",
            "jquery", "bootstrap", "tailwind", "sass", "less", "webpack", "vite",
            
            # Backend Frameworks
            "django", "flask", "fastapi", "express", "express.js", "node.js", "spring", "spring boot",
            "laravel", "rails", "ruby on rails", "asp.net", ".net", "gin",
            
            # Databases
            "sql", "mysql", "postgresql", "postgres", "mongodb", "redis", "cassandra", 
            "dynamodb", "elasticsearch", "neo4j", "sqlite", "oracle", "mssql",
            
            # Cloud & DevOps
            "aws", "azure", "gcp", "google cloud", "docker", "kubernetes", "k8s", "terraform",
            "ansible", "jenkins", "gitlab", "github actions", "circleci", "travis ci",
            
            # Data Science & ML
            "pandas", "numpy", "scikit-learn", "sklearn", "tensorflow", "pytorch", "keras",
            "jupyter", "matplotlib", "seaborn", "spark", "hadoop", "airflow",
            
            # Tools & Others
            "git", "linux", "unix", "api", "rest", "graphql", "microservices", "agile",
            "scrum", "jira", "confluence", "ci/cd", "testing", "unit testing", "pytest",
            "jest", "selenium", "postman", "nginx", "apache", "rabbitmq", "kafka"
        }
        
        # Soft skills database
        self.soft_skills = {
            "leadership", "communication", "teamwork", "problem-solving", "analytical",
            "critical thinking", "time management", "project management", "collaboration",
            "adaptability", "creativity", "innovation", "mentoring", "presentation",
            "negotiation", "decision-making", "strategic thinking", "attention to detail"
        }
        
        # Job titles patterns
        self.job_title_patterns = [
            r'\b(software|senior|junior|lead|principal|staff)\s+(engineer|developer|programmer)\b',
            r'\b(full[\s-]?stack|front[\s-]?end|back[\s-]?end|web)\s+(developer|engineer)\b',
            r'\b(data|machine learning|ml|ai)\s+(scientist|engineer)\b',
            r'\b(devops|site reliability|sre)\s+engineer\b',
            r'\b(product|project|program)\s+manager\b',
            r'\b(ux|ui|product)\s+designer\b',
            r'\b(qa|quality assurance|test)\s+engineer\b',
            r'\b(technical|team|engineering)\s+lead\b',
            r'\b(software|solutions|cloud|security)\s+architect\b'
        ]
    
    def extract_skills(self, text: str) -> Dict[str, List[str]]:
        """
        Extract tech and soft skills from text
        
        Args:
            text: Resume text
            
        Returns:
            Dict with tech_skills and soft_skills lists
        """
        text_lower = text.lower()
        
        # Extract tech skills
        found_tech_skills = set()
        for skill in self.tech_skills:
            # Use word boundaries for accurate matching
            pattern = r'\b' + re.escape(skill) + r'\b'
            if re.search(pattern, text_lower):
                found_tech_skills.add(skill)
        
        # Extract soft skills
        found_soft_skills = set()
        for skill in self.soft_skills:
            pattern = r'\b' + re.escape(skill) + r'\b'
            if re.search(pattern, text_lower):
                found_soft_skills.add(skill)
        
        # Keep skills canonical only (from curated dictionaries).
        # spaCy noun-chunk expansion produced noisy phrases like
        # "this reduced development effort" and "product,engineering and external partners".
        
        return {
            "tech_skills": self._order_by_appearance(list(found_tech_skills), text_lower),
            "soft_skills": self._order_by_appearance(list(found_soft_skills), text_lower)
        }

    def _order_by_appearance(self, skills: List[str], text_lower: str) -> List[str]:
        def first_index(skill: str) -> int:
            idx = text_lower.find(skill.lower())
            return idx if idx >= 0 else 10**9

        unique = sorted(set(skills), key=lambda s: (first_index(s), s))
        return unique
    
    def extract_job_titles(self, text: str) -> List[str]:
        """
        Extract job titles from text
        
        Args:
            text: Resume text
            
        Returns:
            List of job titles found
        """
        job_titles = []
        text_lower = text.lower()
        
        for pattern in self.job_title_patterns:
            matches = re.findall(pattern, text_lower, re.IGNORECASE)
            for match in matches:
                # match is a tuple from groups, join it
                if isinstance(match, tuple):
                    title = ' '.join(match)
                else:
                    title = match
                job_titles.append(title.title())
        
        # Remove duplicates while preserving order
        seen = set()
        unique_titles = []
        for title in job_titles:
            if title not in seen:
                seen.add(title)
                unique_titles.append(title)
        
        return unique_titles
    
    def extract_companies(self, text: str) -> List[str]:
        """
        Extract company names using NLP
        
        Args:
            text: Resume text
            
        Returns:
            List of company names
        """
        # 1) High-precision heuristic: parse employment timeline segments
        # Example segment:
        # "Mar 2025 - Jul 2025: Agency for Science, Technology Research (ASTAR), Singapore  S/w Dev Intern ..."
        heuristic_companies = []
        month = r'(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)'
        segment_pattern = (
            rf'{month}\s+\d{{4}}\s*-\s*(?:{month}\s+\d{{4}}|Present)'
            rf'\s*:\s*(.+?)(?=\s+{month}\s+\d{{4}}\s*-\s*(?:{month}\s+\d{{4}}|Present)|$)'
        )
        for segment in re.findall(segment_pattern, text, re.IGNORECASE):
            company_part = segment.strip()
            # Trim role/header tails
            company_part = re.split(
                r'\s+(?:Senior|Lead|Principal|Staff|S/w|Software|Engineer|Developer|Responsibilities|Major Highlights|Technology used)\b',
                company_part,
                maxsplit=1,
                flags=re.IGNORECASE,
            )[0]
            # Remove trailing location only (preserve inner commas in company names)
            city_country_patterns = [
                r',\s*Singapore\s*$',
                r',\s*India\s*$',
                r',\s*USA\s*$',
                r',\s*United States\s*$',
                r',\s*Canada\s*$',
                r',\s*UK\s*$',
                r',\s*Australia\s*$',
                r',\s*[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*,\s*(?:Singapore|India|USA|United States|Canada|UK|Australia)\s*$',
            ]
            for loc_pat in city_country_patterns:
                company_part = re.sub(loc_pat, '', company_part, flags=re.IGNORECASE)
            # If a trailing city remains, trim it only when left side clearly looks like a company name
            if re.search(r'\b(private limited|limited|corporation|corp|inc|llc|ltd|bank|technologies|technology|systems|solutions|agency)\b', company_part, re.IGNORECASE):
                company_part = re.sub(r',\s*[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\s*$', '', company_part)
            # Remove parenthetical acronyms
            company_part = re.sub(r'\s*\([^)]*\)\s*', '', company_part)
            company_part = re.sub(r'\s+', ' ', company_part).strip(" ,.-")
            if len(company_part) >= 3:
                heuristic_companies.append(company_part)

        # Deduplicate heuristic matches
        seen_h = set()
        ordered_h = []
        for c in heuristic_companies:
            k = c.lower()
            if k in seen_h:
                continue
            seen_h.add(k)
            ordered_h.append(c)
        if ordered_h:
            return ordered_h[:8]

        # 2) NLP fallback when date lines are not available
        if not self.nlp:
            return []
        
        # Focus on likely work-experience region first for better precision
        lower = text.lower()
        start = lower.find("work experience")
        if start == -1:
            start = lower.find("experience")
        scope_text = text[start:start + 5000] if start != -1 else text[:6000]

        doc = self.nlp(scope_text)
        companies = []
        blocked_exact = {
            "API", "AWS", "GCP", "OCI", "SCADA", "LangChain", "MCP",
            "REST", "ELK", "Kafka", "Spark", "Docker", "Kubernetes"
        }
        blocked_contains = {
            "highlights", "responsibilities", "technology used", "skills",
            "experience", "summary", "project", "engineering"
        }
        
        for ent in doc.ents:
            if ent.label_ == "ORG":
                # Filter out common false positives
                company_name = ent.text.strip()
                if (
                    len(company_name) > 2
                    and company_name.lower() not in ['llc', 'inc', 'ltd']
                    and company_name not in blocked_exact
                    and not any(token in company_name.lower() for token in blocked_contains)
                    and not re.fullmatch(r"[A-Z]{2,5}", company_name)
                ):
                    companies.append(company_name)
        
        # Remove duplicates while preserving order
        seen = set()
        ordered = []
        for c in companies:
            key = c.lower()
            if key in seen:
                continue
            seen.add(key)
            ordered.append(c)
        return ordered[:8]
    
    def extract_education_degrees(self, text: str) -> List[str]:
        """
        Extract education degrees
        
        Args:
            text: Resume text
            
        Returns:
            List of degrees
        """
        degrees = []
        
        degree_patterns = [
            r'\b(bachelor|b\.?s\.?|b\.?a\.?|b\.?tech|b\.?e\.?)\s+(of|in|of science|of arts)?\s*([a-z\s]+)\b',
            r'\b(master|m\.?s\.?|m\.?a\.?|m\.?tech|m\.?e\.?|mba)\s+(of|in|of science|of arts)?\s*([a-z\s]+)\b',
            r'\b(phd|ph\.?d\.?|doctorate)\s+(in|of)?\s*([a-z\s]+)\b',
            r'\b(associate|a\.?s\.?|a\.?a\.?)\s+(of|in|of science|of arts)?\s*([a-z\s]+)\b'
        ]
        
        text_lower = text.lower()
        for pattern in degree_patterns:
            matches = re.findall(pattern, text_lower)
            for match in matches:
                degree = ' '.join([part for part in match if part]).strip()
                if degree:
                    degrees.append(degree.title())
        
        return list(set(degrees))


# Global instance
skill_extractor = SkillExtractionService()
