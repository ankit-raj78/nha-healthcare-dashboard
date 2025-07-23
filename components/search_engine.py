"""
Natural Language Search Engine for Healthcare Facilities
"""

import pandas as pd
import numpy as np
import logging
from typing import Optional, List, Dict, Any
import re

logger = logging.getLogger(__name__)

try:
    from sentence_transformers import SentenceTransformer
    import faiss
    SEARCH_AVAILABLE = True
except ImportError:
    logger.warning("sentence-transformers or faiss not available. Search functionality will be limited.")
    SEARCH_AVAILABLE = False


class SearchEngine:
    """Natural language search engine for healthcare facilities"""
    
    def __init__(self, model_name: str = 'all-MiniLM-L6-v2'):
        """Initialize the search engine"""
        self.model = None
        self.index = None
        self.search_texts = []
        self.model_name = model_name
        self.initialized = False
        
    def initialize(self, df: pd.DataFrame) -> bool:
        """Initialize the search engine with facility data"""
        try:
            # Always use fallback search to avoid segmentation faults
            logger.info("Initializing text-based search engine for stability...")
            self.initialized = True
            return True
            
            # Disabled AI search due to stability issues
            # if not SEARCH_AVAILABLE:
            #     logger.warning("Advanced search not available. Using fallback search.")
            #     self.initialized = True
            #     return True
                
            # logger.info("Initializing semantic search engine...")
            
            # # Load sentence transformer model
            # self.model = SentenceTransformer(self.model_name)
            
            # # Create searchable text from facility information
            # self.search_texts = self._create_search_texts(df)
            
            # # Create embeddings
            # embeddings = self.model.encode(self.search_texts)
            
            # # Create FAISS index
            # dimension = embeddings.shape[1]
            # self.index = faiss.IndexFlatIP(dimension)  # Inner product for cosine similarity
            
            # # Normalize embeddings for cosine similarity
            # faiss.normalize_L2(embeddings)
            # self.index.add(embeddings.astype('float32'))
            
            # self.initialized = True
            # logger.info(f"Search engine initialized with {len(self.search_texts)} facility records")
            # return True
            
        except Exception as e:
            logger.error(f"Error initializing search engine: {e}")
            # Fall back to basic text search
            self.initialized = True
            return True
    
    def _create_search_texts(self, df: pd.DataFrame) -> List[str]:
        """Create searchable text representations of facilities"""
        search_texts = []
        
        for _, row in df.iterrows():
            text_parts = []
            
            # Add facility name
            if pd.notna(row.get('Name')):
                text_parts.append(str(row['Name']))
            
            # Add facility type
            if pd.notna(row.get('Facility Type')):
                text_parts.append(str(row['Facility Type']))
            
            # Add ownership
            if pd.notna(row.get('Ownership')):
                text_parts.append(str(row['Ownership']))
            
            # Add address
            if pd.notna(row.get('Address')):
                text_parts.append(str(row['Address']))
            
            # Add state if available
            if pd.notna(row.get('State')):
                text_parts.append(str(row['State']))
            
            # Add specialties if available
            if pd.notna(row.get('Specialties')):
                text_parts.append(str(row['Specialties']))
            
            # Add ABDM status if available
            if pd.notna(row.get('ABDM Enabled')):
                text_parts.append(f"ABDM {row['ABDM Enabled']}")
            
            search_text = ' '.join(text_parts)
            search_texts.append(search_text)
        
        return search_texts
    
    def search(self, query: str, df: pd.DataFrame, top_k: int = 500) -> pd.DataFrame:
        """Perform natural language search on the facilities"""
        if not query.strip():
            return df.head(100)  # Return sample if no query
        
        try:
            if not self.initialized:
                logger.warning("Search engine not initialized, using fallback search")
                return self._fallback_search(query, df)
            
            if not SEARCH_AVAILABLE or self.model is None:
                return self._fallback_search(query, df)
            
            # Encode the search query
            query_embedding = self.model.encode([query])
            faiss.normalize_L2(query_embedding)
            
            # Search the index
            scores, indices = self.index.search(
                query_embedding.astype('float32'), 
                min(top_k, len(df))
            )
            
            # Filter results by relevance threshold
            result_indices = indices[0]
            result_scores = scores[0]
            
            # Keep results with reasonable relevance scores
            valid_mask = result_scores > 0.2  # Adjust threshold as needed
            result_indices = result_indices[valid_mask]
            result_scores = result_scores[valid_mask]
            
            if len(result_indices) == 0:
                logger.info("No relevant results found, falling back to text search")
                return self._fallback_search(query, df)
            
            # Return matching facilities
            results_df = df.iloc[result_indices].copy()
            results_df['relevance_score'] = result_scores
            
            return results_df.sort_values('relevance_score', ascending=False)
            
        except Exception as e:
            logger.error(f"Error in semantic search: {e}")
            return self._fallback_search(query, df)
    
    def _fallback_search(self, query: str, df: pd.DataFrame) -> pd.DataFrame:
        """Fallback text-based search when semantic search is not available"""
        logger.info("Using fallback text search")
        
        # Clean and prepare query
        query_terms = query.lower().split()
        
        # Create search mask
        search_mask = pd.Series(False, index=df.index)
        
        # Search in multiple columns
        search_columns = ['Name', 'Facility Type', 'Ownership', 'Address']
        
        for column in search_columns:
            if column in df.columns:
                column_text = df[column].astype(str).str.lower()
                
                for term in query_terms:
                    search_mask |= column_text.str.contains(term, na=False, regex=False)
        
        # Apply additional logic for common search patterns
        search_mask = self._apply_search_patterns(query.lower(), df, search_mask)
        
        results = df[search_mask].copy()
        
        if len(results) == 0:
            logger.info("No results found in fallback search")
            return df.head(0)  # Return empty DataFrame
        
        logger.info(f"Fallback search found {len(results)} results")
        return results
    
    def _apply_search_patterns(self, query: str, df: pd.DataFrame, base_mask: pd.Series) -> pd.Series:
        """Apply specific search patterns for better results"""
        mask = base_mask.copy()
        
        # Government/public facilities
        if any(term in query for term in ['government', 'govt', 'public']):
            if 'Ownership' in df.columns:
                mask |= df['Ownership'].str.lower().str.contains('government', na=False)
        
        # Private facilities
        if 'private' in query:
            if 'Ownership' in df.columns:
                mask |= df['Ownership'].str.lower().str.contains('private', na=False)
        
        # Hospital types
        if 'hospital' in query:
            if 'Facility Type' in df.columns:
                mask |= df['Facility Type'].str.lower().str.contains('hospital', na=False)
        
        # Primary health centers
        if any(term in query for term in ['phc', 'primary health']):
            if 'Facility Type' in df.columns:
                mask |= df['Facility Type'].str.lower().str.contains('primary health', na=False)
        
        # Community health centers
        if any(term in query for term in ['chc', 'community health']):
            if 'Facility Type' in df.columns:
                mask |= df['Facility Type'].str.lower().str.contains('community health', na=False)
        
        # ABDM enabled
        if any(term in query for term in ['abdm', 'digital']):
            if 'ABDM Enabled' in df.columns:
                mask |= df['ABDM Enabled'].str.lower().str.contains('yes', na=False)
        
        return mask
    
    def get_search_suggestions(self, partial_query: str, df: pd.DataFrame) -> List[str]:
        """Get search suggestions based on partial query"""
        suggestions = []
        
        # Common facility types
        facility_types = df['Facility Type'].dropna().unique()
        for ft in facility_types:
            if partial_query.lower() in ft.lower():
                suggestions.append(ft)
        
        # Common ownership types
        ownership_types = df['Ownership'].dropna().unique()
        for ot in ownership_types:
            if partial_query.lower() in ot.lower():
                suggestions.append(f"{ot} facilities")
        
        # Add state-based suggestions if state column exists
        if 'State' in df.columns:
            states = df['State'].dropna().unique()
            for state in states:
                if partial_query.lower() in state.lower():
                    suggestions.append(f"facilities in {state}")
        
        return suggestions[:5]  # Return top 5 suggestions
