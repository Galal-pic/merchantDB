import streamlit as st
import json
import sqlite3
import os
import pandas as pd
import io
import base64
from datetime import datetime

# Set page configuration
st.set_page_config(
    page_title="Business Category Survey",
    page_icon="📋",
    layout="wide"
)

# Helper functions for database operations
def get_db_path():
    """Get absolute path to the database file"""
    try:
        # Try to get the directory of the current file
        current_dir = os.path.dirname(os.path.abspath(__file__))
    except:
        # Fall back to current working directory
        current_dir = os.getcwd()
    
    return os.path.join(current_dir, 'survey_data.db')

def execute_query(query, params=None, fetch=False):
    """Execute a SQL query safely with proper error handling"""
    conn = None
    result = None
    
    try:
        db_path = get_db_path()
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        if params:
            cursor.execute(query, params)
        else:
            cursor.execute(query)
            
        if fetch:
            result = cursor.fetchall()
        else:
            conn.commit()
            result = cursor.lastrowid
            
    except sqlite3.Error as e:
        st.error(f"Database error: {e}")
        if conn:
            conn.rollback()
        return None
        
    finally:
        if conn:
            conn.close()
            
    return result

def init_database():
    """Create database tables if they don't exist"""
    # Create survey_responses table with merchant_name field and location fields
    execute_query('''
    CREATE TABLE IF NOT EXISTS survey_responses (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        category TEXT NOT NULL,
        merchant_name TEXT NOT NULL,
        timestamp TEXT NOT NULL,
        latitude TEXT,
        longitude TEXT
    )
    ''')
    
    # Create survey_answers table
    execute_query('''
    CREATE TABLE IF NOT EXISTS survey_answers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        response_id INTEGER NOT NULL,
        question TEXT NOT NULL,
        answer TEXT NOT NULL,
        FOREIGN KEY (response_id) REFERENCES survey_responses (id)
    )
    ''')
    
    # Test if we can insert and retrieve data
    test_connection()

def test_connection():
    """Test if we can write to and read from the database"""
    try:
        # Test insert
        execute_query(
            "INSERT INTO survey_responses (category, merchant_name, timestamp, latitude, longitude) VALUES (?, ?, ?, ?, ?)",
            ("Test Category", "Test Merchant", "2023-01-01 00:00:00", "0.0", "0.0")
        )
        
        # Test select
        result = execute_query(
            "SELECT id FROM survey_responses WHERE category = ?",
            ("Test Category",),
            fetch=True
        )
        
        if result:
            # Clean up test data
            execute_query(
                "DELETE FROM survey_responses WHERE category = ?",
                ("Test Category",)
            )
            return True
        return False
    except:
        return False

def save_survey(category, merchant_name, answers, latitude=None, longitude=None):
    """Save a survey response to the database"""
    # First insert the survey response
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    response_id = execute_query(
        "INSERT INTO survey_responses (category, merchant_name, timestamp, latitude, longitude) VALUES (?, ?, ?, ?, ?)",
        (category, merchant_name, timestamp, latitude, longitude)
    )
    
    if response_id:
        # Then insert all the answers
        for question, answer in answers.items():
            execute_query(
                "INSERT INTO survey_answers (response_id, question, answer) VALUES (?, ?, ?)",
                (response_id, question, answer)
            )
        return response_id
    return None

def get_recent_responses(limit=10):
    """Get recent survey responses"""
    result = execute_query(
        f"SELECT id, category, merchant_name, timestamp, latitude, longitude FROM survey_responses ORDER BY id DESC LIMIT {limit}",
        fetch=True
    )
    
    if result:
        return [{"id": row[0], "category": row[1], "merchant_name": row[2], "timestamp": row[3], "latitude": row[4], "longitude": row[5]} for row in result]
    return []

def get_response_details(response_id):
    """Get details for a specific response"""
    # Get response info
    response_info = execute_query(
        "SELECT category, merchant_name, timestamp, latitude, longitude FROM survey_responses WHERE id = ?",
        (response_id,),
        fetch=True
    )
    
    if not response_info:
        return None
        
    # Get answers
    answers_result = execute_query(
        "SELECT question, answer FROM survey_answers WHERE response_id = ?",
        (response_id,),
        fetch=True
    )
    
    answers = {row[0]: row[1] for row in answers_result} if answers_result else {}
    
    return {
        "id": response_id,
        "category": response_info[0][0],
        "merchant_name": response_info[0][1],
        "timestamp": response_info[0][2],
        "latitude": response_info[0][3],
        "longitude": response_info[0][4],
        "answers": answers
    }

