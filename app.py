import streamlit as st
import json
import os
from datetime import datetime

# Set page configuration
st.set_page_config(
    page_title="Business Category Survey",
    page_icon="📋",
    layout="wide"
)

# Function to load the JSON data
@st.cache_data
def load_data():
    try:
        with open('data.json', 'r', encoding='utf-8') as file:
            return json.load(file)
    except FileNotFoundError:
        st.error("Error: data.json file not found in the current directory.")
        return {"business_categories": []}

# Function to save answers
def save_answers(category, answers):
    # Create a filename with timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"survey_answers_{timestamp}.json"
    
    # Prepare data structure
    data = {
        "category": category,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "answers": answers
    }
    
    # Save to file
    with open(filename, 'w', encoding='utf-8') as file:
        json.dump(data, file, ensure_ascii=False, indent=4)
    
    return filename

# Load the data
data = load_data()

# Main app
st.title("استبيان الأعمال التجارية")
st.markdown("### اختر فئة العمل وأجب على الأسئلة")

# Extract categories
categories = [category["category"] for category in data["business_categories"]]

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
            filename = save_answers(selected_category, answers)
            st.success(f"تم حفظ الإجابات بنجاح في الملف: {filename}")
            
            # Display the answers
            st.subheader("الإجابات المقدمة:")
            for question, answer in answers.items():
                st.write(f"**{question}:** {answer}")
else:
    st.error("لم يتم العثور على الفئة المحددة.")

# Add a sidebar with information
with st.sidebar:
    st.header("معلومات")
    st.write("هذا التطبيق يساعدك على اختيار فئة الأعمال وتقديم إجابات على الأسئلة المتعلقة بها.")
    st.write("بعد الانتهاء، سيتم حفظ الإجابات في ملف JSON.")
    
    st.subheader("الفئات المتاحة:")
    for category in categories:
        st.write(f"- {category}")