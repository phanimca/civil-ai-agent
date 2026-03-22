"""Admin reporting dashboard for user and LLM usage analytics"""
import streamlit as st
import pandas as pd
from io import BytesIO
import datetime
from typing import Optional


def render_admin_dashboard(repo, user):
    """Render the admin dashboard with user and LLM analytics"""

    if user["role"] != "admin":
        st.error("⛔ Access Denied. Admin access required.")
        return
    
    st.title("📊 Admin Dashboard")
    st.subheader("User & LLM Usage Analytics")
    
    tabs = st.tabs(["Users by College", "LLM Analytics", "Export Reports"])
    
    with tabs[0]:
        render_users_by_college(repo)
    
    with tabs[1]:
        render_llm_analytics(repo)
    
    with tabs[2]:
        render_export_reports(repo)


def render_users_by_college(repo):
    """Display users grouped by college with LLM stats"""
    st.header("👥 Users by College")
    
    colleges = repo.get_all_colleges()
    colleges.insert(0, "All Colleges")
    
    selected_college = st.selectbox(
        "Select College",
        colleges,
        index=0,
        help="Filter users by college or view all"
    )
    
    college_filter = None if selected_college == "All Colleges" else selected_college
    users_data = repo.get_users_by_college_with_llm_stats(college_filter)
    
    if not users_data:
        st.info("No users found for the selected filter.")
        return
    
    # Summary metrics
    col1, col2, col3, col4 = st.columns(4)
    
    total_users = len(users_data)
    llm_users = len([u for u in users_data if u['total_llm_calls'] > 0])
    total_llm_calls = sum(u['total_llm_calls'] for u in users_data)
    verified_users = len([u for u in users_data if u['is_verified']])
    
    with col1:
        st.metric("Total Users", total_users)
    with col2:
        st.metric("Verified Users", verified_users)
    with col3:
        st.metric("LLM Active Users", llm_users)
    with col4:
        st.metric("Total LLM Calls", total_llm_calls)
    
    st.divider()
    
    # Render the same full dataset used by CSV/Excel/JSON/Sheets exports.
    df_export = pd.DataFrame(repo.export_users_to_list(college_filter))
    df_display = df_export.copy()
    
    st.dataframe(
        df_display,
        use_container_width=True,
        hide_index=True,
        column_config={
            'Total LLM Calls': st.column_config.NumberColumn(format="%d"),
            'Total Tokens': st.column_config.NumberColumn(format="%d"),
        }
    )
    
    # Export CSV
    csv_buffer = BytesIO()
    df_csv = df_export
    df_csv.to_csv(csv_buffer, index=False)
    csv_buffer.seek(0)
    
    filename = f"users_{selected_college.lower().replace(' ', '_')}_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    st.download_button(
        label="📥 Download as CSV",
        data=csv_buffer.getvalue(),
        file_name=filename,
        mime="text/csv",
        key=f"download_csv_{selected_college}"
    )
    
    # Educational Note
    st.info(
        "💡 **Educational Note**: This dashboard demonstrates:\n"
        "- **SQL Aggregations**: GROUP_CONCAT, SUM, COUNT(DISTINCT)\n"
        "- **JOIN Operations**: LEFT JOIN between users and llm_usage tables\n"
        "- **Data Export**: CSV generation from database queries\n"
        "- **Role-Based Access Control**: Admin-only views\n"
    )


def render_llm_analytics(repo):
    """Display LLM usage analytics and trends"""
    st.header("🤖 LLM Usage Analytics")
    
    llm_summary = repo.get_llm_usage_summary()
    
    if not llm_summary:
        st.info("No LLM usage data available yet.")
        return
    
    # Summary metrics
    col1, col2, col3 = st.columns(3)
    
    total_llms = len(llm_summary)
    total_users_using_llm = sum(u['num_users'] for u in llm_summary)
    total_calls = sum(u['total_calls'] for u in llm_summary)
    
    with col1:
        st.metric("LLM Services Used", total_llms)
    with col2:
        st.metric("Users Using LLMs", total_users_using_llm)
    with col3:
        st.metric("Total API Calls", total_calls)
    
    st.divider()
    
    # LLM breakdown
    df_llm = pd.DataFrame([
        {
            'LLM Name': u['llm_name'],
            'Number of Users': u['num_users'],
            'Total Calls': u['total_calls'],
            'Total Tokens': u['total_tokens'] or 0,
            'Avg Calls per User': round(u['avg_calls_per_user'] or 0, 2)
        }
        for u in llm_summary
    ])
    
    st.subheader("LLM Usage Breakdown")
    st.dataframe(
        df_llm,
        use_container_width=True,
        hide_index=True,
        column_config={
            'Total Calls': st.column_config.NumberColumn(format="%d"),
            'Total Tokens': st.column_config.NumberColumn(format="%d"),
        }
    )
    
    # Visualization
    if len(df_llm) > 0:
        col1, col2 = st.columns(2)
        
        with col1:
            st.bar_chart(
                df_llm.set_index('LLM Name')['Total Calls'],
                use_container_width=True
            )
        
        with col2:
            st.bar_chart(
                df_llm.set_index('LLM Name')['Number of Users'],
                use_container_width=True
            )
    
    # Educational Note
    st.info(
        "💡 **Educational Note**: This analytics view demonstrates:\n"
        "- **Aggregate Functions**: SUM, COUNT, AVG\n"
        "- **GROUP BY Queries**: Aggregating usage by LLM\n"
        "- **Data Visualization**: Charts from database queries\n"
        "- **Metrics Dashboard Pattern**: KPI display pattern\n"
    )