def get_all_survey_data():
    """Get all survey data for export in a structured format"""
    # Get all survey responses
    responses = execute_query(
        "SELECT id, category, merchant_name, timestamp, latitude, longitude FROM survey_responses",
        fetch=True
    )
    
    if not responses:
        return None
    
    # Prepare data structure
    all_data = []
    
    for response in responses:
        response_id, category, merchant_name, timestamp, latitude, longitude = response
        
        # Get answers for this response
        answers_result = execute_query(
            "SELECT question, answer FROM survey_answers WHERE response_id = ?",
            (response_id,),
            fetch=True
        )
        
        answers = {row[0]: row[1] for row in answers_result} if answers_result else {}
        
        # Add to data structure
        all_data.append({
            "id": response_id,
            "category": category,
            "merchant_name": merchant_name,
            "timestamp": timestamp,
            "latitude": latitude,
            "longitude": longitude,
            "answers": answers
        })
    
    return all_data

# Download helpers
def create_download_link(df, filename, text):
    """Create a download link for a dataframe"""
    csv = df.to_csv(index=False)
    b64 = base64.b64encode(csv.encode()).decode()
    href = f'<a href="data:file/csv;base64,{b64}" download="{filename}">📥 {text}</a>'
    return href

def create_excel_download_link(df, filename, text):
    """Create a download link for an Excel file"""
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Data')
    excel_data = output.getvalue()
    b64 = base64.b64encode(excel_data).decode()
    href = f'<a href="data:application/vnd.openxmlformats-officedocument.spreadsheetml.sheet;base64,{b64}" download="{filename}">📥 {text}</a>'
    return href

def create_json_download_link(data, filename, text):
    """Create a download link for JSON data"""
    json_str = json.dumps(data, ensure_ascii=False, indent=2)
    b64 = base64.b64encode(json_str.encode('utf-8')).decode()
    href = f'<a href="data:file/json;base64,{b64}" download="{filename}">📥 {text}</a>'
    return href

def prepare_survey_dataframe(data):
    """Prepare a flattened dataframe from survey data"""
    # Start with basic info
    rows = []
    
    for item in data:
        row = {
            "ID": item["id"],
            "الفئة": item["category"],
            "اسم التاجر": item["merchant_name"],
            "التاريخ والوقت": item["timestamp"],
            "خط العرض": item["latitude"],
            "خط الطول": item["longitude"]
        }
        
        # Add all answers
        for question, answer in item["answers"].items():
            row[question] = answer
        
        rows.append(row)
    
    return pd.DataFrame(rows)

# Function to load the JSON data
@st.cache_data
def load_data():
    try:
        with open('data.json', 'r', encoding='utf-8') as file:
            return json.load(file)
    except FileNotFoundError:
        st.error("Error: data.json file not found in the current directory.")
        return {"business_categories": []}

# Initialize the database
init_database()

# Load the data
data = load_data()

