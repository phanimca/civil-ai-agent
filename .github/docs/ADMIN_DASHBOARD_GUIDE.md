# Admin Dashboard - Quick Reference

## 🚀 Quick Start for Admins

### Accessing the Dashboard

1. **Login** with your admin email
2. Click **"Admin"** in the navigation (only shows if you have admin role)
3. Choose your view from tabs:
   - 👥 **Users by College**
   - 🤖 **LLM Analytics**
   - 📤 **Export Reports**

---

## 👥 Users by College Tab

### What It Shows
- **Total Users** in selected college
- **Verified Users** (completed registration)
- **LLM Active Users** (used at least one AI tool)
- **Total LLM Calls** (sum of all student API calls)

### How to Use
1. **Select College** from dropdown at top
2. **View Metrics** in colored cards
3. **Browse Table** showing each student:
   - Name & Email
   - College & Profession
   - AI Tool preference (from registration)
   - ✅ Verification status
   - LLM Calls & Tokens Used
   - Registration date
4. **Download Table as CSV** button at bottom

### Export CSV
- Click "📥 Download as CSV"
- File includes all metrics above
- Recommended format for Excel/Power BI analysis

### Educational Insights
- Can see which students are engaged with AI
- Identify students needing support
- Analyze adoption by college/major

---

## 🤖 LLM Analytics Tab

### What It Shows
- **LLM Services Used** - How many different AI tools (ChatGPT, Claude, Gemini, etc.)
- **Users Using LLMs** - How many students active with AI
- **Total API Calls** - Aggregate of all student API calls

### The Data Table
| Metric | Meaning |
|--------|---------|
| LLM Name | Which AI service (ChatGPT, Claude, etc.) |
| Number of Users | How many students use this LLM |
| Total Calls | Sum of all API calls to this LLM |
| Total Tokens | Approximate token consumption |
| Avg Calls per User | Average usage per student |

### Charts
- **Left Chart**: Students per LLM (adoption)
- **Right Chart**: API Calls per LLM (usage intensity)

### What These Mean
- 📊 If ChatGPT bar is tallest → Most popular among students
- 📈 If Claude's ratio is high → Heavy users who try it
- 🎯 Use for budget forecasting AI tool credits

---

## 📤 Export Reports Tab

### Step 1: Select Format
- **CSV** ✅ Recommended (fastest, Excel-compatible)
- **Excel** (formatted with bold headers)
- **Google Sheets** (cloud, shareable)
- **JSON** (programmatic access)

### Step 2: Filter by College (optional)
- Dropdown to select specific college or "All Colleges"
- Creates college-specific file name

### Step 3: Download or Export
- **CSV**: Click "Download CSV" button
- **Excel**: Requires `pip install openpyxl`
- **Google Sheets**: Click "Export" → Link provided
- **JSON**: Click "Download JSON"

---

## 💾 Detailed Column Reference

When you download a report, these columns are included:

| Column | Description |
|--------|-------------|
| ID | Internal user ID |
| Full Name | Student name |
| Email | University email |
| College | College/School affiliation |
| Profession | Major/Field of study |
| AI Tool Usage | Student survey response (e.g., "ChatGPT, Claude") |
| Verified | Whether email is verified (Yes/No) |
| Registration Date | When they signed up |
| Total LLM Calls | Number of times they used any AI tool |
| Total Tokens | Approximate API tokens consumed |
| Distinct LLMs Used | How many different LLMs they tried |
| LLM Breakdown | Specific count per tool (e.g., "ChatGPT:5; Claude:3") |

---

## 📊 Analytics You Can Do

### 1. Adoption Rate by College
```
College A: 15 students, 12 using AI = 80% adoption
College B: 20 students, 8 using AI = 40% adoption
→ Use to recommend AI training for College B
```

### 2. LLM Preference
```
ChatGPT: 45 students
Claude: 28 students
Gemini: 12 students
→ Most students prefer ChatGPT; Claude has niche users
```

### 3. Usage Intensity
```
Student X: 150 API calls
Student Y: 5 API calls
→ Identify power users vs. casual users
```

### 4. Token Forecasting
```
Monthly tokens = Total Tokens per LLM
→ Budget for next month's API costs
```

---

## 🔍 Troubleshooting

