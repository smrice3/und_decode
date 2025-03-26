# Set page configuration MUST be the first Streamlit command
import streamlit as st
st.set_page_config(
    page_title="Rise IMSCC Creator",
    page_icon="📚",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Now import other libraries
import os
import tempfile
import base64
import json
import re
import pandas as pd
import sys
import io

# Import the IMSCC creator module - make sure imscc_creator.py is in the same directory
import imscc_creator

# Main title and description
st.title("Rise Course IMSCC Creator")
st.markdown("""
This tool helps you create IMS Common Cartridge packages from Rise course lesson data.
Upload your data, provide a base URL, and download an IMSCC package ready to import into your LMS.
""")

# Rest of your code...

# Create tabs for different input methods
tab1, tab2, tab3 = st.tabs(["Extract from und.js", "Upload CSV", "Upload JSON"])

with tab1:
    st.header("Extract from und.js")
    st.markdown("""
    Upload your Rise course `und.js` file to extract lesson data and create an IMSCC package.
    
    This file typically contains the encoded course structure and is located in the `data/` folder of your exported Rise package.
    """)
    
    und_file = st.file_uploader("Upload und.js file", type=["js"], key="und_uploader")
    
    if und_file:
        st.success(f"Uploaded: {und_file.name}")
        
        # Read file content
        file_content = und_file.getvalue().decode('utf-8')
        
        # Show file info
        file_size = len(file_content)
        st.write(f"File size: {file_size} bytes")
        
        # Extract base64 content
        with st.spinner("Extracting encoded data..."):
            # Use the extraction function from imscc_creator
            # First save the file to a temporary location
            with tempfile.NamedTemporaryFile(delete=False, suffix='.js') as temp_file:
                temp_file.write(und_file.getvalue())
                temp_path = temp_file.name
            
            try:
                base64_content = imscc_creator.extract_jsonp_content(temp_path)
                if base64_content:
                    st.success("Found encoded data in the file!")
                    
                    # Decode base64 to get JSON
                    with st.spinner("Decoding data..."):
                        json_data = imscc_creator.decode_base64_content(base64_content)
                        
                        if json_data:
                            # Extract lesson data
                            with st.spinner("Extracting lesson data..."):
                                lessons_data = imscc_creator.extract_lesson_data(json_data)
                                
                                if lessons_data:
                                    st.success(f"Successfully extracted {len(lessons_data)} lessons!")
                                    
                                    # Display in a table
                                    st.write("Extracted Lesson Information:")
                                    lesson_df = pd.DataFrame(lessons_data)
                                    st.dataframe(lesson_df)
                                    
                                    # Course title input
                                    course_title = st.text_input(
                                        "Course title",
                                        value=json_data.get('title', 'Rise Course Export')
                                    )
                                    
                                    # Base URL input
                                    base_url = st.text_input(
                                        "Base URL for iframes (will be combined with lesson IDs)",
                                        placeholder="https://example.com/rise/scorm/"
                                    )
                                    
                                    # Create IMSCC package button
                                    if st.button("Create IMSCC Package"):
                                        if not base_url:
                                            st.error("Please provide a base URL for the iframes.")
                                        else:
                                            with st.spinner("Creating IMSCC package..."):
                                                # Create a temporary directory for the output
                                                with tempfile.TemporaryDirectory() as temp_dir:
                                                    output_path = os.path.join(temp_dir, "rise_course.imscc")
                                                    
                                                    try:
                                                        # Create the IMSCC package using the imported function
                                                        imscc_creator.create_package(
                                                            lessons_data,
                                                            output_path,
                                                            base_url,
                                                            course_title=course_title
                                                        )
                                                        
                                                        # Read the created file for download
                                                        with open(output_path, "rb") as f:
                                                            imscc_bytes = f.read()
                                                        
                                                        st.success("IMSCC package created successfully!")
                                                        
                                                        # Provide download button
                                                        safe_filename = course_title.replace(' ', '_')
                                                        st.download_button(
                                                            label="Download IMSCC Package",
                                                            data=imscc_bytes,
                                                            file_name=f"{safe_filename}.imscc",
                                                            mime="application/zip"
                                                        )
                                                        
                                                        # Description of what was created
                                                        st.info(f"""
                                                        The IMSCC package contains {len(lessons_data)} pages, one for each lesson.
                                                        Each page has an iframe that points to: {base_url}/[lesson_id]
                                                        
                                                        This package can be imported into Canvas, Blackboard, Moodle, and other LMS 
                                                        systems that support IMS Common Cartridge format.
                                                        """)
                                                    except Exception as e:
                                                        st.error(f"Error creating IMSCC package: {str(e)}")
                                                        st.exception(e)
                                else:
                                    st.warning("No lesson data found in the file.")
                        else:
                            st.error("Failed to decode the base64 content.")
                else:
                    st.error("Could not find the expected format in the file.")
            except Exception as e:
                st.error(f"Error processing file: {str(e)}")
                st.exception(e)
            finally:
                # Clean up the temporary file
                if os.path.exists(temp_path):
                    os.remove(temp_path)

with tab2:
    st.header("Upload CSV")
    st.markdown("""
    Upload a CSV file containing lesson data with at least the following columns:
    - `id`: Unique identifier for each lesson
    - `title` (optional): Title of each lesson
    """)
    
    csv_file = st.file_uploader("Upload CSV file", type=["csv"], key="csv_uploader")
    
    if csv_file:
        st.success(f"Uploaded: {csv_file.name}")
        
        # Read CSV file
        try:
            df = pd.read_csv(csv_file)
            
            # Check if it has the required columns
            if 'id' not in df.columns:
                st.error("CSV file must contain an 'id' column.")
            else:
                # Display the data
                st.write("CSV Data:")
                st.dataframe(df)
                
                # Convert to the format expected by imscc_creator
                lessons_data = []
                for _, row in df.iterrows():
                    lesson = {'id': row['id']}
                    if 'title' in df.columns:
                        lesson['title'] = row['title']
                    else:
                        lesson['title'] = f"Lesson {row['id']}"
                    lessons_data.append(lesson)
                
                st.success(f"Found {len(lessons_data)} lessons in the CSV file.")
                
                # Course title input
                course_title = st.text_input(
                    "Course title",
                    value=os.path.splitext(csv_file.name)[0],
                    key="csv_title"
                )
                
                # Base URL input
                base_url = st.text_input(
                    "Base URL for iframes (will be combined with lesson IDs)",
                    placeholder="https://example.com/rise/scorm/",
                    key="csv_url"
                )
                
                # Create IMSCC package button
                if st.button("Create IMSCC Package", key="csv_button"):
                    if not base_url:
                        st.error("Please provide a base URL for the iframes.")
                    else:
                        with st.spinner("Creating IMSCC package..."):
                            # Create a temporary directory for the output
                            with tempfile.TemporaryDirectory() as temp_dir:
                                output_path = os.path.join(temp_dir, "rise_course.imscc")
                                
                                try:
                                    # Create the IMSCC package using the imported function
                                    imscc_creator.create_package(
                                        lessons_data,
                                        output_path,
                                        base_url,
                                        course_title=course_title
                                    )
                                    
                                    # Read the created file for download
                                    with open(output_path, "rb") as f:
                                        imscc_bytes = f.read()
                                    
                                    st.success("IMSCC package created successfully!")
                                    
                                    # Provide download button
                                    safe_filename = course_title.replace(' ', '_')
                                    st.download_button(
                                        label="Download IMSCC Package",
                                        data=imscc_bytes,
                                        file_name=f"{safe_filename}.imscc",
                                        mime="application/zip",
                                        key="csv_download"
                                    )
                                    
                                    # Description of what was created
                                    st.info(f"""
                                    The IMSCC package contains {len(lessons_data)} pages, one for each lesson.
                                    Each page has an iframe that points to: {base_url}/[lesson_id]
                                    
                                    This package can be imported into Canvas, Blackboard, Moodle, and other LMS 
                                    systems that support IMS Common Cartridge format.
                                    """)
                                except Exception as e:
                                    st.error(f"Error creating IMSCC package: {str(e)}")
                                    st.exception(e)
        
        except Exception as e:
            st.error(f"Error reading CSV file: {str(e)}")
            st.exception(e)

with tab3:
    st.header("Upload JSON")
    st.markdown("""
    Upload a JSON file containing lesson data. The JSON should either:
    - Be an array of objects with at least 'id' and optionally 'title' properties
    - Or be an object with a 'lessons' property that contains such an array
    """)
    
    json_file = st.file_uploader("Upload JSON file", type=["json"], key="json_uploader")
    
    if json_file:
        st.success(f"Uploaded: {json_file.name}")
        
        # Read JSON file
        try:
            json_data = json.load(json_file)
            
            # Check the structure and extract lessons array
            if isinstance(json_data, list):
                lessons_data = json_data
            elif isinstance(json_data, dict) and 'lessons' in json_data:
                lessons_data = json_data['lessons']
            else:
                # Try to find an array that looks like lessons
                lessons_data = None
                for key, value in json_data.items():
                    if isinstance(value, list) and len(value) > 0:
                        # Check if the first item has id and title
                        first_item = value[0]
                        if isinstance(first_item, dict) and 'id' in first_item:
                            lessons_data = value
                            st.info(f"Found lessons data in key: '{key}'")
                            break
            
            if not lessons_data:
                st.error("Could not find lesson data in the JSON file.")
            else:
                # Validate that all lessons have at least an id
                valid_lessons = [lesson for lesson in lessons_data if isinstance(lesson, dict) and 'id' in lesson]
                
                if len(valid_lessons) == 0:
                    st.error("No valid lessons found. Each lesson must have an 'id' property.")
                else:
                    # Display the data
                    st.write("JSON Data:")
                    st.json(valid_lessons[:5] if len(valid_lessons) > 5 else valid_lessons)
                    if len(valid_lessons) > 5:
                        st.write(f"... and {len(valid_lessons) - 5} more lessons")
                    
                    st.success(f"Found {len(valid_lessons)} lessons in the JSON file.")
                    
                    # Course title input
                    course_title = st.text_input(
                        "Course title",
                        value=os.path.splitext(json_file.name)[0] if json_file else "Rise Course Export",
                        key="json_title"
                    )
                    
                    # Base URL input
                    base_url = st.text_input(
                        "Base URL for iframes (will be combined with lesson IDs)",
                        placeholder="https://example.com/rise/scorm/",
                        key="json_url"
                    )
                    
                    # Create IMSCC package button
                    if st.button("Create IMSCC Package", key="json_button"):
                        if not base_url:
                            st.error("Please provide a base URL for the iframes.")
                        else:
                            with st.spinner("Creating IMSCC package..."):
                                # Create a temporary directory for the output
                                with tempfile.TemporaryDirectory() as temp_dir:
                                    output_path = os.path.join(temp_dir, "rise_course.imscc")
                                    
                                    try:
                                        # Create the IMSCC package using the imported function
                                        imscc_creator.create_package(
                                            valid_lessons,
                                            output_path,
                                            base_url,
                                            course_title=course_title
                                        )
                                        
                                        # Read the created file for download
                                        with open(output_path, "rb") as f:
                                            imscc_bytes = f.read()
                                        
                                        st.success("IMSCC package created successfully!")
                                        
                                        # Provide download button
                                        safe_filename = course_title.replace(' ', '_')
                                        st.download_button(
                                            label="Download IMSCC Package",
                                            data=imscc_bytes,
                                            file_name=f"{safe_filename}.imscc",
                                            mime="application/zip",
                                            key="json_download"
                                        )
                                        
                                        # Description of what was created
                                        st.info(f"""
                                        The IMSCC package contains {len(valid_lessons)} pages, one for each lesson.
                                        Each page has an iframe that points to: {base_url}/[lesson_id]
                                        
                                        This package can be imported into Canvas, Blackboard, Moodle, and other LMS 
                                        systems that support IMS Common Cartridge format.
                                        """)
                                    except Exception as e:
                                        st.error(f"Error creating IMSCC package: {str(e)}")
                                        st.exception(e)
        
        except Exception as e:
            st.error(f"Error reading JSON file: {str(e)}")
            st.exception(e)

# Add a sidebar with information and instructions
with st.sidebar:
    st.header("About IMSCC Creator")
    st.markdown("""
    This tool creates IMS Common Cartridge (.imscc) packages from Rise course lesson data.
    
    ### What is an IMSCC package?
    
    An IMS Common Cartridge is a standard format for sharing course content between different Learning Management Systems (LMS) like Canvas, Blackboard, and Moodle.
    
    ### What does this tool do?
    
    1. Extracts lesson information from Rise courses or uploaded data
    2. Creates a separate HTML page for each lesson with an iframe
    3. Packages everything into an IMSCC file that can be imported into an LMS
    
    ### How to use this tool:
    
    1. Choose an input method (und.js file, CSV, or JSON)
    2. Upload your data
    3. Provide a base URL that points to your Rise content
    4. Click "Create IMSCC Package"
    5. Download the generated package
    6. Import it into your LMS
    
    ### Base URL Format
    
    The base URL should point to where your Rise content is hosted, such that:
    - When combined with a lesson ID, it forms a valid URL
    - Example: if your lesson with ID "abc123" is at:
      `https://example.com/rise/abc123`
    - Then your base URL should be:
      `https://example.com/rise/`
    """)
    
    # Add a section for troubleshooting
    st.markdown("---")
    st.subheader("Troubleshooting")
    
    with st.expander("Common Issues"):
        st.markdown("""
        **Package not importing into LMS**
        - Ensure your LMS supports IMS Common Cartridge 1.1.0
        - Check that your base URL is correct and accessible
        
        **Lesson content not showing**
        - Make sure your Rise content is publicly accessible
        - Verify that your LMS allows iframes from external domains
        - Check browser console for cross-origin errors
        
        **File extraction issues**
        - Ensure you're using the correct und.js file from your Rise export
        - The file should contain the encoded course data
        """)
    
    st.markdown("---")
    st.caption("Created with the standalone IMSCC Creator")

# Add a help section at the bottom
st.markdown("---")
with st.expander("Need Help?"):
    st.markdown("""
    ### How to find your und.js file
    
    1. Export your Rise course as SCORM
    2. Unzip the exported package
    3. Navigate to the `data` folder
    4. Find the file named `und.js`
    
    ### How to create a CSV file
    
    Create a CSV file with at least these columns:
    - `id`: The unique identifier for each lesson
    - `title`: (Optional) The title of each lesson
    
    Example:
    ```
    id,title
    lesson1,Introduction
    lesson2,Chapter 1
    lesson3,Chapter 2
    ```
    
    ### How to import an IMSCC package
    
    **Canvas LMS**:
    1. Go to Settings > Import Course Content
    2. Select "Canvas Cartridge 1.x Package"
    3. Upload the .imscc file
    4. Run the import
    
    **Blackboard**:
    1. Go to Packages and Utilities > Import Package
    2. Upload the .imscc file
    3. Select content to import
    
    **Moodle**:
    1. Go to Site administration > Courses > Restore
    2. Upload the .imscc file
    3. Follow the restore process
    """)

# Initialize session state for analytics if needed
if 'visit_count' not in st.session_state:
    st.session_state.visit_count = 1
else:
    st.session_state.visit_count += 1