# Create a component for geolocation
def geolocation_component():
    # Create a container for the location component
    container = st.container()
    
    # Initialize session state for location data if not exists
    if 'latitude' not in st.session_state:
        st.session_state.latitude = None
    if 'longitude' not in st.session_state:
        st.session_state.longitude = None
    
    # Callback for the button click
    def get_location():
        # This will be populated by JavaScript
        pass
    
    # Create a styled button
    with container:
        st.button("📍 تحديد الموقع الحالي", on_click=get_location, type="primary")
        
        # Show current location if available
        if st.session_state.latitude and st.session_state.longitude:
            st.info(f"**الموقع الحالي:** خط العرض: {st.session_state.latitude}, خط الطول: {st.session_state.longitude}")
            
            # Show a small map
            st.map(pd.DataFrame({
                'lat': [float(st.session_state.latitude)], 
                'lon': [float(st.session_state.longitude)]
            }), zoom=13)
    
    # Add JavaScript to handle geolocation
    st.markdown("""
    <script>
    // Geolocation handler
    document.addEventListener('DOMContentLoaded', function() {
        // Find the button
        const buttons = document.querySelectorAll('button');
        const locationButton = Array.from(buttons).find(button => 
            button.textContent.includes('تحديد الموقع الحالي')
        );
        
        if (locationButton) {
            locationButton.addEventListener('click', function() {
                if (navigator.geolocation) {
                    navigator.geolocation.getCurrentPosition(function(position) {
                        const lat = position.coords.latitude;
                        const lng = position.coords.longitude;
                        
                        // Send the location data to Streamlit
                        const data = {
                            latitude: lat,
                            longitude: lng
                        };
                        
                        // Set to session state via Streamlit's message passing
                        window.parent.postMessage({
                            type: "streamlit:setComponentValue",
                            value: data
                        }, "*");
                    }, function(error) {
                        console.error("Error getting location:", error);
                        alert("حدث خطأ أثناء محاولة تحديد الموقع: " + error.message);
                    }, {
                        enableHighAccuracy: true,
                        timeout: 5000,
                        maximumAge: 0
                    });
                } else {
                    alert("المتصفح لا يدعم تحديد الموقع!");
                }
            });
        }
    });
    </script>
    """, unsafe_allow_html=True)
    
    return container

# Call the geolocation component
geolocation_component()

# Sidebar navigation
st.sidebar.title("القائمة")
page = st.sidebar.radio("اختر الصفحة", ["الاستبيان", "عرض النتائج السابقة", "تحميل البيانات"])

# Extract categories
categories = [category["category"] for category in data["business_categories"]]

# Add information to sidebar
with st.sidebar:
    st.header("معلومات")
    st.write("هذا التطبيق يساعدك على اختيار فئة الأعمال وتقديم إجابات على الأسئلة المتعلقة بها.")
    st.write("سيتم حفظ الإجابات في قاعدة بيانات SQLite.")
    
    # Database path info
    if st.checkbox("عرض معلومات قاعدة البيانات"):
        st.code(f"مسار قاعدة البيانات: {get_db_path()}")
        
        # Test database connection
        if st.button("اختبار الاتصال بقاعدة البيانات"):
            if test_connection():
                st.success("تم الاتصال بقاعدة البيانات بنجاح!")
            else:
                st.error("فشل الاتصال بقاعدة البيانات!")

