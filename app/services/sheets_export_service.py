"""Google Sheets export service for admin reports"""
from typing import Optional
import gspread
from google.oauth2.service_account import Credentials
import streamlit as st
import pandas as pd
from datetime import datetime


class GoogleSheetsExportService:
    """Service to export user data and LLM usage to Google Sheets"""
    
    def __init__(self, credentials_json_path: str):
        """
        Initialize Google Sheets service.
        
        Args:
            credentials_json_path: Path to Google Cloud service account JSON
        """
        self.credentials_path = credentials_json_path
        self.client = None
        self._init_client()
    
    def _init_client(self):
        """Initialize gspread client with service account credentials"""
        try:
            scopes = [
                'https://www.googleapis.com/auth/spreadsheets',
                'https://www.googleapis.com/auth/drive'
            ]
            creds = Credentials.from_service_account_file(
                self.credentials_path, 
                scopes=scopes
            )
            self.client = gspread.authorize(creds)
        except FileNotFoundError:
            raise FileNotFoundError(f"Google credentials not found at {self.credentials_path}")
        except Exception as e:
            raise Exception(f"Failed to initialize Google Sheets: {str(e)}")
    
    def create_or_get_spreadsheet(self, spreadsheet_name: str) -> gspread.Spreadsheet:
        """Create new spreadsheet or open existing one"""
        try:
            # Try to open existing spreadsheet
            sheet = self.client.open(spreadsheet_name)
            return sheet
        except gspread.exceptions.SpreadsheetNotFound:
            # Create new spreadsheet
            sheet = self.client.create(spreadsheet_name)
            # Share with domain if needed
            sheet.share('', perm_type='default', role='reader')
            return sheet
    
    def export_users_report(self, df: pd.DataFrame, spreadsheet_name: str, sheet_title: str = "Users Report"):
        """
        Export users data to Google Sheets.
        
        Args:
            df: DataFrame with user data
            spreadsheet_name: Name of the spreadsheet to create/update
            sheet_title: Name of the worksheet
        
        Returns:
            URL of the created/updated spreadsheet
        """
        try:
            sheet = self.create_or_get_spreadsheet(spreadsheet_name)
            
            # Remove old sheet if exists
            try:
                worksheet = sheet.worksheet(sheet_title)
                sheet.del_worksheet(worksheet)
            except gspread.exceptions.WorksheetNotFound:
                pass
            
            # Create new worksheet
            worksheet = sheet.add_worksheet(title=sheet_title, rows=len(df)+1, cols=len(df.columns))
            
            # Update headers
            headers = list(df.columns)
            worksheet.update([headers], range_name='A1')
            
            # Update data rows
            data = df.values.tolist()
            if data:
                worksheet.update(data, range_name='A2')
            
            # Auto-resize columns
            worksheet.columns = len(df.columns)
            
            return sheet.url
        except Exception as e:
            raise Exception(f"Failed to export to Google Sheets: {str(e)}")
    
    def export_college_summary(self, college_data: dict, spreadsheet_name: str):
        """
        Export college-wise summary to Google Sheets.
        
        Args:
            college_data: Dict with college names as keys and user lists as values
            spreadsheet_name: Name of the spreadsheet
        
        Returns:
            URL of the spreadsheet
        """
        try:
            sheet = self.create_or_get_spreadsheet(spreadsheet_name)
            
            # Create summary worksheet
            try:
                summary_ws = sheet.worksheet("Summary")
                sheet.del_worksheet(summary_ws)
            except gspread.exceptions.WorksheetNotFound:
                pass
            
            summary_ws = sheet.add_worksheet(title="Summary", rows=len(college_data)+1, cols=4)
            summary_ws.update([['College', 'Total Users', 'LLM Users', 'Total LLM Calls']], range_name='A1')
            
            row_idx = 2
            for college, users in college_data.items():
                total_users = len(users)
                llm_users = len([u for u in users if u.get('total_llm_calls', 0) > 0])
                total_calls = sum(u.get('total_llm_calls', 0) for u in users)
                
                summary_ws.update(
                    [[college, total_users, llm_users, total_calls]],
                    range_name=f'A{row_idx}'
                )
                row_idx += 1
            
            return sheet.url
        except Exception as e:
            raise Exception(f"Failed to export college summary: {str(e)}")
    
    def export_llm_analytics(self, llm_stats: list, spreadsheet_name: str):
        """
        Export LLM usage analytics to Google Sheets.
        
        Args:
            llm_stats: List of LLM usage statistics
            spreadsheet_name: Name of the spreadsheet
        
        Returns:
            URL of the spreadsheet
        """
        try:
            sheet = self.create_or_get_spreadsheet(spreadsheet_name)
            
            # Create analytics worksheet
            try:
                analytics_ws = sheet.worksheet("LLM Analytics")
                sheet.del_worksheet(analytics_ws)
            except gspread.exceptions.WorksheetNotFound:
                pass
            
            headers = ['LLM Name', 'Number of Users', 'Total Calls', 'Total Tokens', 'Avg Calls/User']
            analytics_ws = sheet.add_worksheet(title="LLM Analytics", rows=len(llm_stats)+1, cols=5)
            analytics_ws.update([headers], range_name='A1')
            
            data = []
            for stat in llm_stats:
                data.append([
                    stat['llm_name'],
                    stat['num_users'],
                    stat['total_calls'],
                    stat['total_tokens'],
                    round(stat['avg_calls_per_user'], 2) if stat['avg_calls_per_user'] else 0
                ])
            
            if data:
                analytics_ws.update(data, range_name='A2')
            
            return sheet.url
        except Exception as e:
            raise Exception(f"Failed to export LLM analytics: {str(e)}")


@st.cache_resource
def get_sheets_service():
    """Cached Google Sheets service instance"""
    import os
    credentials_path = os.getenv('GOOGLE_SHEETS_CREDENTIALS', './credentials.json')
    try:
        return GoogleSheetsExportService(credentials_path)
    except Exception as e:
        st.warning(f"Google Sheets not configured: {str(e)}")
        return None