### "Admin" Tab Not Showing?
- ✅ Make sure you're logged in as admin
- ✅ Your email must have `role='admin'` in database
- 📞 Contact database admin if not set up

### No Data in Users by College?
- ✅ Check that students have registered AND filled college field
- ✅ Some students may not have completed registration

### LLM Analytics Shows 0?
- ✅ This means NOBODY has logged LLM usage yet
- ✅ App needs to call `repository.log_llm_usage()` when AI is used
- 📞 Check with developers that logging is implemented

### Google Sheets Export Not Working?
- ✅ Check that Google credentials are configured (see main guide)
- ✅ Requires `GOOGLE_SHEETS_CREDENTIALS` environment variable
- ✅ Must install: `pip install gspread google-auth-oauthlib`

---

## 📈 Common Use Cases

### Use Case 1: Monitoring Student Engagement
**Situation**: Last semester, only 10% of students tried AI tools
**Action**: Check LLM Analytics to see current adoption
**Decision**: If still low, plan workshop on using AI for learning

### Use Case 2: Resource Planning
**Situation**: Faculty asks "How many students are using LLMs?"
**Action**: Go to Users by College → Select college → Note metric
**Response**: "12 out of 50 students (24%) are actively using AI tools"

### Use Case 3: Budget Forecasting
**Situation**: Finance says "How much will API costs be next month?"
**Action**: Check LLM Analytics → Total Tokens per LLM
**Decision**: Multiply by price-per-token for each provider

### Use Case 4: Identifying Training Opportunities
**Situation**: Some students have high usage, others have zero
**Action**: Filter by college, identify patterns
**Decision**: Run "AI for Beginners" workshop for low-usage colleges

### Use Case 5: Sharing Metrics with Leadership
**Situation**: President wants proof that AI initiative is working
**Action**: Export to Google Sheets → Share link
**Presentation**: "45 students across 3 colleges are now using AI tools"

---

## 📱 Mobile Access

The admin dashboard is **responsive** - you can:
- ✅ View on phones (metrics stack vertically)
- ✅ Download CSV files directly
- ✅ Work on tablets (full table view)
- ❌ Complex charts harder to read on small screens

---

## 🔐 Data Privacy Notes

✅ **What is exported:**
- Student names, emails, college
- LLM usage statistics only (counts, not content)
- Registration timestamps

❌ **What is NOT exported:**
- Actual LLM prompts or responses
- Student passwords or authentication data
- Sensitive academic records
- IP addresses or location data

💡 **Safe sharing:**
- It's safe to download CSV for email
- Avoid sharing in public networks
- Google Sheets are shared with specific people only

---

## 🎓 Teaching with This Dashboard

### Activity 1: Data Aggregation Lesson
"Look at this table structure - it combines TWO SQL tables together. Can you spot the JOIN?"
→ Point out the college filtering + LLM usage merge

### Activity 2: Analytics Interpretation
"Why might Claude have fewer users but higher tokens per user?"
→ Discuss user types, use cases, complexity

### Activity 3: CSV to Visualization
Students download CSV → Import to Google Sheets → Create charts
"Now make a pie chart of LLM adoption!"

### Activity 4: Forecasting Exercise
"If we start 500 new students next semester, and 25% adoption continues..."
→ Calculate projected API costs

---

## 💡 Pro Tips

1. **Find High Achievers**
   - Sort by "Total LLM Calls"
   - Students with 50+ calls are power users
   - Consider them for research partnerships

2. **Identify Barriers**
   - Students with 0 LLM calls but verified
   - May need help/training
   - Consider outreach

3. **Track Trends**
   - Export reports monthly
   - Compare adoption over time
   - Visualize in Power BI or Excel

4. **Analyze by Demographics**
   - Compare colleges
   - Compare professions
   - Identify groups needing support

5. **Quality Over Quantity**
   - High calls ≠ quality learning
   - Add follow-up survey: "Rate your AI learning experience"

---

## 📞 Support & Feedback

- **Questions?** Check `DATABASE_AND_REPORTING_GUIDE.md`
- **Want new metrics?** Contact development team
- **Found a bug?** Create an issue with:
  - What were you trying to do?
  - What happened instead?
  - Screenshot of the problem

---

Last Updated: March 2026
Version: 1.0 - LLM Analytics Dashboard
