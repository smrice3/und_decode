#!/usr/bin/env python3
"""
IMSCC Creator Module for Rise Lesson Data

This module creates an IMS Common Cartridge (.imscc) package from a list of
lesson data. Each lesson becomes a page in the package with an iframe that 
loads content based on the lesson ID and a provided base URL.
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
from datetime import datetime


def create_directory_structure(base_dir):
    """
    Create the directory structure required for an IMSCC package
    
    Args:
        base_dir (str): Base directory where the structure will be created
        
    Returns:
        dict: Paths to important directories
    """
    # Ensure base directory exists
    os.makedirs(base_dir, exist_ok=True)
    
    # Create required directories
    paths = {
        'root': base_dir,
        'resources': os.path.join(base_dir, 'resources'),
        'webcontent': os.path.join(base_dir, 'resources', 'webcontent')
    }
    
    for path in paths.values():
        os.makedirs(path, exist_ok=True)
    
    return paths


def create_manifest(paths, course_title, lessons, org_id="RiseExport"):
    """
    Create the imsmanifest.xml file needed for the IMSCC package
    
    Args:
        paths (dict): Directory paths
        course_title (str): Title of the course
        lessons (list): List of lesson dictionaries
        org_id (str): Organization ID for the manifest
        
    Returns:
        str: Path to the created manifest file
    """
    manifest_path = os.path.join(paths['root'], 'imsmanifest.xml')
    
    # Generate unique identifiers
    course_id = "course_" + str(uuid.uuid4()).replace('-', '')
    
    # Start building manifest XML
    manifest = '<?xml version="1.0" encoding="UTF-8"?>\n'
    manifest += '<manifest identifier="{}" '.format(course_id)
    manifest += 'xmlns="http://www.imsglobal.org/xsd/imsccv1p1/imscp_v1p1" '
    manifest += 'xmlns:lom="http://ltsc.ieee.org/xsd/imsccv1p1/LOM/resource" '
    manifest += 'xmlns:lomimscc="http://ltsc.ieee.org/xsd/imsccv1p1/LOM/manifest" '
    manifest += 'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" '
    manifest += 'xsi:schemaLocation="http://www.imsglobal.org/xsd/imsccv1p1/imscp_v1p1 '
    manifest += 'http://www.imsglobal.org/xsd/imscp_v1p1.xsd '
    manifest += 'http://ltsc.ieee.org/xsd/imsccv1p1/LOM/resource '
    manifest += 'http://www.imsglobal.org/profile/cc/ccv1p1/LOM/ccv1p1_lomresource_v1p0.xsd '
    manifest += 'http://ltsc.ieee.org/xsd/imsccv1p1/LOM/manifest '
    manifest += 'http://www.imsglobal.org/profile/cc/ccv1p1/LOM/ccv1p1_lommanifest_v1p0.xsd">\n'
    
    # Metadata
    manifest += '  <metadata>\n'
    manifest += '    <schema>IMS Common Cartridge</schema>\n'
    manifest += '    <schemaversion>1.1.0</schemaversion>\n'
    manifest += '    <lomimscc:lom>\n'
    manifest += '      <lomimscc:general>\n'
    manifest += '        <lomimscc:title>\n'
    manifest += '          <lomimscc:string>{}</lomimscc:string>\n'.format(html.escape(course_title))
    manifest += '        </lomimscc:title>\n'
    manifest += '      </lomimscc:general>\n'
    manifest += '    </lomimscc:lom>\n'
    manifest += '  </metadata>\n'
    
    # Organizations
    manifest += '  <organizations>\n'
    manifest += '    <organization identifier="{}" structure="rooted-hierarchy">\n'.format(org_id)
    manifest += '      <item identifier="root">\n'
    
    # Add items for each lesson
    for lesson in lessons:
        lesson_id = lesson['id']
        lesson_title = lesson.get('title', 'Untitled Lesson')
        
        # Create a sanitized identifier for the manifest
        item_id = "item_" + re.sub(r'[^a-zA-Z0-9]', '_', lesson_id)
        resource_id = "resource_" + re.sub(r'[^a-zA-Z0-9]', '_', lesson_id)
        
        manifest += '        <item identifier="{}" identifierref="{}">\n'.format(item_id, resource_id)
        manifest += '          <title>{}</title>\n'.format(html.escape(lesson_title))
        manifest += '        </item>\n'
    
    manifest += '      </item>\n'
    manifest += '    </organization>\n'
    manifest += '  </organizations>\n'
    
    # Resources
    manifest += '  <resources>\n'
    
    # Add resource for each lesson
    for lesson in lessons:
        lesson_id = lesson['id']
        lesson_title = lesson.get('title', 'Untitled Lesson')
        
        # Create a sanitized identifier for the manifest
        resource_id = "resource_" + re.sub(r'[^a-zA-Z0-9]', '_', lesson_id)
        filename = re.sub(r'[^a-zA-Z0-9]', '_', lesson_id) + '.html'
        
        manifest += '    <resource identifier="{}" type="webcontent" href="resources/webcontent/{}">\n'.format(
            resource_id, filename)
        manifest += '      <file href="resources/webcontent/{}"/>\n'.format(filename)
        manifest += '    </resource>\n'
    
    manifest += '  </resources>\n'
    manifest += '</manifest>\n'
    
    # Write manifest to file
    with open(manifest_path, 'w', encoding='utf-8') as f:
        f.write(manifest)
    
    return manifest_path


def create_lesson_pages(paths, lessons, base_url):
    """
    Create HTML pages for each lesson with an iframe
    
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
        
        # Create a safe filename
        filename = re.sub(r'[^a-zA-Z0-9]', '_', lesson_id) + '.html'
        file_path = os.path.join(paths['webcontent'], filename)
        
        # Format the iframe URL
        iframe_url = base_url
        if not iframe_url.endswith('/'):
            iframe_url += '/'
        iframe_url += lesson_id
        
        # Create HTML content with iframe
        html_content = '<!DOCTYPE html>\n'
        html_content += '<html>\n'
        html_content += '<head>\n'
        html_content += '  <meta charset="UTF-8">\n'
        html_content += '  <title>{}</title>\n'.format(html.escape(lesson_title))
        html_content += '  <style>\n'
        html_content += '    body, html { margin: 0; padding: 0; height: 100%; overflow: hidden; }\n'
        html_content += '    iframe { border: none; width: 100%; height: 800px; }\n'
        html_content += '  </style>\n'
        html_content += '</head>\n'
        html_content += '<body>\n'
        html_content += '  <iframe src="{}" allowfullscreen></iframe>\n'.format(html.escape(iframe_url))
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


def main():
    """
    Main function when script is run directly
    """
    parser = argparse.ArgumentParser(description='Create an IMSCC package from lesson data')
    parser.add_argument('--lessons', '-l', required=True, help='JSON file or JSON string with lesson data')
    parser.add_argument('--output', '-o', required=True, help='Output path for the IMSCC file')
    parser.add_argument('--base-url', '-u', required=True, help='Base URL to combine with lesson IDs')
    parser.add_argument('--title', '-t', default="Rise Course Export", help='Course title')
    
    args = parser.parse_args()
    
    # Load lessons data
    try:
        # First try to parse as a JSON string
        lessons = json.loads(args.lessons)
    except json.JSONDecodeError:
        # If that fails, try to load as a JSON file
        try:
            with open(args.lessons, 'r', encoding='utf-8') as f:
                lessons = json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            print("Error: Could not parse lessons data. Provide valid JSON or a JSON file path.")
            sys.exit(1)
    
    # Ensure lessons is a list
    if not isinstance(lessons, list):
        print("Error: Lessons data must be a list of lesson objects.")
        sys.exit(1)
    
    # Create the IMSCC package
    create_package(lessons, args.output, args.base_url, args.title)


if __name__ == "__main__":
    main()
