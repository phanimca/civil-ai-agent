# LLM Usage Logging - Integration Examples

This file shows practical examples of how to add LLM usage logging throughout your Streamlit app.

## Example 1: Log Usage When Generating AI Report

**Location:** `app/ui/streamlit_app.py` in `_render_inspect()` method

```python
def _generate_inspection_report(self, user, image_data):
    """Generate AI report with LLM usage logging"""
    
    try:
        # Call your AI model (e.g., OpenAI, Anthropic, etc.)
        import openai
        
        response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[
                {
                    "role": "user",
                    "content": f"Analyze this crack image..."
                }
            ]
        )
        
        # Extract tokens used
        tokens_used = response['usage']['total_tokens']
        report_text = response['choices'][0]['message']['content']
        
        # 🔑 LOG THE USAGE
        self.repository.log_llm_usage(
            user_id=int(user['id']),
            llm_name='ChatGPT (GPT-4)',
            tokens_used=tokens_used
        )
        
        # Save to database
        self.repository.log_inspection(...)
        
        return report_text
        
    except Exception as e:
        st.error(f"Report generation failed: {str(e)}")
        return None
```

## Example 2: Log Usage from Claude/Anthropic

**For students using Claude API:**

```python
def _generate_report_claude(self, user, prompt):
    """Example with Anthropic Claude"""
    
    import anthropic
    
    client = anthropic.Anthropic(api_key="your-api-key")
    
    message = client.messages.create(
        model="claude-3-sonnet-20240229",
        max_tokens=1024,
        messages=[
            {"role": "user", "content": prompt}
        ]
    )
    
    # Log Claude usage
    tokens_used = message.usage.input_tokens + message.usage.output_tokens
    
    self.repository.log_llm_usage(
        user_id=int(user['id']),
        llm_name='Claude 3 Sonnet',
        tokens_used=tokens_used
    )
    
    return message.content[0].text
```

## Example 3: Log Usage from Google Gemini

**For students using Google Gemini:**

```python
def _generate_report_gemini(self, user, prompt):
    """Example with Google Gemini"""
    
    import google.generativeai as genai
    
    genai.configure(api_key="your-api-key")
    model = genai.GenerativeModel('gemini-pro')
    
    response = model.generate_content(prompt)
    
    # Estimate tokens (Gemini doesn't always return explicit count)
    estimated_tokens = len(prompt.split()) + len(response.text.split())
    
    self.repository.log_llm_usage(
        user_id=int(user['id']),
        llm_name='Google Gemini Pro',
        tokens_used=estimated_tokens
    )
    
    return response.text
```

## Example 4: Batch Logging Multiple Operations

**For processing multiple requests:**

```python
def process_student_batch(self, user_id, images_list):
    """Process multiple images and log each LLM call"""
    
    results = []
    for idx, image in enumerate(images_list):
        try:
            # Generate report for each image
            report = self._generate_inspection_report(user_id, image)
            
            # Log one entry per image processed
            self.repository.log_llm_usage(
                user_id=user_id,
                llm_name="ChatGPT",
                tokens_used=500  # Approximate
            )
            
            results.append(report)
        except Exception as e:
            st.warning(f"Failed on image {idx}: {str(e)}")
    
    return results
```

## Example 5: Conditional Logging Based on Model Selection

**User selects which AI tool to use:**

```python
def render_inspect_with_model_selection(self, user):
    """Let students choose which AI model to use"""
    
    col1, col2 = st.columns([3, 1])
    
    with col1:
        model_choice = st.radio(
            "Select AI Model",
            ["ChatGPT (GPT-4)", "Claude 3 Sonnet", "Google Gemini Pro"],
            horizontal=True
        )
    
    uploaded_file = st.file_uploader("Upload image")
    
    if uploaded_file and st.button("Analyze"):
        # Generate report with appropriate model
        if model_choice == "ChatGPT (GPT-4)":
            report = self._generate_report_chatgpt(user, uploaded_file)
            llm_name = "ChatGPT (GPT-4)"
        elif model_choice == "Claude 3 Sonnet":
            report = self._generate_report_claude(user, uploaded_file)
            llm_name = "Claude 3 Sonnet"
        else:
            report = self._generate_report_gemini(user, uploaded_file)
            llm_name = "Google Gemini Pro"
        
        # Single standardized logging call
        if report:
            self.repository.log_llm_usage(
                user_id=int(user['id']),
                llm_name=llm_name,
                tokens_used=1000  # Or actual count if available
            )
            st.success(f"Report generated using {llm_name}")
```

## Example 6: Track Usage in Student's First Time Interaction

**Log when student first uses each LLM:**

```python
def on_first_llm_usage(self, user_id, llm_name):
    """Called first time student uses a specific LLM"""
    
    # Check if already logged
    existing = self.repository.get_conn().execute(
        "SELECT * FROM llm_usage WHERE user_id=? AND llm_name=?",
        (user_id, llm_name)
    ).fetchone()
    
    if not existing:
        # First time tracking
        st.balloons()  # Celebration!
        st.write(f"🎉 You're now using {llm_name}!")
        
        # Log it
        self.repository.log_llm_usage(user_id, llm_name, tokens_used=0)
```

## Example 7: Real-time Usage Dashboard for Student

**Show individual student their LLM usage:**

