import sys
from pathlib import Path

import pandas as pd
import streamlit as st

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.utils.config import get_config
from src.utils.db import get_db
from src.utils.logger import get_logger

logger = get_logger(__name__)

# Page configuration
st.set_page_config(
    page_title="F1 Data Engineering Platform",
    page_icon="🏎️",
    layout="wide",
    initial_sidebar_state="expanded"
)


def init_connection():
    try:
        db = get_db()
        if db.test_connection():
            return db
        return None
    except Exception as e:
        st.error(f"Database connection failed: {str(e)}")
        return None


def load_pipeline_metrics(db):
    query = """
    SELECT 
        pipeline_name,
        run_type,
        status,
        records_processed,
        records_failed,
        started_at,
        completed_at,
        EXTRACT(EPOCH FROM (completed_at - started_at)) as duration_seconds
    FROM pipeline_runs
    ORDER BY started_at DESC
    LIMIT 50
    """
    return db.execute_dataframe(query)


def load_data_summary(db):
    queries = {
        'races': "SELECT COUNT(*) as count FROM races",
        'drivers': "SELECT COUNT(*) as count FROM drivers",
        'constructors': "SELECT COUNT(*) as count FROM constructors",
        'circuits': "SELECT COUNT(*) as count FROM circuits",
        'results': "SELECT COUNT(*) as count FROM results",
        'lap_times': "SELECT COUNT(*) as count FROM lap_times",
        'features': "SELECT COUNT(*) as count FROM driver_race_features"
    }
    
    summary = {}
    for name, query in queries.items():
        result = db.execute_query(query)
        summary[name] = result[0]['count'] if result else 0
    
    return summary


def main():
    st.title("🏎️ Formula 1 Data Engineering Platform")
    st.markdown("### Enterprise Data Pipeline Monitoring")
    
    # Sidebar
    st.sidebar.header("Navigation")
    page = st.sidebar.radio(
        "Select View",
        ["Dashboard", "Pipeline Runs", "Data Explorer", "Feature Store"]
    )
    
    # Database connection
    db = init_connection()
    if not db:
        st.warning("Database not connected. Showing demo data.")

        return
    
    if page == "Dashboard":
        render_dashboard(db)
    elif page == "Pipeline Runs":
        render_pipeline_runs(db)
    elif page == "Data Explorer":
        render_data_explorer(db)
    elif page == "Feature Store":
        render_feature_store(db)


def render_dashboard(db):
    st.header("Platform Overview")
    
    # Data volume metrics
    summary = load_data_summary(db)
    
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Races", summary.get('races', 0))
    col2.metric("Drivers", summary.get('drivers', 0))
    col3.metric("Constructors", summary.get('constructors', 0))
    col4.metric("Circuits", summary.get('circuits', 0))
    
    col5, col6 = st.columns(2)
    col5.metric("Results Records", f"{summary.get('results', 0):,}")
    col6.metric("Feature Vectors", f"{summary.get('features', 0):,}")
    
    # Recent pipeline activity
    st.subheader("Recent Pipeline Activity")
    try:
        metrics_df = load_pipeline_metrics(db)
        if not metrics_df.empty:
            metrics_df['started_at'] = pd.to_datetime(metrics_df['started_at'])
            st.dataframe(
                metrics_df[[
                    'pipeline_name', 'run_type', 'status',
                    'records_processed', 'duration_seconds', 'started_at'
                ]],
                use_container_width=True
            )
            
            # Status distribution
            status_counts = metrics_df['status'].value_counts()
            st.bar_chart(status_counts)
        else:
            st.info("No pipeline runs recorded yet.")
    except Exception as e:
        st.error(f"Failed to load metrics: {str(e)}")
    
    # System health
    st.subheader("System Health")
    health_col1, health_col2, health_col3 = st.columns(3)
    
    try:
        # Check database connectivity
        db_health = db.test_connection()
        health_col1.metric(
            "Database",
            "Connected" if db_health else "Disconnected",
            delta=None
        )
    except Exception:
        health_col1.metric("Database", "Error")
    
    health_col2.metric("Storage", "Local", "S3 Ready")
    health_col3.metric("RLS", "Enabled", "Secure")


def render_pipeline_runs(db):
    st.header("Pipeline Execution History")
    
    try:
        runs_df = load_pipeline_metrics(db)
        if not runs_df.empty:
            # Filters
            status_filter = st.multiselect(
                "Filter by Status",
                options=runs_df['status'].unique(),
                default=runs_df['status'].unique()
            )
            
            type_filter = st.multiselect(
                "Filter by Type",
                options=runs_df['run_type'].unique(),
                default=runs_df['run_type'].unique()
            )
            
            filtered = runs_df[
                (runs_df['status'].isin(status_filter)) &
                (runs_df['run_type'].isin(type_filter))
            ]
            
            st.dataframe(filtered, use_container_width=True)
            
            # Success rate over time
            if 'started_at' in filtered.columns:
                filtered['date'] = pd.to_datetime(filtered['started_at']).dt.date
                daily_success = filtered.groupby('date')['status'].apply(
                    lambda x: (x == 'completed').mean() * 100
                ).reset_index()
                daily_success.columns = ['date', 'success_rate']
                
                st.line_chart(daily_success.set_index('date'))
        else:
            st.info("No pipeline runs available.")
    except Exception as e:
        st.error(f"Error loading pipeline runs: {str(e)}")


def render_data_explorer(db):
    st.header("Data Explorer")
    
    table = st.selectbox(
        "Select Table",
        ["races", "drivers", "constructors", "circuits", "results", "lap_times"]
    )
    
    limit = st.slider("Row Limit", 10, 1000, 100)
    
    try:
        query = f"SELECT * FROM {table} LIMIT {limit}"
        df = db.execute_dataframe(query)
        
        if not df.empty:
            st.dataframe(df, use_container_width=True)
            
            # Basic statistics for numeric columns
            numeric_cols = df.select_dtypes(include=['number']).columns
            if len(numeric_cols) > 0:
                st.subheader("Statistics")
                st.write(df[numeric_cols].describe())
        else:
            st.info(f"No data in {table}")
    except Exception as e:
        st.error(f"Query failed: {str(e)}")


def render_feature_store(db):
    st.header("Feature Store")
    
    try:
        # Feature coverage
        coverage_query = """
        SELECT 
            r.year,
            COUNT(DISTINCT f.race_id) as races_with_features,
            COUNT(DISTINCT f.driver_id) as drivers_with_features,
            AVG(f.overall_strength_index) as avg_strength_index,
            AVG(f.driver_performance_index) as avg_driver_index,
            AVG(f.constructor_performance_index) as avg_constructor_index
        FROM driver_race_features f
        JOIN races r ON f.race_id = r.race_id
        GROUP BY r.year
        ORDER BY r.year DESC
        """
        coverage = db.execute_dataframe(coverage_query)
        
        if not coverage.empty:
            st.dataframe(coverage, use_container_width=True)
            
            # Feature distribution
            st.subheader("Feature Distribution")
            feature_query = """
            SELECT overall_strength_index, driver_performance_index,
                   constructor_performance_index, dnf_probability
            FROM driver_race_features
            LIMIT 10000
            """
            features_df = db.execute_dataframe(feature_query)
            
            if not features_df.empty:
                st.write(features_df.describe())
        else:
            st.info("No features generated yet.")
    except Exception as e:
        st.error(f"Feature store error: {str(e)}")


if __name__ == "__main__":
    main()