def render_export_reports(repo):
    """Render export options to various formats"""
    st.header("📤 Export Reports")
    
    export_type = st.radio(
        "Select Export Format",
        ["CSV (Recommended)", "Excel", "Google Sheets", "JSON"],
        horizontal=True
    )
    
    colleges = repo.get_all_colleges()
    colleges.insert(0, "All Colleges")
    selected_college = st.selectbox("College Filter", colleges, index=0)
    
    college_filter = None if selected_college == "All Colleges" else selected_college
    
    export_data = repo.export_users_to_list(college_filter)
    df = pd.DataFrame(export_data)
    
    if export_type == "CSV (Recommended)":
        render_csv_export(df, selected_college)
    elif export_type == "Excel":
        render_excel_export(df, selected_college)
    elif export_type == "Google Sheets":
        render_sheets_export(repo, df, selected_college)
    elif export_type == "JSON":
        render_json_export(df, selected_college)


def render_csv_export(df: pd.DataFrame, college: str):
    """Export as CSV"""
    st.subheader("📄 CSV Export")
    
    csv_buffer = BytesIO()
    df.to_csv(csv_buffer, index=False)
    csv_buffer.seek(0)
    
    filename = f"users_report_{college.lower().replace(' ', '_')}_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    
    st.download_button(
        label="⬇️ Download CSV",
        data=csv_buffer.getvalue(),
        file_name=filename,
        mime="text/csv",
        key=f"csv_export_{college}"
    )
    
    st.write(f"**Records**: {len(df)} users")
    st.dataframe(df.head(10), use_container_width=True)


def render_excel_export(df: pd.DataFrame, college: str):
    """Export as Excel"""
    st.subheader("📊 Excel Export")
    
    # Requires openpyxl
    try:
        import openpyxl

        buffer = BytesIO()
        with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
            df.to_excel(writer, sheet_name='Users Report', index=False)
            
            # Format headers
            worksheet = writer.sheets['Users Report']
            for cell in worksheet[1]:
                cell.font = openpyxl.styles.Font(bold=True)
        
        buffer.seek(0)
        filename = f"users_report_{college.lower().replace(' ', '_')}_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        
        st.download_button(
            label="⬇️ Download Excel",
            data=buffer.getvalue(),
            file_name=filename,
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            key=f"excel_export_{college}"
        )
        st.write(f"**Records**: {len(df)} users")
    except ImportError:
        st.warning("Excel export requires: `pip install openpyxl`")


def render_sheets_export(repo, df: pd.DataFrame, college: str):
    """Export to Google Sheets"""
    st.subheader("☁️ Google Sheets Export")
    
    try:
        from services.sheets_export_service import get_sheets_service
        
        sheets_svc = get_sheets_service()
        if not sheets_svc:
            st.warning("Google Sheets not configured. Set GOOGLE_SHEETS_CREDENTIALS environment variable.")
            return
        
        if st.button(f"Export to Google Sheets - {college}", key=f"sheets_export_{college}"):
            with st.spinner("Exporting to Google Sheets..."):
                spreadsheet_name = f"Civil AI Users Report - {college} - {datetime.datetime.now().strftime('%Y-%m-%d')}"
                url = sheets_svc.export_users_report(df, spreadsheet_name)
                st.success(f"✅ Exported to Google Sheets!")
                st.link_button("🔗 Open Spreadsheet", url)
    except ImportError:
        st.warning("Google Sheets export requires: `pip install gspread google-auth-oauthlib`")


def render_json_export(df: pd.DataFrame, college: str):
    """Export as JSON"""
    st.subheader("📋 JSON Export")
    
    json_str = df.to_json(orient='records', indent=2)
    
    st.download_button(
        label="⬇️ Download JSON",
        data=json_str,
        file_name=f"users_report_{college.lower().replace(' ', '_')}_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
        mime="application/json",
        key=f"json_export_{college}"
    )
    
    st.write(f"**Records**: {len(df)} users")
    st.json(df.head(3).to_dict(orient='records'))
