import streamlit as st
import json
import sqlite3
import os
from datetime import datetime

# Set page configuration
st.set_page_config(
    page_title="Business Category Survey",
    page_icon="📋",
    layout="wide"
)

# Database functions
def init_db():
    """Initialize SQLite database and create tables if they don't exist"""
    conn = sqlite3.connect('survey_data.db')
    c = conn.cursor()
    
    # Create tables if they don't exist
    c.execute('''
    CREATE TABLE IF NOT EXISTS survey_responses (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        category TEXT NOT NULL,
        timestamp TEXT NOT NULL
    )
    ''')
    
    c.execute('''
    CREATE TABLE IF NOT EXISTS survey_answers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        response_id INTEGER NOT NULL,
        question TEXT NOT NULL,
        answer TEXT NOT NULL,
        FOREIGN KEY (response_id) REFERENCES survey_responses (id)
    )
    ''')
    
    conn.commit()
    conn.close()

def save_to_db(category, answers):
    """Save survey answers to SQLite database"""
    conn = sqlite3.connect('survey_data.db')
    c = conn.cursor()
    
    # Get current timestamp
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # Insert into survey_responses table
    c.execute(
        "INSERT INTO survey_responses (category, timestamp) VALUES (?, ?)",
        (category, timestamp)
    )
    
    # Get the response_id (last inserted row id)
    response_id = c.lastrowid
    
    # Insert answers into survey_answers table
    for question, answer in answers.items():
        c.execute(
            "INSERT INTO survey_answers (response_id, question, answer) VALUES (?, ?, ?)",
            (response_id, question, answer)
        )
    
    conn.commit()
    conn.close()
    
    return response_id

def get_recent_responses(limit=10):
    """Get recent survey responses from the database"""
    conn = sqlite3.connect('survey_data.db')
    c = conn.cursor()
    
    # Get recent responses
    c.execute('''
    SELECT id, category, timestamp FROM survey_responses 
    ORDER BY timestamp DESC LIMIT ?
    ''', (limit,))
    
    responses = [{"id": row[0], "category": row[1], "timestamp": row[2]} for row in c.fetchall()]
    
    conn.close()
    return responses

def get_response_details(response_id):
    """Get details for a specific response"""
    conn = sqlite3.connect('survey_data.db')
    c = conn.cursor()
    
    # Get response info
    c.execute("SELECT category, timestamp FROM survey_responses WHERE id = ?", (response_id,))
    response_info = c.fetchone()
    
    if not response_info:
        conn.close()
        return None
    
    # Get answers for this response
    c.execute("SELECT question, answer FROM survey_answers WHERE response_id = ?", (response_id,))
    answers = {row[0]: row[1] for row in c.fetchall()}
    
    conn.close()
    
    return {
        "id": response_id,
        "category": response_info[0],
        "timestamp": response_info[1],
        "answers": answers
    }

# Function to load the JSON data
@st.cache_data
def load_data():
    try:
        with open('data.json', 'r', encoding='utf-8') as file:
            return json.load(file)
    except FileNotFoundError:
        st.error("Error: data.json file not found in the current directory.")
        return {"business_categories": []}

# Initialize database
init_db()

# Load the data
data = load_data()

# Sidebar navigation
st.sidebar.title("القائمة")
page = st.sidebar.radio("اختر الصفحة", ["الاستبيان", "عرض النتائج السابقة"])

# Extract categories
categories = [category["category"] for category in data["business_categories"]]

# Add information to sidebar
with st.sidebar:
    st.header("معلومات")
    st.write("هذا التطبيق يساعدك على اختيار فئة الأعمال وتقديم إجابات على الأسئلة المتعلقة بها.")
    st.write("سيتم حفظ الإجابات في قاعدة بيانات SQLite.")
    
    st.subheader("الفئات المتاحة:")
    for category in categories:
        st.write(f"- {category}")

# Main app - Survey Page
if page == "الاستبيان":
    st.title("استبيان الأعمال التجارية")
    st.markdown("### اختر فئة العمل وأجب على الأسئلة")

    # Add a select box for categories
    selected_category = st.selectbox("اختر الفئة", categories, index=0)

    # Find the selected category data
    selected_category_data = next(
        (category for category in data["business_categories"] if category["category"] == selected_category),
        None
    )

    if selected_category_data:
        st.subheader(f"أسئلة عن: {selected_category_data['category']}")
        
        # Create a form
        with st.form(key='survey_form'):
            # Dictionary to store answers
            answers = {}
            
            # Display each question with its options
            for i, q in enumerate(selected_category_data["questions"]):
                question = q["question"]
                options = q["options"]
                
                # Create a unique key for each radio button
                key = f"question_{i}"
                
                # Display the question and options
                st.write(f"**{i+1}. {question}**")
                answer = st.radio(
                    "اختر إجابة",
                    options,
                    key=key,
                    label_visibility="collapsed"
                )
                
                # Add to answers dictionary
                answers[question] = answer
                
                # Add a separator
                st.divider()
            
            # Submit button
            submit_button = st.form_submit_button("حفظ الإجابات")
            
            if submit_button:
                response_id = save_to_db(selected_category, answers)
                st.success(f"تم حفظ الإجابات بنجاح في قاعدة البيانات برقم: {response_id}")
                
                # Display the answers
                st.subheader("الإجابات المقدمة:")
                for question, answer in answers.items():
                    st.write(f"**{question}:** {answer}")
    else:
        st.error("لم يتم العثور على الفئة المحددة.")

# Results Page
elif page == "عرض النتائج السابقة":
    st.title("نتائج الاستبيانات السابقة")
    
    # Get recent responses
    recent_responses = get_recent_responses(20)
    
    if not recent_responses:
        st.info("لا توجد استبيانات سابقة.")
    else:
        st.write(f"عدد الاستبيانات المحفوظة: {len(recent_responses)}")
        
        # Create a table of recent responses
        st.subheader("الاستبيانات الأخيرة")
        response_data = {
            "ID": [r["id"] for r in recent_responses],
            "الفئة": [r["category"] for r in recent_responses],
            "التاريخ والوقت": [r["timestamp"] for r in recent_responses]
        }
        st.dataframe(response_data, width=800)
        
        # Allow viewing a specific response
        st.subheader("عرض تفاصيل استبيان")
        response_id = st.number_input("أدخل رقم الاستبيان للعرض", min_value=1, step=1)
        
        if st.button("عرض التفاصيل"):
            response_details = get_response_details(response_id)
            if response_details:
                st.write(f"**الفئة:** {response_details['category']}")
                st.write(f"**التاريخ والوقت:** {response_details['timestamp']}")
                
                st.subheader("الإجابات:")
                for question, answer in response_details["answers"].items():
                    st.write(f"**{question}:** {answer}")
            else:
                st.error(f"لم يتم العثور على استبيان برقم {response_id}")