import streamlit as st
import json
import base64
import re
import pandas as pd
import io

def extract_jsonp_content(file_content):
    """
    Extract the base64 encoded content from the und.js file that starts with
    __resolveJsonp("course:und","....").
    
    Args:
        file_content (str): Content of the und.js file
    
    Returns:
        str: Extracted base64 content or None if not found
    """
    # Pattern to match __resolveJsonp("course:und","....") format
    pattern = r'__resolveJsonp\("course:und","([^"]+)"\)'
    match = re.search(pattern, file_content)
    
    if match:
        return match.group(1)
    return None

def decode_base64_content(base64_content):
    """
    Decode base64 content to JSON.
    
    Args:
        base64_content (str): Base64 encoded content
    
    Returns:
        dict: Decoded JSON data or None if decoding fails
    """
    try:
        # Decode base64 to get JSON string
        decoded_bytes = base64.b64decode(base64_content)
        json_str = decoded_bytes.decode('utf-8')
        
        # Parse JSON string
        json_data = json.loads(json_str)
        return json_data
    except Exception as e:
        st.error(f"Error decoding content: {str(e)}")
        return None

def extract_lesson_data(json_data):
    """
    Extract lesson titles and IDs from the decoded JSON data.
    
    Args:
        json_data (dict): The decoded JSON data
    
    Returns:
        list: List of dictionaries containing title and id for each lesson
    """
    lessons_data = []
    
    # Try to find lessons in the JSON structure
    if 'lessons' in json_data:
        lessons = json_data['lessons']
    else:
        # If not directly available, look through the data structure
        lessons = []
        # Check for any arrays that might contain lesson objects
        for key, value in json_data.items():
            if isinstance(value, list) and len(value) > 0:
                # Check if items in the list look like lessons (have title and id)
                if all('title' in item and 'id' in item for item in value[:2]):
                    lessons = value
                    break
    
    # Extract titles and IDs from lessons
    for lesson in lessons:
        if 'title' in lesson and 'id' in lesson:
            lessons_data.append({
                'title': lesson['title'],
                'id': lesson['id']
            })
    
    return lessons_data

def get_downloadable_csv(lessons_data):
    """
    Convert lessons data to CSV format for download.
    
    Args:
        lessons_data (list): List of lesson dictionaries
    
    Returns:
        str: CSV data as a string
    """
    df = pd.DataFrame(lessons_data)
    csv = df.to_csv(index=False)
    return csv

def main():
    st.title("Rise Course Lesson Extractor")
    
    st.write("""
    Upload your Rise course `und.js` file to extract lesson titles and IDs.
    
    The file should contain content in the format: `__resolveJsonp("course:und","...")` 
    where `...` is the base64 encoded course data.
    """)
    
    uploaded_file = st.file_uploader("Choose your und.js file", type=['js'])
    
    if uploaded_file is not None:
        # Read file content
        file_content = uploaded_file.getvalue().decode('utf-8')
        
        # Extract base64 content
        base64_content = extract_jsonp_content(file_content)
        
        if base64_content:
            with st.spinner("Decoding and extracting lesson data..."):
                # Decode base64 to get JSON
                json_data = decode_base64_content(base64_content)
                
                if json_data:
                    # Extract lesson titles and IDs
                    lessons_data = extract_lesson_data(json_data)
                    
                    if lessons_data:
                        st.success(f"Successfully extracted {len(lessons_data)} lessons!")
                        
                        # Display in a table
                        st.write("Extracted Lesson Information:")
                        lesson_df = pd.DataFrame(lessons_data)
                        st.dataframe(lesson_df)
                        
                        # Provide download links
                        csv = get_downloadable_csv(lessons_data)
                        st.download_button(
                            label="Download as CSV",
                            data=csv,
                            file_name="lesson_data.csv",
                            mime="text/csv"
                        )
                        
                        # Text output option
                        text_output = "\n".join([f"{lesson['title']} - {lesson['id']}" for lesson in lessons_data])
                        st.download_button(
                            label="Download as Text",
                            data=text_output,
                            file_name="lesson_data.txt",
                            mime="text/plain"
                        )
                    else:
                        st.warning("No lesson data found in the file.")
                else:
                    st.error("Failed to decode the base64 content.")
        else:
            st.error("Could not find the expected format in the file. Make sure it contains __resolveJsonp(\"course:und\",\"...\")")

if __name__ == "__main__":
    main()
