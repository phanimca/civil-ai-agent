# Database & LLM Usage Tracking - Setup Guide

## Overview

This system demonstrates production-grade database practices for an educational platform:
- **SQLite** local database with college/profession tracking
- **LLM Usage Monitoring** - Track ChatGPT, Claude, Gemini usage per user
- **Admin Reporting Dashboard** - CSV/Excel/Google Sheets exports by college
- **Role-Based Access Control** - Admin-only analytics views

---

## 1. Database Schema

### Tables Created

**users** (existing, enhanced with college field)
```sql
CREATE TABLE users (
    id INTEGER PRIMARY KEY,
    full_name TEXT,
    email TEXT UNIQUE,
    college TEXT,
    profession TEXT,
    ai_tool_usage TEXT,  -- Already asking students which AI tools they use
    role TEXT,
    created_at TEXT
);
```

**llm_usage** (NEW - tracks LLM API calls)
```sql
CREATE TABLE llm_usage (
    id INTEGER PRIMARY KEY,
    user_id INTEGER,
    llm_name TEXT,           -- 'ChatGPT', 'Claude', 'Gemini', etc.
    usage_count INTEGER,     -- Number of API calls
    tokens_used INTEGER,     -- Token count (if applicable)
    last_used TEXT,          -- Timestamp of last use
    created_at TEXT,
    updated_at TEXT,
    UNIQUE(user_id, llm_name)
);
```

---

## 2. Repository Methods (Enhanced)

### Logging LLM Usage
```python
from app.data.repository import SQLiteRepository

repo = SQLiteRepository(...)

# Log when student uses ChatGPT
repo.log_llm_usage(
    user_id=123,
    llm_name='ChatGPT',
    tokens_used=500
)

# Log Claude usage
repo.log_llm_usage(
    user_id=123,
    llm_name='Claude',
    tokens_used=1200
)
```

### Getting User Stats
```python
# Get LLM usage for a specific student
stats = repo.get_user_llm_stats(user_id=123)
# Returns: [
#   {'llm_name': 'ChatGPT', 'usage_count': 5, 'tokens_used': 2500},
#   {'llm_name': 'Claude', 'usage_count': 3, 'tokens_used': 1500}
# ]
```

### Getting College Reports
```python
# Get all users with college="MIT" + their LLM stats
users_data = repo.get_users_by_college_with_llm_stats(college='MIT')

# Returns structured data with aggregations:
# {
#   'id': 1,
#   'full_name': 'John Doe',
#   'college': 'MIT',
#   'total_llm_calls': 8,
#   'total_tokens': 4000,
#   'distinct_llms': 2,
#   'llm_breakdown': 'ChatGPT:5; Claude:3'
# }
```

### Export to CSV/Excel
```python
# Export all MIT students
export_data = repo.export_users_to_list(college='MIT')
# Returns list of dicts with all fields for CSV writing
```

---

## 3. Admin Dashboard Features

### Access the Dashboard
1. **Login as admin** (use your admin seed email from env vars)
2. **Navigate to "Admin" tab** (visible only for admin role)
3. **Choose view:**
   - **Users by College** - Filter students, view LLM usage
   - **LLM Analytics** - Overall LLM adoption statistics
   - **Export Reports** - Download CSV/Excel/Google Sheets

### Users by College Tab
- **Filter by college** - Select from dropdown or "All Colleges"
- **Key Metrics Shown:**
  - Total Users in college
  - Verified Users
  - Users actively using LLMs
  - Total LLM API calls made
- **Table Displays:**
  - Student name, email, profession
  - AI tool preference (from registration)
  - Verification status
  - LLM usage count & token count
  - Registration date

### LLM Analytics Tab
- **Global statistics:**
  - How many LLM services are being used (ChatGPT, Claude, etc.)
  - How many students use each LLM
  - Total API calls and tokens per LLM
  - Average usage per student
- **Visualizations:**
  - Bar charts for API calls by LLM
  - Bar charts for user adoption by LLM

