import pickle
from pathlib import Path
import pandas as pd
from sqlalchemy import create_engine
from sklearn.preprocessing import StandardScaler
from src.utils.config import get_config

print("=" * 60)
print("FIXING MODELS - ADDING SCALER")
print("=" * 60)

config = get_config()
engine = create_engine(config.database.connection_string)

# Feature columns
FEATURE_COLS = [
    'rolling_avg_points_5r', 'rolling_avg_finish_pos_5r', 'rolling_points_trend',
    'recent_form_points', 'recent_form_finish_pos', 'recent_form_quali_pos',
    'constructor_avg_points_5r', 'constructor_reliability_score',
    'track_avg_points', 'track_avg_finish_pos', 'track_best_finish_pos', 'track_experience_races',
    'lap_consistency_std', 'avg_lap_time_ms', 'fastest_lap_time_ms',
    'dnf_probability', 'consecutive_finishes', 'mechanical_dnf_rate',
    'quali_position', 'quali_gap_to_pole_ms', 'grid_position_gain_potential',
    'wet_race_experience', 'wet_race_avg_points',
    'driver_performance_index', 'constructor_performance_index',
    'starting_position'
]

# Create scaler from training data
print("\nCreating scaler from training data...")
train_data = pd.read_sql(f"SELECT {', '.join(FEATURE_COLS)} FROM driver_race_features LIMIT 5000", engine)
train_data = train_data.fillna(0)
scaler = StandardScaler()
scaler.fit(train_data)
print("✅ Scaler created")

# Update models in artifacts/models
model_dir = Path("artifacts/models")
if not model_dir.exists():
    print(f"❌ Model directory not found: {model_dir}")
    exit()

print(f"\nUpdating models in {model_dir}...")

for model_file in model_dir.glob("*.pkl"):
    print(f"  Processing {model_file.name}...")
    
    # Load model
    with open(model_file, 'rb') as f:
        bundle = pickle.load(f)
    
    # Add scaler if missing
    if 'scaler' not in bundle:
        bundle['scaler'] = scaler
        print(f"    ✅ Added scaler")
    else:
        print(f"    ⏭️ Scaler already present")
    
    # Save back
    with open(model_file, 'wb') as f:
        pickle.dump(bundle, f)
    
    print(f"    ✅ Saved")

print("\n✅ All models updated successfully!")
