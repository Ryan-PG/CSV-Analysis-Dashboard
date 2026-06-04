import io

import pandas as pd
import plotly.express as px
import streamlit as st


st.set_page_config(page_title="CSV Analysis Dashboard", page_icon="chart_with_upwards_trend", layout="wide")


def read_csv(uploaded_file: io.BytesIO) -> pd.DataFrame:
    """Read a CSV upload with a small fallback for common encoding issues."""
    try:
        return pd.read_csv(uploaded_file)
    except UnicodeDecodeError:
        uploaded_file.seek(0)
        return pd.read_csv(uploaded_file, encoding="latin-1")


def coerce_datetime_columns(df: pd.DataFrame) -> pd.DataFrame:
    result = df.copy()
    object_columns = result.select_dtypes(include=["object"]).columns

    for column in object_columns:
        sample = result[column].dropna().head(100)
        if sample.empty:
            continue

        parsed = pd.to_datetime(sample, errors="coerce")
        if parsed.notna().mean() >= 0.8:
            result[column] = pd.to_datetime(result[column], errors="coerce")

    return result


def show_overview(df: pd.DataFrame) -> None:
    rows, columns = df.shape
    missing_cells = int(df.isna().sum().sum())
    duplicate_rows = int(df.duplicated().sum())

    metric_cols = st.columns(4)
    metric_cols[0].metric("Rows", f"{rows:,}")
    metric_cols[1].metric("Columns", f"{columns:,}")
    metric_cols[2].metric("Missing cells", f"{missing_cells:,}")
    metric_cols[3].metric("Duplicate rows", f"{duplicate_rows:,}")

    st.subheader("Data Preview")
    st.dataframe(df.head(100), use_container_width=True)


def show_data_quality(df: pd.DataFrame) -> None:
    st.subheader("Data Quality")

    missing = (
        df.isna()
        .sum()
        .reset_index()
        .rename(columns={"index": "column", 0: "missing_count"})
    )
    missing["missing_percent"] = (missing["missing_count"] / len(df) * 100).round(2)
    missing = missing.sort_values("missing_count", ascending=False)

    left, right = st.columns([1, 1])
    with left:
        st.dataframe(missing, use_container_width=True, hide_index=True)

    with right:
        missing_with_values = missing[missing["missing_count"] > 0]
        if missing_with_values.empty:
            st.info("No missing values found.")
        else:
            fig = px.bar(
                missing_with_values,
                x="column",
                y="missing_count",
                title="Missing Values by Column",
                labels={"column": "Column", "missing_count": "Missing values"},
            )
            fig.update_layout(xaxis_tickangle=-35)
            st.plotly_chart(fig, use_container_width=True)


def show_numeric_analysis(df: pd.DataFrame) -> None:
    numeric_columns = df.select_dtypes(include="number").columns.tolist()

    st.subheader("Numeric Analysis")
    if not numeric_columns:
        st.info("No numeric columns found.")
        return

    st.dataframe(df[numeric_columns].describe().T, use_container_width=True)

    selected_column = st.selectbox(
        "Distribution column",
        numeric_columns,
        key="distribution_column",
    )

    fig = px.histogram(
        df,
        x=selected_column,
        marginal="box",
        title=f"Distribution of {selected_column}",
    )
    st.plotly_chart(fig, use_container_width=True)

    if len(numeric_columns) >= 2:
        corr = df[numeric_columns].corr(numeric_only=True)
        fig = px.imshow(
            corr,
            text_auto=".2f",
            aspect="auto",
            color_continuous_scale="RdBu_r",
            title="Correlation Heatmap",
            zmin=-1,
            zmax=1,
        )
        st.plotly_chart(fig, use_container_width=True)

        x_column = st.selectbox("Scatter X axis", numeric_columns, key="scatter_x")
        y_default = 1 if len(numeric_columns) > 1 else 0
        y_column = st.selectbox(
            "Scatter Y axis",
            numeric_columns,
            index=y_default,
            key="scatter_y",
        )

        fig = px.scatter(
            df,
            x=x_column,
            y=y_column,
            trendline="ols",
            title=f"{y_column} vs {x_column}",
        )
        st.plotly_chart(fig, use_container_width=True)


def show_categorical_analysis(df: pd.DataFrame) -> None:
    categorical_columns = df.select_dtypes(include=["object", "category", "bool"]).columns.tolist()

    st.subheader("Categorical Analysis")
    if not categorical_columns:
        st.info("No categorical columns found.")
        return

    selected_column = st.selectbox(
        "Category column",
        categorical_columns,
        key="category_column",
    )
    top_n = st.slider("Number of categories", min_value=5, max_value=30, value=10)

    counts = (
        df[selected_column]
        .astype("string")
        .fillna("Missing")
        .value_counts()
        .head(top_n)
        .reset_index()
    )
    counts.columns = [selected_column, "count"]

    fig = px.bar(
        counts,
        x=selected_column,
        y="count",
        title=f"Top {top_n} Values in {selected_column}",
        labels={selected_column: selected_column, "count": "Count"},
    )
    fig.update_layout(xaxis_tickangle=-35)
    st.plotly_chart(fig, use_container_width=True)


def show_time_analysis(df: pd.DataFrame) -> None:
    datetime_columns = df.select_dtypes(include=["datetime64[ns]", "datetimetz"]).columns.tolist()
    numeric_columns = df.select_dtypes(include="number").columns.tolist()

    st.subheader("Time Analysis")
    if not datetime_columns:
        st.info("No date/time columns detected.")
        return

    date_column = st.selectbox("Date column", datetime_columns, key="date_column")
    value_column = st.selectbox(
        "Value column",
        ["Row count"] + numeric_columns,
        key="time_value_column",
    )

    time_df = df.dropna(subset=[date_column]).copy()
    time_df["_period"] = time_df[date_column].dt.to_period("D").dt.to_timestamp()

    if value_column == "Row count":
        grouped = time_df.groupby("_period").size().reset_index(name="value")
        y_label = "Row count"
    else:
        grouped = time_df.groupby("_period")[value_column].mean().reset_index(name="value")
        y_label = f"Average {value_column}"

    fig = px.line(
        grouped,
        x="_period",
        y="value",
        markers=True,
        title=f"{y_label} Over Time",
        labels={"_period": "Date", "value": y_label},
    )
    st.plotly_chart(fig, use_container_width=True)


def main() -> None:
    st.title("CSV Analysis Dashboard")
    st.caption("Upload a CSV file to inspect structure, quality, distributions, correlations, categories, and time trends.")

    uploaded_file = st.file_uploader("Upload CSV", type=["csv"])
    if uploaded_file is None:
        st.info("Choose a CSV file to begin.")
        return

    try:
        df = read_csv(uploaded_file)
    except Exception as exc:
        st.error(f"Could not read the CSV file: {exc}")
        return

    if df.empty:
        st.warning("The uploaded CSV file is empty.")
        return

    df = coerce_datetime_columns(df)

    overview_tab, quality_tab, numeric_tab, category_tab, time_tab = st.tabs(
        ["Overview", "Quality", "Numeric", "Categories", "Time"]
    )

    with overview_tab:
        show_overview(df)

    with quality_tab:
        show_data_quality(df)

    with numeric_tab:
        show_numeric_analysis(df)

    with category_tab:
        show_categorical_analysis(df)

    with time_tab:
        show_time_analysis(df)


if __name__ == "__main__":
    main()
