import streamlit as st
import json
import sqlite3
import os
import pandas as pd
import io
import base64
from datetime import datetime
import streamlit.components.v1 as components

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

# Function to get geolocation
def get_location():
    """Get user's geolocation using HTML component"""
    # Create container for location info
    location_container = st.empty()
    
    # Create HTML component with geolocation functionality
    geolocation_html = """
    <div style="margin-bottom: 10px;">
        <button 
            id="get-location-btn" 
            style="background-color: #0366d6; color: white; padding: 10px 16px; 
                   border: none; border-radius: 4px; cursor: pointer; font-weight: bold;"
            onclick="getLocation()">
            📍 تحديد الموقع الحالي
        </button>
        <div id="location-status" style="margin-top: 8px; font-size: 14px;"></div>
    </div>
    
    <script>
    function getLocation() {
        // Update status
        document.getElementById('location-status').innerHTML = 
            '<div style="padding: 8px; background-color: #e3f2fd; border-radius: 4px; text-align: right;">جاري تحديد الموقع...</div>';
        
        if (navigator.geolocation) {
            navigator.geolocation.getCurrentPosition(
                function(position) {
                    // Success - get coordinates
                    const lat = position.coords.latitude;
                    const lng = position.coords.longitude;
                    
                    // Save to local storage
                    localStorage.setItem('survey_latitude', lat);
                    localStorage.setItem('survey_longitude', lng);
                    
                    // Update status display
                    document.getElementById('location-status').innerHTML = 
                        '<div style="padding: 8px; background-color: #e8f5e9; border-radius: 4px; text-align: right;">' +
                        'تم تحديد الموقع بنجاح! خط العرض: ' + lat + ', خط الطول: ' + lng + '</div>';
                    
                    // Submit coordinates to Streamlit via URL parameters and reload
                    const url = new URL(window.location.href);
                    url.searchParams.set('lat', lat);
                    url.searchParams.set('lng', lng);
                    window.location.href = url.toString();
                },
                function(error) {
                    // Handle errors
                    let errorMessage = 'حدث خطأ أثناء محاولة تحديد الموقع.';
                    switch(error.code) {
                        case error.PERMISSION_DENIED:
                            errorMessage = 'تم رفض إذن الوصول إلى الموقع.';
                            break;
                        case error.POSITION_UNAVAILABLE:
                            errorMessage = 'معلومات الموقع غير متاحة.';
                            break;
                        case error.TIMEOUT:
                            errorMessage = 'انتهت مهلة طلب الموقع.';
                            break;
                    }
                    document.getElementById('location-status').innerHTML = 
                        '<div style="padding: 8px; background-color: #ffebee; border-radius: 4px; text-align: right;">' +
                        errorMessage + '</div>';
                }
            );
        } else {
            document.getElementById('location-status').innerHTML = 
                '<div style="padding: 8px; background-color: #ffebee; border-radius: 4px; text-align: right;">' +
                'المتصفح لا يدعم خدمة تحديد الموقع.</div>';
        }
    }
    
    // Check if we have coordinates in localStorage when page loads
    document.addEventListener('DOMContentLoaded', function() {
        const urlParams = new URLSearchParams(window.location.search);
        if (urlParams.has('lat') && urlParams.has('lng')) {
            // We have coordinates from URL
            const lat = urlParams.get('lat');
            const lng = urlParams.get('lng');
            document.getElementById('location-status').innerHTML = 
                '<div style="padding: 8px; background-color: #e8f5e9; border-radius: 4px; text-align: right;">' +
                'تم تحديد الموقع بنجاح! خط العرض: ' + lat + ', خط الطول: ' + lng + '</div>';
        } else {
            // Check localStorage
            const lat = localStorage.getItem('survey_latitude');
            const lng = localStorage.getItem('survey_longitude');
            if (lat && lng) {
                document.getElementById('location-status').innerHTML = 
                    '<div style="padding: 8px; background-color: #e8f5e9; border-radius: 4px; text-align: right;">' +
                    'تم تحديد الموقع سابقًا! خط العرض: ' + lat + ', خط الطول: ' + lng + '</div>';
            }
        }
    });
    </script>
    """
    
    # Render HTML component
    components.html(geolocation_html, height=100)
    
    # Check URL parameters for coordinates
    query_params = st.experimental_get_query_params()
    latitude = None
    longitude = None
    
    if 'lat' in query_params and 'lng' in query_params:
        latitude = query_params['lat'][0]
        longitude = query_params['lng'][0]
        
        # Store in session state
        st.session_state.latitude = latitude
        st.session_state.longitude = longitude
        
        # Clear URL parameters
        cleaned_params = {k: v for k, v in query_params.items() if k not in ['lat', 'lng']}
        st.experimental_set_query_params(**cleaned_params)
        
        # Show map with location
        with location_container:
            st.success(f"تم تحديد الموقع: خط العرض: {latitude}, خط الطول: {longitude}")
            
            # Show map
            try:
                st.map(pd.DataFrame({
                    'lat': [float(latitude)], 
                    'lon': [float(longitude)]
                }))
            except:
                st.error("تعذر عرض الخريطة. تأكد من صحة الإحداثيات.")
    
    # Alternative manual input
    if st.checkbox("إدخال الإحداثيات يدويًا", key="manual_geo_input"):
        col1, col2 = st.columns(2)
        with col1:
            manual_lat = st.text_input("خط العرض (Latitude)", key="manual_lat_input")
        with col2:
            manual_lng = st.text_input("خط الطول (Longitude)", key="manual_lng_input")
            
        if st.button("استخدام الإحداثيات المدخلة", key="use_manual_coords"):
            if manual_lat and manual_lng:
                try:
                    # Validate coordinates
                    lat_float = float(manual_lat)
                    lng_float = float(manual_lng)
                    
                    if -90 <= lat_float <= 90 and -180 <= lng_float <= 180:
                        st.session_state.latitude = manual_lat
                        st.session_state.longitude = manual_lng
                        st.experimental_rerun()
                    else:
                        st.error("قيم غير صالحة للإحداثيات. يجب أن يكون خط العرض بين -90 و 90، وخط الطول بين -180 و 180.")
                except ValueError:
                    st.error("يرجى إدخال أرقام صالحة للإحداثيات.")
    
    return latitude, longitude