### Export Reports Tab
**Format Options:**

#### CSV (Recommended)
```
Full Name,Email,College,Profession,Total LLM Calls,Tokens Used,...
John Doe,john@mit.edu,MIT,Computer Science,8,4000,...
```

#### Excel
- Auto-formatted headers
- Column auto-sizing
- Requires: `pip install openpyxl`

#### Google Sheets (Cloud-Based)
- Live-shared spreadsheet in Google Drive
- Real-time collaboration
- Requires credentials setup (see below)

#### JSON
- For programmatic access
- Structured for integration with other tools

---

## 4. Google Sheets Integration (Optional)

### Setup Steps

**Step 1: Create Google Cloud Project**
1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create new project: "Civil AI Student Dashboard"
3. Enable APIs:
   - Google Sheets API
   - Google Drive API

**Step 2: Create Service Account**
1. Go to "Service Accounts" in IAM
2. Click "Create Service Account"
3. Name: `civil-ai-admin`
4. Create key → Download JSON file
5. Save as `credentials.json` in project root

**Step 3: Share Google Drive Folder**
1. Create a folder in your Google Drive: "Civil AI Reports"
2. Share it with the service account email (found in credentials.json)
3. Set permission to "Editor"

**Step 4: Set Environment Variable**
```bash
# .env (or Streamlit Cloud secrets)
GOOGLE_SHEETS_CREDENTIALS=/path/to/credentials.json
```

**Step 5: Install Package**
```bash
pip install gspread google-auth-oauthlib
```

### Usage from Admin Dashboard
- Go to "Export Reports" → "Google Sheets"
- Click "Export to Google Sheets"
- Spreadsheet created instantly in Google Drive
- Share link provided in Streamlit UI

---

## 5. Educational Database Concepts Demonstrated

### SQL Concepts
- ✅ **PRIMARY KEY** - User IDs, unique identifiers
- ✅ **FOREIGN KEY** - llm_usage → users relationship
- ✅ **UNIQUE Constraint** - One record per (user, llm) pair
- ✅ **INDEX** - Performance optimization on email and college
- ✅ **GROUP_CONCAT** - Aggregate LLM breakdown per user
- ✅ **LEFT JOIN** - Include users even without LLM history
- ✅ **WHERE Clause** - Filter by college
- ✅ **ORDER BY** - Sort results
- ✅ **SUM, COUNT, AVG** - Aggregation functions

### Database Design Patterns
- **Schema Evolution** - Adding columns without breaking existing code (`_ensure_column`)
- **Data Validation** - NOT NULL constraints, UNIQUE combinations
- **Referential Integrity** - FOREIGN KEY relationships
- **Audit Trail** - created_at, updated_at timestamps
- **Performance** - Strategic indexing

### Python/OOP Patterns
- **Repository Pattern** - Data access abstraction layer
- **Caching** - `@st.cache_resource` for service initialization
- **Error Handling** - Graceful fallbacks for missing Google credentials
- **Data Export** - Multiple format support (CSV, JSON, Google Sheets)

### Web/Data Science Patterns
- **Role-Based Access Control** - Admin-only views
- **Aggregation Pipeline** - Database-level data transformation
- **Export/Sharing** - Multi-channel report distribution
- **Real-time Dashboards** - Live metrics visualization

---

## 6. Example: Logging LLM Usage in Your App

### Adding LLM Logging to Streamlit Pages

**In _render_inspect page or wherever you call LLMs:**

```python
def _render_inspect(self, user) -> None:
    # ... existing code ...
    
    if st.button("Generate AI Report"):
        # Call your AI model
        response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[...]
        )
        
        # Log the usage
        tokens_used = response['usage']['total_tokens']
        self.repository.log_llm_usage(
            user_id=user['id'],
            llm_name='ChatGPT',
            tokens_used=tokens_used
        )
        
        st.success("Report generated!")
```

### Batch Logging Example

