# Model evaluation and comparison
import json
import pickle
from pathlib import Path
from typing import Any, Dict, List, Optional

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from sklearn.metrics import (
    precision_recall_curve, roc_curve, confusion_matrix
)

from src.utils.config import get_config
from src.utils.io_utils import get_io
from src.utils.logger import get_logger

logger = get_logger(__name__)

class ModelEvaluator:
   
    def __init__(self):
        self.config = get_config()
        self.model_dir = Path(self.config.ml.model_dir)
        self.metrics_dir = Path(self.config.ml.metrics_dir)
    
    def load_model(self, model_path: str) -> Dict[str, Any]:
        with open(model_path, 'rb') as f:
            return pickle.load(f)
    
    def load_metrics(self, metrics_path: str) -> Dict[str, Any]:
        with open(metrics_path, 'r') as f:
            return json.load(f)
    
    def compare_models(self, target: str) -> pd.DataFrame:
       
        comparisons = []
        
        for metrics_file in self.metrics_dir.glob(f"*_{target}_*.json"):
            metrics = self.load_metrics(str(metrics_file))
            
            comparisons.append({
                'model': metrics_file.stem.split('_')[0],
                'target': target,
                'accuracy': metrics.get('accuracy', 0),
                'precision': metrics.get('precision', 0),
                'recall': metrics.get('recall', 0),
                'f1_score': metrics.get('f1_score', 0),
                'roc_auc': metrics.get('roc_auc', None)
            })
        
        df = pd.DataFrame(comparisons)
        logger.info("model_comparison_generated", target=target, models=len(df))
        return df
    
    def plot_confusion_matrix(
        self,
        y_true: np.ndarray,
        y_pred: np.ndarray,
        title: str = "Confusion Matrix"
    ) -> plt.Figure:
        cm = confusion_matrix(y_true, y_pred)
        
        fig, ax = plt.subplots(figsize=(8, 6))
        sns.heatmap(
            cm,
            annot=True,
            fmt='d',
            cmap='Blues',
            xticklabels=['Not Winner', 'Winner'],
            yticklabels=['Not Winner', 'Winner'],
            ax=ax
        )
        ax.set_title(title)
        ax.set_ylabel('True Label')
        ax.set_xlabel('Predicted Label')
        
        return fig
    
    def plot_roc_curve(
        self,
        y_true: np.ndarray,
        y_prob: np.ndarray,
        title: str = "ROC Curve"
    ) -> plt.Figure:
        fpr, tpr, _ = roc_curve(y_true, y_prob)
        
        fig, ax = plt.subplots(figsize=(8, 6))
        ax.plot(fpr, tpr, linewidth=2)
        ax.plot([0, 1], [0, 1], 'k--', linewidth=1)
        ax.set_xlim([0.0, 1.0])
        ax.set_ylim([0.0, 1.05])
        ax.set_xlabel('False Positive Rate')
        ax.set_ylabel('True Positive Rate')
        ax.set_title(title)
        ax.grid(True, alpha=0.3)
        
        return fig
    
    def plot_feature_importance(
        self,
        importance: Dict[str, float],
        title: str = "Feature Importance",
        top_n: int = 15
    ) -> plt.Figure:
        sorted_imp = dict(sorted(importance.items(), key=lambda x: x[1], reverse=True)[:top_n])
        
        fig, ax = plt.subplots(figsize=(10, 8))
        y_pos = np.arange(len(sorted_imp))
        
        ax.barh(y_pos, list(sorted_imp.values()), align='center')
        ax.set_yticks(y_pos)
        ax.set_yticklabels(list(sorted_imp.keys()))
        ax.invert_yaxis()
        ax.set_xlabel('Importance')
        ax.set_title(title)
        
        return fig
    
    def threshold_analysis(
        self,
        y_true: np.ndarray,
        y_prob: np.ndarray
    ) -> pd.DataFrame:
        
        precision, recall, thresholds = precision_recall_curve(y_true, y_prob)
        f1_scores = 2 * (precision * recall) / (precision + recall + 1e-10)
        
        results = []
        for i, threshold in enumerate(thresholds):
            results.append({
                'threshold': round(threshold, 3),
                'precision': round(precision[i], 3),
                'recall': round(recall[i], 3),
                'f1_score': round(f1_scores[i], 3)
            })
        
        df = pd.DataFrame(results)
        optimal = df.loc[df['f1_score'].idxmax()]
        
        logger.info(
            "threshold_analysis_complete",
            optimal_threshold=optimal['threshold'],
            optimal_f1=optimal['f1_score']
        )
        
        return df
    
    def generate_evaluation_report(
        self,
        model_paths: Dict[str, str],
        output_path: Optional[str] = None
    ) -> str:
       
        report_lines = [
            "# F1 Race Prediction — Model Evaluation Report\n",
            f"Generated: {pd.Timestamp.now(tz='UTC').isoformat()}\n",
            "## Model Comparison\n"
        ]
        
        for target in ['is_winner', 'is_top3']:
            report_lines.append(f"\n### Target: {target}\n")
            
            comparison = self.compare_models(target)
            if not comparison.empty:
                report_lines.append(comparison.to_markdown(index=False))
                report_lines.append("\n")
                
                best_model = comparison.loc[comparison['f1_score'].idxmax()]
                report_lines.append(
                    f"**Best Model:** {best_model['model']} "
                    f"(F1: {best_model['f1_score']:.3f})\n"
                )
        
        report = "\n".join(report_lines)
        
        if output_path:
            Path(output_path).write_text(report)
            logger.info("evaluation_report_saved", path=output_path)
        
        return report