#!/usr/bin/env python3
"""
Standalone IMSCC Creator for Rise Lesson Data

This script creates an IMS Common Cartridge (.imscc) package from a list of
lesson data. Each lesson becomes a page in the package with an iframe that 
loads content based on the lesson ID and a provided base URL.

Usage:
  python imscc_creator.py --input lesson_data.json --output course.imscc --base-url https://example.com/rise/
  python imscc_creator.py --input lesson_data.csv --output course.imscc --base-url https://example.com/rise/
  python imscc_creator.py --extract und.js --output course.imscc --base-url https://example.com/rise/
"""

import os
import sys
import shutil
import zipfile
import uuid
import html
import re
import argparse
import json
import csv
import base64
from datetime import datetime

import streamlit as st
st.title("IMSCC Creator")
st.write("This application is running. If you can see this, the script is loaded correctly.")

def extract_jsonp_content(file_path):
    """
    Extract the base64 encoded content from a Rise und.js file.
    
    Args:
        file_path (str): Path to the und.js file
    
    Returns:
        str: Extracted base64 content or None if not found
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            file_content = file.read()
        
        # Pattern to match __resolveJsonp("course:und","....") format
        pattern = r'__resolveJsonp\("course:und","([^"]+)"\)'
        match = re.search(pattern, file_content)
        
        if match:
            return match.group(1)
        
        # Try more flexible pattern as fallback
        alternative_pattern = r'__resolveJsonp\([^,]+,\s*"([^"]+)"\)'
        alt_match = re.search(alternative_pattern, file_content)
        if alt_match:
            print("Using alternative pattern for extraction")
            return alt_match.group(1)
        
        print("Could not find the expected format in the file.")
        return None
    except Exception as e:
        print(f"Error reading file: {str(e)}")
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
        print(f"Error decoding content: {str(e)}")
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
    lessons = None
    
    # Method 1: Direct lookup for 'lessons' key
    if 'lessons' in json_data:
        lessons = json_data['lessons']
        print(f"Found direct 'lessons' key with {len(lessons)} items")
    
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
            print(f"Found potential lessons array in '{best_candidate[0]}' with {len(lessons)} items")
    
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
    
    # If no lessons found, show error
    if not lessons_data:
        print("No lesson data could be extracted")
    
    return lessons_data


# Update the directory structure creation function
def create_directory_structure(base_dir):
    """
    Create the directory structure required for a Canvas-compatible IMSCC package
    
    Args:
        base_dir (str): Base directory where the structure will be created
        
    Returns:
        dict: Paths to important directories
    """
    # Ensure base directory exists
    os.makedirs(base_dir, exist_ok=True)
    
    # Create required directories for Canvas
    paths = {
        'root': base_dir,
        'wiki_content': os.path.join(base_dir, 'wiki_content'),  # Canvas expects pages in wiki_content
        'course_settings': os.path.join(base_dir, 'course_settings'),
    }
    
    for path in paths.values():
        os.makedirs(path, exist_ok=True)
    
    return paths

# Update the manifest creation function to use titles for filenames
def create_manifest(paths, course_title, lessons, org_id="org_1"):
    """
    Create the imsmanifest.xml file needed for the IMSCC package in Canvas format
    
    Args:
        paths (dict): Directory paths
        course_title (str): Title of the course
        lessons (list): List of lesson dictionaries
        org_id (str): Organization ID for the manifest
        
    Returns:
        str: Path to the created manifest file
    """
    manifest_path = os.path.join(paths['root'], 'imsmanifest.xml')
    
    # Generate unique identifiers for Canvas
    course_id = "course_" + str(uuid.uuid4()).replace('-', '')
    
    # Start building manifest XML with Canvas-compatible format
    manifest = '<?xml version="1.0" encoding="UTF-8"?>\n'
    manifest += '<manifest identifier="{}" '.format(course_id)
    manifest += 'xmlns="http://www.imsglobal.org/xsd/imsccv1p1/imscp_v1p1" '
    manifest += 'xmlns:lom="http://ltsc.ieee.org/xsd/imsccv1p1/LOM/resource" '
    manifest += 'xmlns:lomimscc="http://ltsc.ieee.org/xsd/imsccv1p1/LOM/manifest" '
    manifest += 'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" '
    manifest += 'xsi:schemaLocation="http://www.imsglobal.org/xsd/imsccv1p1/imscp_v1p1 '
    manifest += 'http://www.imsglobal.org/profile/cc/ccv1p1/ccv1p1_imscp_v1p2_v1p0.xsd '
    manifest += 'http://ltsc.ieee.org/xsd/imsccv1p1/LOM/resource '
    manifest += 'http://www.imsglobal.org/profile/cc/ccv1p1/LOM/ccv1p1_lomresource_v1p0.xsd '
    manifest += 'http://ltsc.ieee.org/xsd/imsccv1p1/LOM/manifest '
    manifest += 'http://www.imsglobal.org/profile/cc/ccv1p1/LOM/ccv1p1_lommanifest_v1p0.xsd">\n'
    
    # Metadata section in Canvas format
    manifest += '  <metadata>\n'
    manifest += '    <schema>IMS Common Cartridge</schema>\n'
    manifest += '    <schemaversion>1.1.0</schemaversion>\n'
    manifest += '    <lomimscc:lom>\n'
    manifest += '      <lomimscc:general>\n'
    manifest += '        <lomimscc:title>\n'
    manifest += '          <lomimscc:string>{}</lomimscc:string>\n'.format(html.escape(course_title))
    manifest += '        </lomimscc:title>\n'
    manifest += '      </lomimscc:general>\n'
    manifest += '      <lomimscc:lifeCycle>\n'
    manifest += '        <lomimscc:contribute>\n'
    manifest += '          <lomimscc:date>\n'
    manifest += '            <lomimscc:dateTime>{}</lomimscc:dateTime>\n'.format(datetime.now().strftime("%Y-%m-%d"))
    manifest += '          </lomimscc:date>\n'
    manifest += '        </lomimscc:contribute>\n'
    manifest += '      </lomimscc:lifeCycle>\n'
    manifest += '      <lomimscc:rights>\n'
    manifest += '        <lomimscc:copyrightAndOtherRestrictions>\n'
    manifest += '          <lomimscc:value>yes</lomimscc:value>\n'
    manifest += '        </lomimscc:copyrightAndOtherRestrictions>\n'
    manifest += '        <lomimscc:description>\n'
    manifest += '          <lomimscc:string>Private (Copyrighted) - http://en.wikipedia.org/wiki/Copyright</lomimscc:string>\n'
    manifest += '        </lomimscc:description>\n'
    manifest += '      </lomimscc:rights>\n'
    manifest += '    </lomimscc:lom>\n'
    manifest += '  </metadata>\n'
    
    # Organizations section in Canvas format
    manifest += '  <organizations>\n'
    manifest += '    <organization identifier="{}" structure="rooted-hierarchy">\n'.format(org_id)
    manifest += '      <item identifier="LearningModules">\n'
    
    # Add module for the lessons
    module_id = "module_" + str(uuid.uuid4()).replace('-', '')
    manifest += '        <item identifier="{}">\n'.format(module_id)
    manifest += '          <title>{}</title>\n'.format(html.escape(course_title))
    
    # Add items for each lesson
    for lesson in lessons:
        lesson_id = lesson['id']
        lesson_title = lesson.get('title', 'Untitled Lesson')
        
        # Create Canvas-style identifiers
        item_id = "g" + re.sub(r'[^a-zA-Z0-9]', '', str(uuid.uuid4()))
        resource_id = "g" + re.sub(r'[^a-zA-Z0-9]', '', str(uuid.uuid4()))
        
        # Use the title to create the filename
        # Convert to lowercase, replace spaces and special chars with hyphens
        filename = lesson_title.lower()
        # Replace spaces and special characters with hyphens
        filename = re.sub(r'[^a-z0-9]+', '-', filename)
        # Remove leading/trailing hyphens
        filename = filename.strip('-')
        # Add .html extension
        filename = filename + '.html'
        
        # Store filenames for later use
        lesson['filename'] = filename
        lesson['resource_id'] = resource_id
        
        manifest += '          <item identifier="{}" identifierref="{}">\n'.format(item_id, resource_id)
        manifest += '            <title>{}</title>\n'.format(html.escape(lesson_title))
        manifest += '          </item>\n'
    
    # Close organization structure
    manifest += '        </item>\n'
    manifest += '      </item>\n'
    manifest += '    </organization>\n'
    manifest += '  </organizations>\n'
    
    # Resources section in Canvas format
    manifest += '  <resources>\n'
    
    # Add course settings resource for Canvas
    settings_id = "g" + re.sub(r'[^a-zA-Z0-9]', '', str(uuid.uuid4()))
    manifest += '    <resource identifier="{}" type="associatedcontent/imscc_xmlv1p1/learning-application-resource" href="course_settings/canvas_export.txt">\n'.format(settings_id)
    manifest += '      <file href="course_settings/course_settings.xml"/>\n'
    manifest += '      <file href="course_settings/canvas_export.txt"/>\n'
    manifest += '    </resource>\n'
    
    # Add resource for each lesson
    for lesson in lessons:
        resource_id = lesson['resource_id']
        filename = lesson['filename']
        
        manifest += '    <resource identifier="{}" type="webcontent" href="wiki_content/{}">\n'.format(
            resource_id, filename)
        manifest += '      <file href="wiki_content/{}"/>\n'.format(filename)
        manifest += '    </resource>\n'
    
    manifest += '  </resources>\n'
    manifest += '</manifest>\n'
    
    # Write manifest to file
    with open(manifest_path, 'w', encoding='utf-8') as f:
        f.write(manifest)
    
    # Create course settings file for Canvas
    create_canvas_settings(paths, course_title)
    
    return manifest_path

# Update the page creation function to preserve title consistency
def create_lesson_pages(paths, lessons, base_url):
    """
    Create HTML pages for each lesson with an iframe in Canvas format
    
    Args:
        paths (dict): Directory paths
        lessons (list): List of lesson dictionaries
        base_url (str): Base URL to combine with lesson IDs
        
    Returns:
        list: Paths to the created HTML files
    """
    html_files = []
    
    for lesson in lessons:
        lesson_id = lesson['id']
        lesson_title = lesson.get('title', 'Untitled Lesson')
        filename = lesson.get('filename')
        
        # If filename wasn't set in the manifest creation, create it here (fallback)
        if not filename:
            filename = lesson_title.lower()
            filename = re.sub(r'[^a-z0-9]+', '-', filename)
            filename = filename.strip('-') + '.html'
        
        file_path = os.path.join(paths['wiki_content'], filename)
        
        # Format the iframe URL
        iframe_url = base_url
        if not iframe_url.endswith('/'):
            iframe_url += '/'
        iframe_url += lesson_id
        
        # Create HTML content with iframe in Canvas-compatible format
        html_content = '<!DOCTYPE html>\n'
        html_content += '<html>\n'
        html_content += '<head>\n'
        html_content += '  <meta charset="UTF-8">\n'
        html_content += '  <meta name="viewport" content="width=device-width, initial-scale=1.0">\n'
        html_content += f'  <title>{html.escape(lesson_title)}</title>\n'
        html_content += '  <style>\n'
        html_content += '    body { font-family: Arial, sans-serif; line-height: 1.6; margin: 0; padding: 20px; }\n'
        html_content += '    h1 { color: #333; margin-bottom: 20px; }\n'
        html_content += '    .iframe-container { width: 100%; height: 800px; border: 1px solid #ddd; margin: 20px 0; }\n'
        html_content += '    iframe { border: none; width: 100%; height: 100%; }\n'
        html_content += '  </style>\n'
        html_content += '</head>\n'
        html_content += '<body>\n'
        html_content += f'  <h1>{html.escape(lesson_title)}</h1>\n'
        html_content += '  <div class="iframe-container">\n'
        html_content += f'    <iframe src="{html.escape(iframe_url)}" allowfullscreen></iframe>\n'
        html_content += '  </div>\n'
        html_content += '  <p><small>This content is embedded from an external source.</small></p>\n'
        html_content += '</body>\n'
        html_content += '</html>\n'
        
        # Write HTML to file
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        html_files.append(file_path)
    
    return html_files


def create_imscc_package(paths, output_path):
    """
    Create the final IMSCC package as a ZIP file
    
    Args:
        paths (dict): Directory paths
        output_path (str): Path for the output IMSCC file
        
    Returns:
        str: Path to the created IMSCC file
    """
    # Ensure output directory exists
    output_dir = os.path.dirname(output_path)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
    
    # Create ZIP file with the .imscc extension
    with zipfile.ZipFile(output_path, 'w') as imscc_zip:
        # Walk through the directory structure and add all files
        for root, _, files in os.walk(paths['root']):
            for file in files:
                file_path = os.path.join(root, file)
                # Get the relative path from the base directory
                rel_path = os.path.relpath(file_path, paths['root'])
                imscc_zip.write(file_path, rel_path)
    
    return output_path


def load_lessons_from_file(file_path):
    """
    Load lesson data from a CSV or JSON file
    
    Args:
        file_path (str): Path to the CSV or JSON file
        
    Returns:
        list: List of lesson dictionaries containing 'id' and 'title'
    """
    file_ext = os.path.splitext(file_path)[1].lower()
    
    # Load JSON file
    if file_ext == '.json':
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # If data is a list, assume it's already in the correct format
            if isinstance(data, list):
                return data
            
            # If data has a 'lessons' key, extract that
            if isinstance(data, dict) and 'lessons' in data:
                return data['lessons']
            
            # Otherwise, return empty list
            return []
        except Exception as e:
            print(f"Error loading JSON file: {str(e)}")
            return []
    
    # Load CSV file
    elif file_ext == '.csv':
        try:
            lessons = []
            with open(file_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    if 'id' in row:
                        lesson = {'id': row['id']}
                        if 'title' in row:
                            lesson['title'] = row['title']
                        lessons.append(lesson)
            return lessons
        except Exception as e:
            print(f"Error loading CSV file: {str(e)}")
            return []
    
    # Unsupported file type
    else:
        print(f"Unsupported file type: {file_ext}")
        return []


def create_package(lessons, output_path, base_url, course_title=None, clean_temp=True):
    """
    Main function to create an IMSCC package from lesson data
    
    Args:
        lessons (list): List of lesson dictionaries containing 'id' and 'title'
        output_path (str): Path for the output IMSCC file
        base_url (str): Base URL to combine with lesson IDs for iframes
        course_title (str, optional): Title of the course. Defaults to "Rise Course Export".
        clean_temp (bool, optional): Whether to clean up temporary files. Defaults to True.
        
    Returns:
        str: Path to the created IMSCC file
    """
    # Use current timestamp for temp directory to avoid conflicts
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    temp_dir = os.path.join(os.path.dirname(output_path), f"temp_imscc_{timestamp}")
    
    # Set default course title if not provided
    if not course_title:
        course_title = "Rise Course Export"
    
    try:
        # Create directory structure
        paths = create_directory_structure(temp_dir)
        
        # Create manifest
        create_manifest(paths, course_title, lessons)
        
        # Create lesson pages
        create_lesson_pages(paths, lessons, base_url)
        
        # Create IMSCC package
        imscc_path = create_imscc_package(paths, output_path)
        
        print(f"Successfully created IMSCC package at: {imscc_path}")
        return imscc_path
    
    finally:
        # Clean up temporary files if requested
        if clean_temp and os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)