# Initialize the database
init_database()

# Load the data
data = load_data()

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
    
    # Get location
    st.subheader("تحديد الموقع")
    st.markdown("يمكنك تحديد الموقع الحالي لحفظه مع الاستبيان.")
    latitude, longitude = get_location()
    
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
                # Validate merchant name
                if not merchant_name:
                    st.error("يرجى إدخال اسم التاجر")
                else:
                    # Get latest location data from session state
                    lat = st.session_state.get('latitude', latitude)
                    lng = st.session_state.get('longitude', longitude)
                    
                    # Save to database
                    response_id = save_survey(selected_category, merchant_name, answers, lat, lng)
                    
                    if response_id:
                        st.success(f"تم حفظ الإجابات بنجاح في قاعدة البيانات برقم: {response_id}")
                        
                        # Display the answers
                        st.subheader("الإجابات المقدمة:")
                        st.write(f"**اسم التاجر:** {merchant_name}")
                        
                        # Display location if available
                        if lat and lng:
                            st.write(f"**الموقع:** خط العرض: {lat}, خط الطول: {lng}")
                            
                            # Display map if coordinates are available
                            st.map(pd.DataFrame({'lat': [float(lat)], 'lon': [float(lng)]}))
                        
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
                            "latitude": lat,
                            "longitude": lng,
                            "answers": answers
                        }
                        
                        # Create JSON download
                        json_filename = f"survey_{response_id}_{selected_category.replace(' ', '_')}.json"
                        json_link = create_json_download_link(response_data, json_filename, "تحميل كملف JSON")
                        st.markdown(json_link, unsafe_allow_html=True)
                        
                        # Create Excel download
                        df = pd.DataFrame(
                            [[response_id, selected_category, merchant_name, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), lat, lng]], 
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