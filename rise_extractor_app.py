import streamlit as st
import json
import base64
import re
import pandas as pd
import io
from collections import Counter
import os
import tempfile
import traceback
import sys

# Set page config first - must be the first Streamlit command
st.set_page_config(
    page_title="Rise Course Extractor",
    page_icon="📚",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Setup error logging
st.write("Starting application initialization...")

# Import the IMSCC creator module with error handling
try:
    import imscc_creator
    st.success("Successfully imported imscc_creator module")
except Exception as e:
    st.error(f"Failed to import imscc_creator: {str(e)}")
    st.code(traceback.format_exc())
    st.warning("The application may not function correctly without the imscc_creator module.")

def extract_jsonp_content(file_content):
    """
    Extract the base64 encoded content from the und.js file that starts with
    __resolveJsonp("course:und","....").
    
    Args:
        file_content (str): Content of the und.js file
    
    Returns:
        str: Extracted base64 content or None if not found
    """
    try:
        # Pattern to match __resolveJsonp("course:und","....") format
        pattern = r'__resolveJsonp\("course:und","([^"]+)"\)'
        match = re.search(pattern, file_content)
        
        if match:
            return match.group(1)
        
        # Debug information
        st.error("Failed to extract base64 content with primary pattern")
        st.write("First 200 characters of file:")
        st.code(file_content[:200])
        
        # Try more flexible pattern as fallback
        alternative_pattern = r'__resolveJsonp\([^,]+,\s*"([^"]+)"\)'
        alt_match = re.search(alternative_pattern, file_content)
        if alt_match:
            st.info("Found content with alternative pattern, trying that instead...")
            return alt_match.group(1)
        
        # Try even more flexible pattern as last resort
        last_resort_pattern = r'__resolveJsonp\(.*?,\s*"([A-Za-z0-9+/=]+)"\)'
        last_match = re.search(last_resort_pattern, file_content)
        if last_match:
            st.info("Found content with last resort pattern, attempting to use...")
            return last_match.group(1)
            
        st.error("Could not extract content with any pattern")
        return None
    except Exception as e:
        st.error(f"Error in extract_jsonp_content: {str(e)}")
        st.code(traceback.format_exc())
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
        st.success("Successfully decoded base64 content")
        
        try:
            json_str = decoded_bytes.decode('utf-8')
            st.success("Successfully converted to UTF-8 string")
        except UnicodeDecodeError:
            st.error("Failed to decode as UTF-8, trying alternate encodings")
            # Try alternate encodings
            for encoding in ['latin-1', 'iso-8859-1', 'windows-1252']:
                try:
                    json_str = decoded_bytes.decode(encoding)
                    st.success(f"Successfully decoded using {encoding}")
                    break
                except UnicodeDecodeError:
                    continue
            else:
                st.error("Could not decode with any encoding")
                return None
        
        # Parse JSON string
        try:
            json_data = json.loads(json_str)
            st.success("Successfully parsed JSON data")
            return json_data
        except json.JSONDecodeError as je:
            st.error(f"JSON parsing error: {str(je)}")
            # Show partial JSON for debugging
            st.write("First 500 characters of decoded content:")
            st.code(json_str[:500])
            return None
            
    except base64.binascii.Error as be:
        st.error(f"Base64 decoding error: {str(be)}")
        # Try to show the first part of the base64 string for debugging
        st.write("First 50 characters of base64 content:")
        st.code(base64_content[:50])
        return None
    except Exception as e:
        st.error(f"Unexpected error in decode_base64_content: {str(e)}")
        st.code(traceback.format_exc())
        return None

def analyze_json_structure(json_data):
    """
    Analyze the structure of the JSON data for debugging.
    
    Args:
        json_data (dict): The JSON data to analyze
    
    Returns:
        dict: Information about the JSON structure
    """
    try:
        structure_info = {
            "top_level_keys": list(json_data.keys()),
            "list_fields": [],
            "potential_lesson_arrays": []
        }
        
        # Find all fields that are lists
        for key, value in json_data.items():
            if isinstance(value, list):
                list_info = {
                    "key": key,
                    "length": len(value),
                    "sample_keys": []
                }
                
                # Get sample keys from the first item if it's a dictionary
                if len(value) > 0 and isinstance(value[0], dict):
                    list_info["sample_keys"] = list(value[0].keys())
                    
                    # Check if this might be a lesson array
                    if 'title' in value[0] or 'id' in value[0]:
                        structure_info["potential_lesson_arrays"].append(key)
                
                structure_info["list_fields"].append(list_info)
        
        return structure_info
    except Exception as e:
        st.error(f"Error in analyze_json_structure: {str(e)}")
        st.code(traceback.format_exc())
        return {"error": str(e)}

def extract_lesson_data(json_data, debug=False):
    """
    Extract lesson titles and IDs from the decoded JSON data.
    
    Args:
        json_data (dict): The decoded JSON data
        debug (bool): Whether to show debug information
    
    Returns:
        list: List of dictionaries containing title and id for each lesson
    """
    try:
        if debug:
            # Analyze and display JSON structure
            structure_info = analyze_json_structure(json_data)
            st.write("### JSON Structure Analysis")
            st.write("Top level keys:", structure_info["top_level_keys"])
            
            if structure_info["potential_lesson_arrays"]:
                st.write("Potential lesson arrays found:", structure_info["potential_lesson_arrays"])
            else:
                st.warning("No obvious lesson arrays found in the top level")
        
        lessons_data = []
        lessons = None
        
        # Method 1: Direct lookup for 'lessons' key
        if 'lessons' in json_data:
            lessons = json_data['lessons']
            if debug:
                st.success(f"Found direct 'lessons' key with {len(lessons)} items")
        
        # Method 2: Look for arrays that might contain lessons
        if not lessons:
            candidates = []
            for key, value in json_data.items():
                if isinstance(value, list) and len(value) > 0:
                    # Check first few items to see if they look like lessons
                    sample_size = min(5, len(value))
                    sample_items = value[:sample_size]
                    
                    has_title_id = sum(1 for item in sample_items 
                                     if isinstance(item, dict) and ('title' in item or 'id' in item))
                    
                    if has_title_id > 0:
                        candidates.append((key, value, has_title_id/sample_size))
            
            # Sort candidates by the proportion that have title and id
            candidates.sort(key=lambda x: x[2], reverse=True)
            
            if candidates:
                best_candidate = candidates[0]
                lessons = best_candidate[1]
                if debug:
                    st.success(f"Found potential lessons array in '{best_candidate[0]}' with {len(lessons)} items")
                    st.write(f"Match confidence: {best_candidate[2]*100:.1f}%")
        
        # Method 3: Deep search for arrays of objects with title and id
        if not lessons and debug:
            st.info("Performing deep search for lesson-like objects...")
            
            def find_lesson_arrays(obj, path="root"):
                results = []
                
                if isinstance(obj, dict):
                    for key, value in obj.items():
                        new_path = f"{path}.{key}"
                        results.extend(find_lesson_arrays(value, new_path))
                
                elif isinstance(obj, list) and len(obj) > 0 and isinstance(obj[0], dict):
                    # Check if this array has items with title and id
                    sample_size = min(5, len(obj))
                    sample_items = obj[:sample_size]
                    has_title_id = sum(1 for item in sample_items 
                                    if ('title' in item or 'id' in item))
                    
                    if has_title_id > 0:
                        results.append((path, obj, has_title_id/sample_size))
                    
                    # Also check children
                    for i, item in enumerate(obj[:3]):  # Only check first few items
                        results.extend(find_lesson_arrays(item, f"{path}[{i}]"))
                
                return results
            
            deep_candidates = find_lesson_arrays(json_data)
            deep_candidates.sort(key=lambda x: x[2], reverse=True)
            
            if deep_candidates:
                st.write("Found nested lesson-like arrays:")
                for path, arr, confidence in deep_candidates[:3]:
                    st.write(f"- Path: {path}, Items: {len(arr)}, Confidence: {confidence*100:.1f}%")
                
                best_deep = deep_candidates[0]
                if not lessons:  # Only use if we haven't found lessons yet
                    lessons = best_deep[1]
                    st.success(f"Using deep search result: {best_deep[0]}")
        
        # Extract data from the lessons if found
        if lessons:
            for lesson in lessons:
                if isinstance(lesson, dict):
                    lesson_data = {}
                    
                    # Always include id and title if available
                    if 'id' in lesson:
                        lesson_data['id'] = lesson['id']
                    if 'title' in lesson:
                        lesson_data['title'] = lesson['title']
                    
                    # Only add if we have at least an id
                    if 'id' in lesson_data:
                        lessons_data.append(lesson_data)
        
        # Debug: If no lessons found, show sample data
        if debug and not lessons_data:
            st.error("No lesson data could be extracted")
            
            # Show a sample of the JSON structure for troubleshooting
            st.write("### Sample of JSON Data")
            try:
                st.json(json.dumps(json_data, indent=2)[:1000] + "...")
            except:
                st.write("Could not display JSON sample")
                st.write("JSON type:", type(json_data))
        
        return lessons_data
    except Exception as e:
        st.error(f"Error in extract_lesson_data: {str(e)}")
        st.code(traceback.format_exc())
        return []

def get_downloadable_csv(lessons_data):
    """
    Convert lessons data to CSV format for download.
    
    Args:
        lessons_data (list): List of lesson dictionaries
    
    Returns:
        str: CSV data as a string
    """
    try:
        df = pd.DataFrame(lessons_data)
        csv = df.to_csv(index=False)
        return csv
    except Exception as e:
        st.error(f"Error creating CSV: {str(e)}")
        st.code(traceback.format_exc())
        return "Error generating CSV"

def main():
    try:
        st.title("Rise Course Lesson Extractor & IMSCC Creator")
        
        st.markdown("""
        ## Extract Rise course content and create LMS-compatible packages
        
        This tool helps you:
        1. **Extract lesson information** from Rise course files
        2. **Create IMS Common Cartridge packages** for importing into Learning Management Systems
        3. **Link your Rise content** through iframes in the LMS
        """)
        
        with st.expander("Where to find the und.js file"):
            st.markdown("""
            1. Find the `und.js` file in your published Rise course files
               - This is typically in the `data/` folder of your exported SCORM package
               - It contains the encoded course structure and lesson data
            
            2. Upload the file using the file uploader below
            
            3. The tool will extract lesson information and display it in a table
            
            4. Optionally create an IMSCC package by providing a base URL
               - The base URL will be combined with each lesson ID
               - Each lesson will be a page with an iframe pointing to the content
            """)
        
        # Add debug mode checkbox
        debug_mode = st.checkbox("Enable debug mode", value=True)
        
        uploaded_file = st.file_uploader("Choose your und.js file", type=['js'])
        
        if uploaded_file is not None:
            try:
                # Check file size
                file_size = len(uploaded_file.getvalue())
                st.info(f"File size: {file_size/1024:.1f} KB")
                
                if file_size > 10_000_000:  # 10MB
                    st.warning(f"File is {file_size/1_000_000:.1f}MB. Large files may cause performance issues.")
                
                # Read file content
                file_content = uploaded_file.getvalue().decode('utf-8')
                
                # Quick validation
                if not "__resolveJsonp" in file_content[:1000]:
                    st.warning("This may not be a valid Rise und.js file. It doesn't contain the expected pattern.")
                
                # Show file info in debug mode
                if debug_mode:
                    st.write("File preview (first 200 characters):")
                    st.code(file_content[:200])
                
                # Extract base64 content
                st.info("Extracting content from file...")
                base64_content = extract_jsonp_content(file_content)
                
                if base64_content:
                    if debug_mode:
                        st.write(f"Base64 content length: {len(base64_content)} bytes")
                        st.write("Base64 preview (first 50 characters):")
                        st.code(base64_content[:50])
