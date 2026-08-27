"""
Intent Extraction Engine (Agent 1 + Python Deterministic Matcher with Entity Masking).
"""

import json
import re
from dataclasses import dataclass
from typing import Dict, List, Optional
import ollama

from core.prompts.extractor_prompts import (
    AGENT_1_SYSTEM_PROMPT,
    get_agent_1_schema,
)
from database.ro_executor import execute_ro_query


@dataclass(frozen=True)
class IntentPayload:
    """Immutable data container for combined classification output."""
    reasoning: str
    matched_accounts: List[str]
    matched_categories: List[str]
    matched_methods: List[str]
    matched_projects: List[str]
    matched_streams: List[str]
    unmapped_search_terms: List[str]


class IntentExtractor:
    """Manages master data caching, Python exact matching, and Agent 1 masked extraction."""
    # Deterministic Kill-List for terms we NEVER want to send to the Vector DB
    STOP_WORDS = {
        "money", "spend", "spending", "spent", "cost", "costs", "pay", "paid",
        "account", "accounts", "purchase", "purchases", "expense", "expenses",
        "balance", "balances", "year", "month", "week", "weekend", "today",
        "yesterday", "amount", "total", "much", "more", "less", "highest", "lowest"
    }

    def __init__(self, model_name: str = "qwen2.5-coder:7b") -> None:
        self.model_name = model_name
        self._master_data_cache: Optional[Dict[str, List[str]]] = None

    def _fetch_master_data(self) -> Dict[str, List[str]]:
        if self._master_data_cache is not None:
            return self._master_data_cache

        def _get_list(table_name: str) -> List[str]:
            query = f"SELECT name FROM {table_name} WHERE active_bool = 1 ORDER BY name ASC;"
            return [row["name"] for row in execute_ro_query(query)]

        master_data = {
            "accounts": _get_list("accounts"),
            "categories": _get_list("categories"),
            "payment_methods": _get_list("payment_methods"),
            "projects": _get_list("projects"),
            "streams": _get_list("streams"),
        }
        self._master_data_cache = master_data
        return master_data
    @staticmethod
    def _python_exact_match(user_query: str, active_list: List[str]) -> List[str]:
        """Lightning-fast deterministic exact matching using safe boundaries."""
        matches = []
        query_lower = user_query.lower()
        sorted_list = sorted(active_list, key=len, reverse=True)
        for item in sorted_list:
            pattern = r'(?<!\w)' + re.escape(item.lower()) + r'(?!\w)'
            if re.search(pattern, query_lower):
                matches.append(item)
                query_lower = re.sub(pattern, '', query_lower)
        return matches

    def extract_intent(self, user_query: str) -> IntentPayload:
        master_data = self._fetch_master_data()

        # 1. PYTHON DETERMINISTIC PASS
        matched_accounts = self._python_exact_match(user_query, master_data["accounts"])
        matched_categories = self._python_exact_match(user_query, master_data["categories"])
        matched_methods = self._python_exact_match(user_query, master_data["payment_methods"])
        matched_projects = self._python_exact_match(user_query, master_data["projects"])
        matched_streams = self._python_exact_match(user_query, master_data["streams"])

        all_python_matches = (
                matched_accounts + matched_categories + matched_methods +
                matched_projects + matched_streams
        )

        # 2. ENTITY MASKING
        masked_query = user_query
        for match in sorted(all_python_matches, key=len, reverse=True):
            pattern = re.compile(r'(?<!\w)' + re.escape(match) + r'(?!\w)', re.IGNORECASE)
            masked_query = pattern.sub('__MAPPED__', masked_query)

        print("\n" + "-" * 40)
        print("[DEBUG] Pipeline Intercept:")
        print(f"  -> Original : {user_query}")
        print(f"  -> Matches  : {all_python_matches if all_python_matches else 'None'}")
        print(f"  -> Masked   : {masked_query}")
        print("-" * 40)

        # 3. LLM FUZZY PASS
        schema = get_agent_1_schema()
        response = ollama.chat(
            model=self.model_name,
            messages=[
                {"role": "system", "content": AGENT_1_SYSTEM_PROMPT},
                {"role": "user", "content": masked_query},
            ],
            format=schema,
            options={"temperature": 0.0},
        )

        content = json.loads(response["message"]["content"])

        # 4. THE ULTIMATE BOUNCER
        raw_terms = content.get("unmapped_search_terms", [])
        cleaned_terms = []
        for term in raw_terms:
            term_clean = term.strip().lower()
            if "__mapped__" in term_clean or term_clean in self.STOP_WORDS:
                continue
            cleaned_terms.append(term)

        # 5. MERGE AND RETURN
        return IntentPayload(
            reasoning=content.get("reasoning", ""),
            matched_accounts=matched_accounts,
            matched_categories=matched_categories,
            matched_methods=matched_methods,
            matched_projects=matched_projects,
            matched_streams=matched_streams,
            unmapped_search_terms=cleaned_terms,
        )