# Main app - Survey Page
if page == "الاستبيان":
    st.title("استبيان الأعمال التجارية")
    st.markdown("### اختر فئة العمل وأدخل اسم التاجر وأجب على الأسئلة")

    # Add a select box for categories
    selected_category = st.selectbox("اختر الفئة", categories, index=0)
    
    # Add field for merchant name
    merchant_name = st.text_input("أدخل اسم التاجر", "")
    
    # Create placeholders for latitude and longitude
    latitude_placeholder = st.empty()
    longitude_placeholder = st.empty()
    
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
            
            # Get latitude and longitude from session state if available
            latitude = st.session_state.get('latitude', None)
            longitude = st.session_state.get('longitude', None)
            
            # Hidden fields for location data
            latitude_input = st.text_input("Latitude", key="lat_input", value=latitude, label_visibility="collapsed")
            longitude_input = st.text_input("Longitude", key="lng_input", value=longitude, label_visibility="collapsed")
            
            # JavaScript callback to set session state
            st.markdown('''
            <script>
            // Get the values from hidden inputs when form loads
            document.addEventListener('DOMContentLoaded', function() {
                const lat = document.getElementById('latitude').value;
                const lng = document.getElementById('longitude').value;
                
                if (lat && lng) {
                    const latInput = document.querySelector('input[data-testid="stTextInput"][aria-label="Latitude"]');
                    const lngInput = document.querySelector('input[data-testid="stTextInput"][aria-label="Longitude"]');
                    
                    if (latInput && lngInput) {
                        latInput.value = lat;
                        lngInput.value = lng;
                        
                        // Trigger change event
                        const event = new Event('change', { bubbles: true });
                        latInput.dispatchEvent(event);
                        lngInput.dispatchEvent(event);
                    }
                }
            });
            </script>
            ''', unsafe_allow_html=True)
            
            # Submit button
            submit_button = st.form_submit_button("حفظ الإجابات")
            
            if submit_button:
                # Validate merchant name
                if not merchant_name:
                    st.error("يرجى إدخال اسم التاجر")
                else:
                    # Get location data from session state
                    latitude = st.session_state.latitude if 'latitude' in st.session_state else None
                    longitude = st.session_state.longitude if 'longitude' in st.session_state else None
                    
                    # Save to database
                    response_id = save_survey(selected_category, merchant_name, answers, latitude, longitude)
                    
                    if response_id:
                        st.success(f"تم حفظ الإجابات بنجاح في قاعدة البيانات برقم: {response_id}")
                        
                        # Display the answers
                        st.subheader("الإجابات المقدمة:")
                        st.write(f"**اسم التاجر:** {merchant_name}")
                        
                        # Display location if available
                        if latitude and longitude:
                            st.write(f"**الموقع:** خط العرض: {latitude}, خط الطول: {longitude}")
                            
                            # Display map if coordinates are available
                            st.map(pd.DataFrame({'lat': [float(latitude)], 'lon': [float(longitude)]}))
                        
                        for question, answer in answers.items():
                            st.write(f"**{question}:** {answer}")
                        
                        # Create download links for this survey
                        st.subheader("تحميل هذا الاستبيان:")
                        
                        # Prepare data
                        response_data = {
                            "id": response_id,
                            "category": selected_category,
                            "merchant_name": merchant_name,
                            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                            "latitude": latitude,
                            "longitude": longitude,
                            "answers": answers
                        }
                        
                        # Create JSON download
                        json_filename = f"survey_{response_id}_{selected_category.replace(' ', '_')}.json"
                        json_link = create_json_download_link(response_data, json_filename, "تحميل كملف JSON")
                        st.markdown(json_link, unsafe_allow_html=True)
                        
                        # Create Excel download
                        df = pd.DataFrame(
                            [[response_id, selected_category, merchant_name, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), latitude, longitude]], 
                            columns=["ID", "الفئة", "اسم التاجر", "التاريخ والوقت", "خط العرض", "خط الطول"]
                        )
                        # Add answers as columns
                        for question, answer in answers.items():
                            df[question] = answer
                        
                        excel_filename = f"survey_{response_id}_{selected_category.replace(' ', '_')}.xlsx"
                        excel_link = create_excel_download_link(df, excel_filename, "تحميل كملف Excel")
                        st.markdown(excel_link, unsafe_allow_html=True)
                    else:
                        st.error("حدث خطأ أثناء حفظ الإجابات. يرجى المحاولة مرة أخرى.")
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
            "اسم التاجر": [r["merchant_name"] for r in recent_responses],
            "التاريخ والوقت": [r["timestamp"] for r in recent_responses],
            "خط العرض": [r["latitude"] for r in recent_responses],
            "خط الطول": [r["longitude"] for r in recent_responses]
        }
        st.dataframe(response_data, width=800)
        
        # Allow viewing a specific response
        st.subheader("عرض تفاصيل استبيان")
        response_id = st.number_input("أدخل رقم الاستبيان للعرض", min_value=1, step=1)
        
        if st.button("عرض التفاصيل"):
            response_details = get_response_details(response_id)
            if response_details:
                col1, col2 = st.columns(2)
                
                with col1:
                    st.write(f"**الفئة:** {response_details['category']}")
                    st.write(f"**اسم التاجر:** {response_details['merchant_name']}")
                    st.write(f"**التاريخ والوقت:** {response_details['timestamp']}")
                    
                    # Display location if available
                    if response_details['latitude'] and response_details['longitude']:
                        st.write(f"**الموقع:** خط العرض: {response_details['latitude']}, خط الطول: {response_details['longitude']}")
                        
                        # Display map
                        st.map(pd.DataFrame({
                            'lat': [float(response_details['latitude'])], 
                            'lon': [float(response_details['longitude'])]
                        }))
                
                with col2:
                    # Download options for this response
                    st.write("**تحميل هذا الاستبيان:**")
                    
                    # JSON download
                    json_filename = f"survey_{response_id}_{response_details['category'].replace(' ', '_')}.json"
                    json_link = create_json_download_link(response_details, json_filename, "تحميل كملف JSON")
                    st.markdown(json_link, unsafe_allow_html=True)
                    
                    # Create dataframe for Excel
                    df = pd.DataFrame(
                        [[
                            response_id, 
                            response_details['category'], 
                            response_details['merchant_name'], 
                            response_details['timestamp'],
                            response_details['latitude'],
                            response_details['longitude']
                        ]], 
                        columns=["ID", "الفئة", "اسم التاجر", "التاريخ والوقت", "خط العرض", "خط الطول"]
                    )
                    # Add answers as columns
                    for question, answer in response_details['answers'].items():
                        df[question] = answer
                    
                    # Excel download
                    excel_filename = f"survey_{response_id}_{response_details['category'].replace(' ', '_')}.xlsx"
                    excel_link = create_excel_download_link(df, excel_filename, "تحميل كملف Excel")
                    st.markdown(excel_link, unsafe_allow_html=True)
                
                st.subheader("الإجابات:")
                for question, answer in response_details["answers"].items():
                    st.write(f"**{question}:** {answer}")
            else:
                st.error(f"لم يتم العثور على استبيان برقم {response_id}")

