import pandas as pd
import streamlit as st
import plotly.express as px

# Streamlit page configuration
st.set_page_config(page_title="✈️ Excel Flight Dashboard", layout="wide")

# File uploader
uploaded_file = st.sidebar.file_uploader("📁 Upload Excel File", type=["xlsx", "xls"])

if uploaded_file:
    try:
        df = pd.read_excel(uploaded_file)

        # Clean and convert date
        df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
        df.dropna(subset=["Date"], inplace=True)

        # Add Year and Month for filtering
        df["Year"] = df["Date"].dt.year
        df["Month"] = df["Date"].dt.month
        df["Month_Name"] = df["Date"].dt.strftime("%B")

        # Fix and convert numeric columns
        numeric_cols = ["Total Price", "Commission", "No Passengers"]
        for col in numeric_cols:
            if col in df.columns:
                df[col] = df[col].replace(["NaN", "nan", "NAN", "Null", "NULL", "", " "], pd.NA)
                non_numeric = df[~df[col].astype(str).str.replace('.', '', 1).str.replace('-', '', 1).str.isnumeric()][col]
                if not non_numeric.empty:
                    st.sidebar.warning(f"⚠️ Non-numeric values in `{col}` found and converted.")
                    st.sidebar.write(non_numeric.unique())
                df[col] = pd.to_numeric(df[col], errors="coerce")

        # Safe integer conversion (if needed)
        if "No Passengers" in df.columns:
            df["No Passengers"] = df["No Passengers"].fillna(0).astype(int)

        # Sidebar Filters
        st.sidebar.header("🔎 Filter by Date Range")
        min_date, max_date = df["Date"].min(), df["Date"].max()
        start_date = st.sidebar.date_input("Start Date", min_value=min_date, max_value=max_date, value=min_date)
        end_date = st.sidebar.date_input("End Date", min_value=min_date, max_value=max_date, value=max_date)

        # Filter by selected date range
        filtered_df = df[(df["Date"] >= pd.to_datetime(start_date)) & (df["Date"] <= pd.to_datetime(end_date))]

        # Filter out "No Tickets"
        ticketed_df = filtered_df[filtered_df["Ticket Numbers"].str.lower() != "no tickets"]

        # Drop rows with missing price or commission
        ticketed_df = ticketed_df.dropna(subset=["Total Price", "Commission"])

        # Dashboard Title
        st.title("✈️ Flight Booking Dashboard")
        st.markdown("## 📊 Key Metrics")

        col1, col2, col3 = st.columns(3)
        col1.metric("📦 Total Bookings", f"{len(filtered_df):,}")
        col2.metric("🎟️ Total Ticketed", f"{ticketed_df['No Passengers'].sum():,}")
        col3.metric("💰 Max Ticket Price (ETB)", f"{ticketed_df['Total Price'].max():,.0f}")

        with st.expander("💸 Sales Vs Commission", expanded=False):
            col4, col5, col6 = st.columns(3)
            col4.metric("💸 Total Commission (ETB)", f"{ticketed_df['Commission'].sum():,.0f}")
            col5.metric("💵 Total Sales (ETB)", f"{ticketed_df['Total Price'].sum():,.0f}")
            col6.metric("🎫 Avg. Ticket Price (ETB)", f"{ticketed_df['Total Price'].mean():,.0f}")

        # Pie chart by Type
        st.subheader("🌍 Route Type: Domestic vs International")
        fig_type = px.pie(ticketed_df, names="Type", title="Flight Type Distribution", hole=0.4,
                          color_discrete_sequence=px.colors.qualitative.Set2)
        fig_type.update_traces(textinfo="percent+label")
        st.plotly_chart(fig_type, use_container_width=True)

        st.subheader("💰 Commission by Route Type")
        type_commission = (
            ticketed_df.dropna(subset=["Type"])
            .groupby("Type")["Commission"]
            .sum()
            .reset_index()
            .sort_values("Commission", ascending=False)
        )
        fig_commission_type = px.bar(
            type_commission,
            x="Type",
            y="Commission",
            title="💳 Total Commission by Flight Type",
            labels={"Type": "Flight Type", "Commission": "Total Commission (ETB)"},
            color="Commission",
            color_continuous_scale="Blues"
        )
        fig_commission_type.update_traces(texttemplate='%{y:,.0f}', textposition='outside')
        fig_commission_type.update_layout(yaxis_title="Commission (ETB)", xaxis_title="Flight Type")
        st.plotly_chart(fig_commission_type, use_container_width=True)

        # Top 10 Destinations
        st.subheader("🏁 Top 10 Destinations by Ticket Sells ")
        top_dests = (
            ticketed_df.groupby("To")["Total Price"]
            .sum()
            .sort_values(ascending=False)
            .head(10)
            .reset_index()
        )
        fig_dest = px.bar(
            top_dests,
            x="To",
            y="Total Price",
            title="Top Destinations by Total Price",
            labels={"To": "Destination", "Total Price": "Total Price (ETB)"},
            color="Total Price",
            color_continuous_scale="viridis"
        )
        st.plotly_chart(fig_dest, use_container_width=True)

        # Commission by Payment Method
        st.subheader("🏦 Commission by Bank")
        bank_df = (
            ticketed_df.groupby("Payment Method")["Commission"]
            .sum()
            .reset_index()
            .sort_values("Commission", ascending=False)
            .head(10)
        )
        fig_bank = px.bar(
            bank_df,
            x="Payment Method",
            y="Commission",
            title="Top Banks by Commission",
            color="Commission",
            color_continuous_scale="Plasma"
        )
        st.plotly_chart(fig_bank, use_container_width=True)

        # Payment method distribution
        st.subheader("🏦 Payment Method Distribution")
        payment_counts = ticketed_df["Payment Method"].value_counts().reset_index()
        payment_counts.columns = ["Payment Method", "Count"]
        fig_payment = px.pie(
            payment_counts,
            names="Payment Method",
            values="Count",
            hole=0.4,
            title="Most Used Payment Methods",
            color_discrete_sequence=px.colors.qualitative.Pastel
        )
        fig_payment.update_traces(textinfo="percent+label")
        st.plotly_chart(fig_payment, use_container_width=True)

        # Ticket Price Range Distribution
        st.subheader("🎯 Ticket Price Distribution by Fixed Ranges")
        price_df = ticketed_df.copy()
        bins = [0, 5000, 10000, 15000, 20000, 30000, 40000, 60000, 100000, float("inf")]
        labels = ["0–5K", "5K–10K", "10K–15K", "15K–20K", "20K–30K", "30K–40K", "40K–60K", "60K–100K", "100K+"]
        price_df["Fixed Price Range"] = pd.cut(price_df["Total Price"], bins=bins, labels=labels, right=False)

        range_counts = (
            price_df.groupby("Fixed Price Range")
            .agg(
                Ticket_Count=("Fixed Price Range", "count"),
                Total_Commission=("Commission", "sum"),
                Avg_Ticket_Price=("Total Price", "mean")
            )
            .reset_index()
        )

        fig_fixed = px.bar(
            range_counts,
            x="Fixed Price Range",
            y="Ticket_Count",
            text="Ticket_Count",
            color="Fixed Price Range",
            title="🎫 Ticket Count by Price Range (Fixed Intervals)",
            labels={"Ticket_Count": "Number of Tickets"},
            color_discrete_sequence=px.colors.qualitative.Safe
        )
        fig_fixed.update_traces(textposition='outside')
        fig_fixed.update_layout(xaxis_title="Price Range", yaxis_title="Tickets", xaxis_tickangle=-45)
        st.plotly_chart(fig_fixed, use_container_width=True)

    except Exception as e:
        st.error(f"🚨 An error occurred while processing the file:\n\n{e}")

else:
    st.warning("📤 Please upload an Excel file to begin.")
