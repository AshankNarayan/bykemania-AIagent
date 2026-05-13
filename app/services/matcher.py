# app/services/matcher.py
from typing import Optional
import pandas as pd
from rapidfuzz import process, fuzz


class Matcher:
    def __init__(self):
        try:
            # IMPORTANT: Using semicolon separator
            self.models_df = pd.read_csv(
                "app/data/models.csv",
                sep=";",           # ← This is the key fix
                quoting=1,
                on_bad_lines='skip',
                encoding='utf-8'
            )
            
            self.locations_df = pd.read_csv(
                "app/data/locations.csv",
                sep=";",           # ← This is the key fix
                quoting=1,
                on_bad_lines='skip',
                encoding='utf-8'
            )
            
            print(f"✅ Matcher: Loaded {len(self.models_df)} models and {len(self.locations_df)} locations")
            print(f"   Models columns: {list(self.models_df.columns)}")
            print(f"   Locations columns: {list(self.locations_df.columns)}")
            
        except Exception as e:
            print(f"⚠️ Matcher: CSV loading failed - {e}")
            self.models_df = pd.DataFrame()
            self.locations_df = pd.DataFrame()

    def match_model(self, model_name: str) -> Optional[int]:
        if self.models_df.empty or not model_name:
            return None

        # Clean column names (remove quotes if any)
        self.models_df.columns = [col.strip('"') for col in self.models_df.columns]

        model_col = "name"          # From your CSV structure
        id_col = "model_id"

        if model_col not in self.models_df.columns:
            print(f"⚠️ Model column '{model_col}' not found. Available: {list(self.models_df.columns)}")
            return None

        choices = self.models_df[model_col].astype(str).tolist()
        
        result = process.extractOne(model_name, choices, scorer=fuzz.partial_ratio)
        
        if result and result[1] > 65:
            matched_name = result[0]
            row = self.models_df[self.models_df[model_col] == matched_name].iloc[0]
            
            try:
                model_id = row[id_col]
                # Sometimes model_id is like "model_11"
                if isinstance(model_id, str) and model_id.startswith("model_"):
                    model_id = model_id.replace("model_", "")
                return int(model_id)
            except:
                return None
        return None

    def match_location(self, location_name: str) -> Optional[int]:
        if self.locations_df.empty or not location_name:
            return None

        self.locations_df.columns = [col.strip('"') for col in self.locations_df.columns]

        loc_col = "l_name"          # From your CSV
        id_col = "location_id"

        if loc_col not in self.locations_df.columns:
            print(f"⚠️ Location column '{loc_col}' not found.")
            return None

        choices = self.locations_df[loc_col].astype(str).tolist()
        
        result = process.extractOne(location_name, choices, scorer=fuzz.partial_ratio)
        
        if result and result[1] > 65:
            matched_name = result[0]
            row = self.locations_df[self.locations_df[loc_col] == matched_name].iloc[0]
            
            try:
                return int(row[id_col])
            except:
                return None
        return None


# Quick test
if __name__ == "__main__":
    matcher = Matcher()
    print("\n--- Test Matches ---")
    print("Model match:", matcher.match_model("Activa"))
    print("Location match:", matcher.match_location("Koramangala"))