```python
@st.fragment
def show_student_llm_stats(self, user_id):
    """Display user's own LLM usage breakdown"""
    
    stats = self.repository.get_user_llm_stats(user_id)
    
    if not stats:
        st.info("No LLM usage yet. Try generating a report!")
        return
    
    col1, col2, col3 = st.columns(3)
    
    total_calls = sum(s['usage_count'] for s in stats)
    total_tokens = sum(s['tokens_used'] for s in stats)
    distinct_llms = len(stats)
    
    with col1:
        st.metric("Total LLM Calls", total_calls)
    with col2:
        st.metric("Total Tokens", total_tokens)
    with col3:
        st.metric("Models Used", distinct_llms)
    
    # Show breakdown
    st.subheader("Your LLM Usage Breakdown")
    for stat in stats:
        st.write(
            f"**{stat['llm_name']}**: {stat['usage_count']} calls, "
            f"{stat['tokens_used']} tokens, "
            f"Last used: {stat['last_used']}"
        )
```

## Example 8: Educational Report Card

**For students to see learning metrics:**

```python
def generate_student_report_card(self, user_id, user):
    """Create a learning report card for student"""
    
    st.header(f"📊 Your Learning Report Card")
    
    # Get their stats
    llm_stats = self.repository.get_user_llm_stats(user_id)
    inspections = self.repository.recent_inspections(user_id, limit=10)
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric(
            "AI Models Explored",
            len(llm_stats),
            help="How many different AI systems you've tried"
        )
    
    with col2:
        total_calls = sum(s['usage_count'] for s in llm_stats)
        st.metric(
            "AI Experiments",
            total_calls,
            help="Total times you used an AI tool"
        )
    
    with col3:
        st.metric(
            "Inspections Done",
            len(inspections),
            help="Number of civil structures you've analyzed"
        )
    
    st.markdown("---")
    st.write("**Models You've Used:**")
    for stat in llm_stats:
        st.markdown(
            f"- 🤖 **{stat['llm_name']}**: {stat['usage_count']} times"
        )
```

## Example 9: Aggregating College-Level Statistics

**Admin creating a college report:**

```python
def generate_college_report(self, college_name):
    """Generate comprehensive report for a college"""
    
    users_data = self.repository.get_users_by_college_with_llm_stats(college_name)
    
    st.write(f"# Report: {college_name}")
    
    # Metrics
    total_students = len(users_data)
    active_llm_students = len([u for u in users_data if u['total_llm_calls'] > 0])
    total_llm_calls = sum(u['total_llm_calls'] for u in users_data)
    
    st.metric("Total Students", total_students)
    st.metric("Using AI Tools", active_llm_students)
    st.metric("Total API Calls", total_llm_calls)
    
    # Detailed table
    df = pd.DataFrame(users_data)
    st.dataframe(df[['full_name', 'total_llm_calls', 'distinct_llms', 'llm_breakdown']])
```

## Example 10: Analyzing LLM Adoption Trends

**Educational analysis: Which LLMs are popular?**

```python
def show_llm_adoption_trends(self):
    """Show which AI tools are most popular among students"""
    
    st.header("🤖 AI Tool Adoption Trends")
    
    llm_summary = self.repository.get_llm_usage_summary()
    
    if not llm_summary:
        st.info("No data yet")
        return
    
    # Create visualization
    df_trends = pd.DataFrame([
        {
            'AI Tool': s['llm_name'],
            'Student Users': s['num_users'],
            'Total API Calls': s['total_calls'],
            'Avg Uses per Student': round(s['avg_calls_per_user'], 1)
        }
        for s in llm_summary
    ])
    
    # Charts
    col1, col2 = st.columns(2)
    
    with col1:
        st.bar_chart(
            df_trends.set_index('AI Tool')['Student Users'],
            title="Students per Tool"
        )
    
    with col2:
        st.bar_chart(
            df_trends.set_index('AI Tool')['Total API Calls'],
            title="Total API Calls per Tool"
        )
    
    # Table
    st.dataframe(df_trends, use_container_width=True)
    
    # Insights
    st.info(
        "💡 **Insights**: This data shows:\n"
        "- ChatGPT is leading in student adoption\n"
        "- Claude has higher average usage per student\n"
        "- Consider what features attract students"
    )
```

---

## Implementation Checklist

- [ ] Choose where to log LLM usage (which functions/pages)
- [ ] Get API token counts from your LLM provider
- [ ] Add `repository.log_llm_usage()` calls in those locations
- [ ] Test logging by:
  - Generating a report as a user
  - Checking the admin dashboard → Users by College
  - Verifying LLM calls appear
- [ ] Set up Google Sheets export (optional)
- [ ] Share admin dashboard link with stakeholders

## Common Integration Points

1. **When you call OpenAI/Claude/Gemini API** → Log it
2. **After generating AI reports** → Log it
3. **User first time trying new model** → Log it
4. **Batch processing multiple items** → Log for each
5. **Success milestones** → Celebrate + Log it

---

## Testing Your Logging

```python
# In Streamlit terminal:

import sqlite3
conn = sqlite3.connect('app_data/inspections.db')
cur = conn.cursor()

# Check if table exists
cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='llm_usage'")
print(cur.fetchone())  # Should return ('llm_usage',)

# See all logged usage
cur.execute("""
SELECT u.full_name, l.llm_name, l.usage_count, l.tokens_used, l.last_used
FROM llm_usage l
JOIN users u ON l.user_id = u.id
ORDER BY l.last_used DESC
""")

for row in cur.fetchall():
    print(row)

conn.close()
```

---

## Support

If logging isn't working:
1. Check that `repository.init_db()` was called (creates llm_usage table)
2. Verify user_id is correct (not None, not zero)
3. Ensure error isn't silently caught - add logging: `print(f"Logged {llm_name}: {tokens}")`
4. Query the table directly to see if data was inserted
