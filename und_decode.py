import streamlit as st
import json
import base64
import re
import pandas as pd
import io
from collections import Counter

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
    
    # Debug information
    st.error("Failed to extract base64 content from the file")
    st.write("First 200 characters of file:")
    st.code(file_content[:200])
    
    # Try more flexible pattern as fallback
    alternative_pattern = r'__resolveJsonp\([^,]+,\s*"([^"]+)"\)'
    alt_match = re.search(alternative_pattern, file_content)
    if alt_match:
        st.info("Found content with alternative pattern, trying that instead...")
        return alt_match.group(1)
    
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
        # Try to show the first part of the base64 string for debugging
        st.write("First 50 characters of base64 content:")
        st.code(base64_content[:50])
        return None

def analyze_json_structure(json_data):
    """
    Analyze the structure of the JSON data for debugging.
    
    Args:
        json_data (dict): The JSON data to analyze
    
    Returns:
        dict: Information about the JSON structure
    """
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

def extract_lesson_data(json_data, debug=False):
    """
    Extract lesson titles and IDs from the decoded JSON data.
    
    Args:
        json_data (dict): The decoded JSON data
        debug (bool): Whether to show debug information
    
    Returns:
        list: List of dictionaries containing title and id for each lesson
    """
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
                                 if isinstance(item, dict) and 'title' in item and 'id' in item)
                
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
                                if 'title' in item and 'id' in item)
                
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
        st.json(json.dumps(json_data, indent=2)[:1000] + "...")
    
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
    
    # Add debug mode checkbox
    debug_mode = st.checkbox("Enable debug mode", value=False)
    
    uploaded_file = st.file_uploader("Choose your und.js file", type=['js'])
    
    if uploaded_file is not None:
        # Read file content
        file_content = uploaded_file.getvalue().decode('utf-8')
        
        # Show file info in debug mode
        if debug_mode:
            file_size = len(file_content)
            st.write(f"File size: {file_size} bytes")
            st.write("File preview (first 200 characters):")
            st.code(file_content[:200])
        
        # Extract base64 content
        base64_content = extract_jsonp_content(file_content)
        
        if base64_content:
            if debug_mode:
                st.write(f"Base64 content length: {len(base64_content)} bytes")
                st.write("Base64 preview (first 50 characters):")
                st.code(base64_content[:50])
            
            with st.spinner("Decoding and extracting lesson data..."):
                # Decode base64 to get JSON
                json_data = decode_base64_content(base64_content)
                
                if json_data:
                    # Extract lesson titles and IDs with debug info if enabled
                    lessons_data = extract_lesson_data(json_data, debug=debug_mode)
                    
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
                        text_output = "\n".join([f"{lesson.get('title', 'No Title')} - {lesson['id']}" 
                                               for lesson in lessons_data if 'id' in lesson])
                        st.download_button(
                            label="Download as Text",
                            data=text_output,
                            file_name="lesson_data.txt",
                            mime="text/plain"
                        )
                    else:
                        st.warning("No lesson data found in the file.")
                        
                        if debug_mode:
                            # Try to show the raw 'lessons' structure if possible
                            if 'lessons' in json_data:
                                st.write("Raw 'lessons' data found but extraction failed:")
                                st.json(json_data['lessons'][:2])  # Show first 2 items
                else:
                    st.error("Failed to decode the base64 content.")
        else:
            st.error("Could not find the expected format in the file. Make sure it contains __resolveJsonp(\"course:und\",\"...\")")
            
            if debug_mode:
                # Try alternative pattern search
                st.write("Trying to find any jsonp pattern...")
                jsonp_patterns = [
                    r'__resolveJsonp\(([^,]+),\s*"([^"]+)"\)',
                    r'__resolveJsonp\(([^)]+)\)',
                    r'_resolve\w+\(([^)]+)\)'
                ]
                
                for pattern in jsonp_patterns:
                    matches = re.findall(pattern, file_content)
                    if matches:
                        st.write(f"Found potential matches with pattern: {pattern}")
                        st.write(f"First few matches: {matches[:2]}")
                        break

if __name__ == "__main__":
    main()
