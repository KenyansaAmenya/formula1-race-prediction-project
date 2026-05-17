from src.models.train import F1ModelTrainer
import pickle
from pathlib import Path
import shutil

# Clear old models
if Path('artifacts/models').exists():
    shutil.rmtree('artifacts/models')
Path('artifacts/models').mkdir(parents=True)

print('Training with debug...')
trainer = F1ModelTrainer()

# Override save_model temporarily to debug
original_save = trainer.save_model

def debug_save(model, model_name, target, metrics):
    print(f'  Saving {model_name}_{target}')
    print(f'    Model type: {type(model)}')
    print(f'    Has predict: {hasattr(model, "predict")}')
    return original_save(model, model_name, target, metrics)

trainer.save_model = debug_save

results = trainer.train_all_models(years=[2020, 2021, 2022, 2023, 2024, 2025])

print('\n' + '='*60)
print('Checking saved files:')
for f in Path('artifacts/models').glob('*.pkl'):
    with open(f, 'rb') as file:
        data = pickle.load(file)
    print(f'{f.name}: {type(data)}')
    if isinstance(data, dict):
        print(f'  Keys: {list(data.keys())}')
        if 'model' in data:
            print(f'  model type: {type(data["model"])}')
            print(f'  model has predict: {hasattr(data["model"], "predict")}')