# Download Page
elif page == "تحميل البيانات":
    st.title("تحميل بيانات الاستبيانات")
    
    # Get all data
    all_data = get_all_survey_data()
    
    if not all_data:
        st.info("لا توجد بيانات للتحميل.")
    else:
        st.write(f"إجمالي عدد الاستبيانات: {len(all_data)}")
        
        st.subheader("تحميل جميع البيانات")
        
        # Format selection
        format_option = st.radio(
            "اختر صيغة التحميل:",
            ["Excel (ملف واحد)", "CSV (ملف واحد)", "JSON (ملف واحد)"]
        )
        
        # Create timestamp for filenames
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        if format_option == "Excel (ملف واحد)":
            # Create a flattened dataframe
            df = prepare_survey_dataframe(all_data)
            
            # Create the download link
            excel_filename = f"all_surveys_{timestamp}.xlsx"
            excel_link = create_excel_download_link(df, excel_filename, "تحميل جميع البيانات كملف Excel")
            st.markdown(excel_link, unsafe_allow_html=True)
            
        elif format_option == "CSV (ملف واحد)":
            # Create a flattened dataframe
            df = prepare_survey_dataframe(all_data)
            
            # Create the download link
            csv_filename = f"all_surveys_{timestamp}.csv"
            csv_link = create_download_link(df, csv_filename, "تحميل جميع البيانات كملف CSV")
            st.markdown(csv_link, unsafe_allow_html=True)
            
        else:  # JSON
            # Create the download link
            json_filename = f"all_surveys_{timestamp}.json"
            json_link = create_json_download_link(all_data, json_filename, "تحميل جميع البيانات كملف JSON")
            st.markdown(json_link, unsafe_allow_html=True)
        
        # Filter options
        st.subheader("تصفية البيانات حسب الفئة")
        
        # Get unique categories
        unique_categories = list(set(item["category"] for item in all_data))
        
        selected_category = st.selectbox(
            "اختر الفئة للتحميل",
            unique_categories
        )
        
        # Filter data by category
        filtered_data = [item for item in all_data if item["category"] == selected_category]
        
        if filtered_data:
            st.write(f"عدد الاستبيانات في الفئة '{selected_category}': {len(filtered_data)}")
            
            # Create download links for filtered data
            df_filtered = prepare_survey_dataframe(filtered_data)
            
            # Excel download
            excel_filename = f"{selected_category.replace(' ', '_')}_{timestamp}.xlsx"
            excel_link = create_excel_download_link(df_filtered, excel_filename, f"تحميل بيانات '{selected_category}' كملف Excel")
            st.markdown(excel_link, unsafe_allow_html=True)
            
            # CSV download
            csv_filename = f"{selected_category.replace(' ', '_')}_{timestamp}.csv"
            csv_link = create_download_link(df_filtered, csv_filename, f"تحميل بيانات '{selected_category}' كملف CSV")
            st.markdown(csv_link, unsafe_allow_html=True)
            
            # JSON download
            json_filename = f"{selected_category.replace(' ', '_')}_{timestamp}.json"
            json_link = create_json_download_link(filtered_data, json_filename, f"تحميل بيانات '{selected_category}' كملف JSON")
            st.markdown(json_link, unsafe_allow_html=True)
            
        # Filter options by merchant name
        st.subheader("تصفية البيانات حسب اسم التاجر")
        
        # Get unique merchant names
        unique_merchants = list(set(item["merchant_name"] for item in all_data))
        
        selected_merchant = st.selectbox(
            "اختر اسم التاجر للتحميل",
            unique_merchants
        )
        
        # Filter data by merchant name
        filtered_by_merchant = [item for item in all_data if item["merchant_name"] == selected_merchant]
        
        if filtered_by_merchant:
            st.write(f"عدد الاستبيانات للتاجر '{selected_merchant}': {len(filtered_by_merchant)}")
            
            # Create download links for filtered data
            df_filtered_merchant = prepare_survey_dataframe(filtered_by_merchant)
            
            # Excel download
            excel_filename = f"merchant_{selected_merchant.replace(' ', '_')}_{timestamp}.xlsx"
            excel_link = create_excel_download_link(df_filtered_merchant, excel_filename, f"تحميل بيانات التاجر '{selected_merchant}' كملف Excel")
            st.markdown(excel_link, unsafe_allow_html=True)
            
            # CSV download
            csv_filename = f"merchant_{selected_merchant.replace(' ', '_')}_{timestamp}.csv"
            csv_link = create_download_link(df_filtered_merchant, csv_filename, f"تحميل بيانات التاجر '{selected_merchant}' كملف CSV")
            st.markdown(csv_link, unsafe_allow_html=True)
            
            # JSON download
            json_filename = f"merchant_{selected_merchant.replace(' ', '_')}_{timestamp}.json"
            json_link = create_json_download_link(filtered_by_merchant, json_filename, f"تحميل بيانات التاجر '{selected_merchant}' كملف JSON")
            st.markdown(json_link, unsafe_allow_html=True)