```python
def _generate_reports_batch(self, user_ids, llm_stats):
    """Process multiple reports and log each one"""
    for user_id in user_ids:
        # Generate report
        tokens = generate_report(...)
        
        # Log to database
        self.repository.log_llm_usage(
            user_id=user_id,
            llm_name='Claude',
            tokens_used=tokens
        )
```

---

## 7. Installation & Setup

### Step 1: Update Python Packages
```bash
pip install pandas gspread google-auth-oauthlib
```

### Step 2: The Database Automatically Migrates
```python
# In main.py (already done)
repo = SQLiteRepository(...)
repo.init_db()  # Automatically creates llm_usage table on first run
```

### Step 3: Start Logging Usage
```python
# Anywhere in your Streamlit app:
repo.log_llm_usage(user_id, 'ChatGPT', tokens)
```

### Step 4: Access Admin Dashboard
- Log in as admin
- Navigate to "Admin" tab
- View reports and export

---

## 8. Data Privacy & GDPR Considerations

For educational deployment:

✅ **What's Recommended:**
- Store college affiliation (for filtering)
- Store AI tool preferences (from survey)
- Store LLM usage stats (count, not prompts)
- Timestamp all access

❌ **What to AVOID:**
- Storing actual LLM prompts
- Storing response content
- Storing sensitive student info beyond email
- Sharing raw data without anonymization

---

## 9. Architecture Diagram

```
┌─────────────────────────────────────────────────────┐
│         Streamlit Web Interface                      │
├─────────────────────────────────────────────────────┤
│  Admin Dashboard (render_admin_dashboard)            │
│  ├─ Users by College Tab                            │
│  ├─ LLM Analytics Tab                               │
│  └─ Export Reports Tab                              │
└──────────────────────┬──────────────────────────────┘
                       │
┌──────────────────────┴──────────────────────────────┐
│    SQLiteRepository (Data Access Layer)             │
│  ├─ log_llm_usage()                                 │
│  ├─ get_users_by_college()                          │
│  ├─ get_llm_usage_summary()                         │
│  └─ export_users_to_list()                          │
└──────────────────────┬──────────────────────────────┘
                       │
         ┌─────────────┼─────────────┐
         │             │             │
    ┌────▼────┐   ┌────▼────┐  ┌───▼────┐
    │ SQLite  │   │ Google  │  │ CSV    │
    │Database │   │ Sheets  │  │ Export │
    └─────────┘   └─────────┘  └────────┘
```

---

## 10. Troubleshooting

### LLM Usage Not Showing Up
```python
# Check if data is being logged
>> conn = repo.get_conn()
>> conn.execute("SELECT * FROM llm_usage WHERE user_id = ?", (123,))
>> rows = conn.fetchall()
>> print(rows)  # Should show your entries
```

### Google Sheets Export Failing
```bash
# Check credentials path
echo $GOOGLE_SHEETS_CREDENTIALS

# Validate JSON is readable
cat credentials.json | python -m json.tool

# Test gspread import
python -c "import gspread; print('OK')"
```

### Admin Tab Not Showing
```python
# Verify admin role in database:
SELECT * FROM users WHERE email = 'your_email@example.com';
# Should show role='admin'

# If not, update:
UPDATE users SET role='admin' WHERE email='your_email@example.com';
```

---

## 11. Next Steps

1. **For Learning:**
   - Explore `repository.py` methods - see SQL patterns
   - Modify queries to add new analytics
   - Try different aggregation functions

2. **For Production:**
   - Add row-level security (college-specific dashboards)
   - Implement data retention policies
   - Add audit logging for exports
   - Set up automated reports via cron

3. **For Expansion:**
   - Track API costs per LLM
   - Compare model performance metrics
   - Analyze adoption patterns over time
   - Build student recommendations based on usage

---

Questions? Check the inline comments in:
- `app/data/repository.py` - SQL queries with explanations
- `app/ui/admin_dashboard.py` - UI patterns
- `app/services/sheets_export_service.py` - Google Sheets integration