# Add JavaScript component to handle geolocation
components_js = """
<script>
// Check for geolocation data in URL params on page load
document.addEventListener('DOMContentLoaded', function() {
    // Try to read from hidden input fields
    const urlParams = new URLSearchParams(window.location.search);
    const lat = urlParams.get('lat');
    const lng = urlParams.get('lng');
    
    if (lat && lng) {
        // Set values in hidden fields
        document.getElementById('latitude').value = lat;
        document.getElementById('longitude').value = lng;
        
        // Update display
        const latDisplay = document.getElementById('lat-display');
        const lngDisplay = document.getElementById('lng-display');
        
        if (latDisplay && lngDisplay) {
            latDisplay.textContent = lat;
            lngDisplay.textContent = lng;
            document.getElementById('location-container').style.display = 'block';
        }
    }
});

// Function to update Streamlit form inputs when location is captured
function updateLocationInputs(lat, lng) {
    // Find the Streamlit text inputs for latitude and longitude
    const latInput = document.querySelector('input[data-testid="stTextInput"][aria-label="Latitude"]');
    const lngInput = document.querySelector('input[data-testid="stTextInput"][aria-label="Longitude"]');
    
    if (latInput && lngInput) {
        // Set the values
        latInput.value = lat;
        lngInput.value = lng;
        
        // Trigger change events to update Streamlit's state
        const event = new Event('input', { bubbles: true });
        latInput.dispatchEvent(event);
        lngInput.dispatchEvent(event);
    }
}

// Listen for clicks on the location button
document.addEventListener('click', function(e) {
    if (e.target && e.target.matches('button') && e.target.textContent.includes('تحديد الموقع الحالي')) {
        e.preventDefault();
        
        if (navigator.geolocation) {
            navigator.geolocation.getCurrentPosition(function(position) {
                const lat = position.coords.latitude;
                const lng = position.coords.longitude;
                
                // Update hidden fields
                document.getElementById('latitude').value = lat;
                document.getElementById('longitude').value = lng;
                
                // Update display
                document.getElementById('lat-display').textContent = lat;
                document.getElementById('lng-display').textContent = lng;
                document.getElementById('location-container').style.display = 'block';
                
                // Update Streamlit inputs
                updateLocationInputs(lat, lng);
                
                // Rerun Streamlit app to update state
                window.parent.postMessage({
                    type: "streamlit:setComponentValue",
                    value: { latitude: lat, longitude: lng }
                }, "*");
            });
        } else {
            alert("المتصفح لا يدعم تحديد الموقع!");
        }
    }
});
</script>
"""

st.components.v1.html(components_js, height=0)