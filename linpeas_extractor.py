#!/usr/bin/env python3
#version 4.7.25

import re
import sys
import argparse

DEBUG = False


open_API = "sdcsdcsdcsdcsdc"     


def remove_ansi_codes(text):
    """Remove ANSI escape codes from text"""
    # Fixed: Added timeout protection and simpler pattern
    ansi_escape = re.compile(r'\x1B\[[0-9;]*[a-zA-Z]')
    return ansi_escape.sub('', text)

def extract_highlighted_words(line, red_only=False):
    """Extract only the segments that were highlighted with red/yellow or red-only ANSI codes"""
    highlighted_segments = []
    
    if red_only:
        # Look for red-only patterns (1;31m without yellow background)
        # Pattern 1: \x1B[1;31m...text...\x1B[0m - Fixed: Added length limit
        pattern1 = r'\x1B\[1;31m([^\x1B]{1,500})(?:\x1B\[0m|\x1B\[)'
        highlighted_segments = re.findall(pattern1, line)
        
        # Pattern 2: \x1B[31m...text...\x1B[0m - Fixed: Added length limit
        pattern2 = r'\x1B\[31m([^\x1B]{1,500})(?:\x1B\[0m|\x1B\[)'
        highlighted_segments.extend(re.findall(pattern2, line))
        
        # Pattern 3: More general - extract text between red markers and any ANSI code or end
        if not highlighted_segments and ('\x1B[1;31m' in line or '\x1B[31m' in line):
            # Fixed: Added length limit and timeout protection
            pattern3 = r'\x1B\[(?:1;)?31m([^\x1B]{1,500})(?:\x1B|\Z)'
            highlighted_segments.extend(re.findall(pattern3, line))
            
        # Pattern 4: Even more general - just find text after red markers until non-text
        if not highlighted_segments:
            # Fixed: Added length limit to prevent ReDoS
            pattern4 = r'\x1B\[(?:1;)?31m([^\x1B]{1,500})'
            highlighted_segments.extend(re.findall(pattern4, line))
    else:
        # Original red/yellow pattern logic - Fixed: Added length limits
        pattern1 = r'\x1B\[1;31;103m([^\x1B]{1,500})(?:\x1B\[0m|\x1B\[)'
        highlighted_segments = re.findall(pattern1, line)
        
        # Also check for more complex patterns with nested ANSI codes - Fixed: Added length limit
        pattern2 = r'\x1B\[1;31;103m\x1B\[1;31m([^\x1B]{1,500})\x1B\[0m'
        highlighted_segments.extend(re.findall(pattern2, line))
        
        # If the above didn't find anything, try a more general approach
        if not highlighted_segments and '1;31;103m' in line:
            # Fixed: Added length limit to prevent ReDoS
            pattern3 = r'\x1B\[1;31;103m([^\x1B]{1,500})(?:\x1B|\Z)'
            highlighted_segments.extend(re.findall(pattern3, line))
    
    # Clean any extra characters and ANSI codes from the segments
    clean_segments = []
    for segment in highlighted_segments:
        # Remove any embedded ANSI codes
        clean_segment = remove_ansi_codes(segment).strip()
        if clean_segment:
            clean_segments.append(clean_segment)
    
    if DEBUG:
        # Show the actual line for debugging
        clean_line = remove_ansi_codes(line).strip()
        print(f"[DEBUG] Line: {clean_line[:80]}")
        if clean_segments:
            print(f"[DEBUG] Highlighted segments: {clean_segments}")
        else:
            # If no matches but has markers, show raw line
            search_pattern = '1;31;103m' if not red_only else ('1;31m' if '1;31m' in line else '31m')
            if search_pattern in line:
                print(f"[DEBUG] Line has {'red/yellow' if not red_only else 'red'} markers but no segments extracted!")
                debug_line = line.replace('\x1B', '^[')
                print(f"[DEBUG] Raw line: {debug_line[:80]}")
    
    return clean_segments

def colorize_text(text, highlighted_segments):
    """Add modern color highlighting to specific segments"""
    # Modern color codes for better visibility in terminal
    YELLOW_BG = '\033[43m'      # Yellow background
    RED_TEXT = '\033[1;31m'     # Bold red text
    RESET = '\033[0m'           # Reset all attributes
  #  [0m[1;31;103m[1;31m
    result = text
    # Sort segments by length (longest first) to avoid partial replacements
    sorted_segments = sorted(highlighted_segments, key=len, reverse=True)
    
    for segment in sorted_segments:
        if segment.strip():  # Only colorize non-empty segments
            try:
                # Replace exact segment with colored version - keep original LinPEAS look
                highlighted = f"{RED_TEXT}{YELLOW_BG}{segment}{RESET}"
                # Need to replace exact segments to avoid partial matches
                result = result.replace(segment, highlighted)
            except Exception as e:
                if DEBUG:
                    print(f"[DEBUG] Error highlighting '{segment}': {e}")
    
    return result

def has_red_yellow_marker(line, red_only=False):
    """Check if line contains red/yellow or red-only ANSI color codes that indicate important findings"""
    if red_only:
        # Look for red-only patterns (without yellow background)
        # Check for \x1B[1;31m or \x1B[31m patterns
        if ('\x1B[1;31m' in line or '\x1B[31m' in line):
            # Make sure it's not part of red/yellow pattern
            if '1;31;103m' not in line:
                if DEBUG:
                    print(f"[DEBUG] Found RED-only marker in line: {remove_ansi_codes(line)[:80]}...")
                return True
    else:
        # Only look for the specific RED text on YELLOW background pattern
        red_yellow_pattern = r'1;31;103m'  # RED text on YELLOW background - highest priority
        
        if red_yellow_pattern in line:
            if DEBUG:
                print(f"[DEBUG] Found RED/YELLOW marker in line: {remove_ansi_codes(line)[:80]}...")
            return True
    return False

def is_section_header(line):
    """Check if line is a section header (contains box drawing characters)"""
    box_chars = ['╔', '╣', '╚', '═', '╗', '╠', '╝', '║']
    clean_line = remove_ansi_codes(line)
    return any(char in clean_line for char in box_chars)

def extract_red_yellow_with_context(file_path, red_only=False):
    """Extract lines with red/yellow or red-only markers along with their section context"""
    
    print(f"Processing file: {file_path}")
    print(f"Mode: {'RED-only' if red_only else 'RED/YELLOW'}")
    print("=" * 50)
    
    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
        lines = f.readlines()
    
    results = []
    current_section = ""
    current_subsection = ""
    start_processing = False
    
    for i, line in enumerate(lines, 1):
        # Look for the "Basic information" section to start processing
        if not start_processing:
            clean_line = remove_ansi_codes(line).strip()
            if 'Basic information' in clean_line and '╣' in clean_line and '╠' in clean_line:
                start_processing = True
                current_section = clean_line
                if DEBUG:
                    print(f"[DEBUG] Starting processing from Basic information section at line {i}")
                continue
            else:
                continue  # Skip everything before Basic information section
        
        # Track section headers (only after we start processing)
        if is_section_header(line):
            clean_header = remove_ansi_codes(line).strip()
            if '╣' in clean_header and '╠' in clean_header:
                # Main section header like "═══════════════════════════════╣ Basic information ╠═══════════════════════════════"
                current_section = clean_header
                current_subsection = ""
                if DEBUG:
                    print(f"[DEBUG] Found main section: {current_section}")
            elif '╔' in clean_header and '╣' in clean_header:
                # Subsection header like "╔══════════╣ Operative system"
                current_subsection = clean_header
                if DEBUG:
                    print(f"[DEBUG] Found subsection: {current_subsection}")
        
        # Check for red/yellow or red-only markers (only after we start processing)
        if has_red_yellow_marker(line, red_only):
            clean_line = remove_ansi_codes(line).strip()
            highlighted_words = extract_highlighted_words(line, red_only)
            
            if clean_line:  # Only skip empty lines, include section headers if they have red/yellow markers
                context = ""
                if current_section:
                    # Extract just the section name from between ╣ and ╠
                    section_match = re.search(r'╣\s*([^╠]+)\s*╠', current_section)
                    if section_match:
                        context = f"Section: {section_match.group(1).strip()}"
                    else:
                        context = f"Section: {current_section}"
                
                if current_subsection:
                    # Extract just the subsection name after ╣
                    subsection_match = re.search(r'╣\s*(.+)', current_subsection)
                    if subsection_match:
                        if context:
                            context += f"\nSubsection: {subsection_match.group(1).strip()}"
                        else:
                            context = f"Subsection: {subsection_match.group(1).strip()}"
                
                results.append({
                    'line_number': i,
                    'context': context,
                    'content': clean_line,
                    'highlighted_words': highlighted_words,
                    'raw_line': line.strip()
                })
                
                if DEBUG:
                    print(f"[DEBUG] Added finding at line {i}")
    
    return results

def group_findings_by_context(findings):
    """Group findings by their section and subsection context"""
    grouped = {}
    for finding in findings:
        context_key = finding['context'] if finding['context'] else "No Context"
        if context_key not in grouped:
            grouped[context_key] = []
        grouped[context_key].append(finding)
    return grouped

def ansi_to_html(text):
    """Convert ANSI escape codes to HTML with CSS styling"""
    import re
    
    # Escape HTML characters first
    html_text = text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
    
    # Stack to track open spans for proper nesting
    span_stack = []
    
    def process_ansi_code(match):
        nonlocal span_stack
        code = match.group(1)
        
        # Reset code - close all open spans
        if code == '0' or code == '':
            result = '</span>' * len(span_stack)
            span_stack.clear()
            return result
        
        # Parse the ANSI code
        parts = [int(x) if x.isdigit() else 0 for x in code.split(';') if x]
        if not parts:
            return ''
        
        styles = []
        bg_color = None
        
        for part in parts:
            if part == 1:  # Bold
                styles.append('font-weight: bold')
            elif part == 31:  # Red
                styles.append('color: #ff4444')
            elif part == 32:  # Green  
                styles.append('color: #44ff44')
            elif part == 33:  # Yellow
                styles.append('color: #ffff44')
            elif part == 34:  # Blue
                styles.append('color: #4444ff')
            elif part == 35:  # Magenta
                styles.append('color: #ff44ff')
            elif part == 36:  # Cyan
                styles.append('color: #44ffff')
            elif part == 37:  # White
                styles.append('color: #ffffff')
            elif part == 90:  # Bright Black (Gray)
                styles.append('color: #888888')
            elif part == 91:  # Bright Red
                styles.append('color: #ff6666')
            elif part == 92:  # Bright Green
                styles.append('color: #66ff66')
            elif part == 93:  # Bright Yellow
                styles.append('color: #ffff66')
            elif part == 94:  # Bright Blue
                styles.append('color: #6666ff')
            elif part == 95:  # Bright Magenta
                styles.append('color: #ff66ff')
            elif part == 96:  # Bright Cyan
                styles.append('color: #66ffff')
            elif part == 97:  # Bright White
                styles.append('color: #ffffff')
            elif part == 40:  # Black background
                bg_color = '#000000'
            elif part == 41:  # Red background
                bg_color = '#aa0000'
            elif part == 42:  # Green background
                bg_color = '#00aa00'
            elif part == 43:  # Yellow background
                bg_color = '#aa5500'
            elif part == 44:  # Blue background
                bg_color = '#0000aa'
            elif part == 45:  # Magenta background
                bg_color = '#aa00aa'
            elif part == 46:  # Cyan background
                bg_color = '#00aaaa'
            elif part == 47:  # White background
                bg_color = '#aaaaaa'
            elif part == 100:  # Bright Black background
                bg_color = '#555555'
            elif part == 101:  # Bright Red background
                bg_color = '#ff5555'
            elif part == 102:  # Bright Green background
                bg_color = '#55ff55'
            elif part == 103:  # Bright Yellow background
                bg_color = '#ffff55'
            elif part == 104:  # Bright Blue background
                bg_color = '#5555ff'
            elif part == 105:  # Bright Magenta background
                bg_color = '#ff55ff'
            elif part == 106:  # Bright Cyan background
                bg_color = '#55ffff'
            elif part == 107:  # Bright White background
                bg_color = '#ffffff'
        
        if bg_color:
            styles.append(f'background-color: {bg_color}')
        
        if styles:
            style_str = '; '.join(styles)
            span_stack.append(style_str)
            return f'<span style="{style_str}">'
        
        return ''
    
    # Process ANSI escape sequences
    ansi_pattern = re.compile(r'\x1B\[([0-9;]*)m')
    html_text = ansi_pattern.sub(process_ansi_code, html_text)
    
    # Clean up any remaining malformed ANSI codes
    ansi_escape = re.compile(r'\x1B\[[0-9;]*[a-zA-Z]')
    html_text = ansi_escape.sub('', html_text)
    
    # Close any remaining open spans
    html_text += '</span>' * len(span_stack)
    
    return html_text

def convert_to_html(file_path):
    """Convert entire LinPEAS output to HTML format"""
    print(f"Converting {file_path} to HTML format...")
    
    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
        content = f.read()
    
    # Convert ANSI to HTML
    html_content = ansi_to_html(content)
    
    # Create HTML document
    html_template = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>LinPEAS Output - {filename}</title>
    <style>
        body {{
            background-color: #0d1117;
            color: #c9d1d9;
            font-family: 'Consolas', 'Monaco', 'Courier New', monospace;
            font-size: 14px;
            line-height: 1.4;
            margin: 20px;
            padding: 20px;
        }}
        
        .container {{
            max-width: 1200px;
            margin: 0 auto;
            background-color: #161b22;
            padding: 30px;
            border-radius: 8px;
            border: 1px solid #30363d;
            box-shadow: 0 8px 24px rgba(0, 0, 0, 0.3);
        }}
        
        .header {{
            text-align: center;
            margin-bottom: 30px;
            padding-bottom: 20px;
            border-bottom: 2px solid #21262d;
        }}
        
        .header h1 {{
            color: #58a6ff;
            margin: 0;
            font-size: 2.2em;
            text-shadow: 0 0 10px rgba(88, 166, 255, 0.3);
        }}
        
        .header p {{
            color: #8b949e;
            margin: 10px 0 0 0;
            font-style: italic;
        }}
        
        .content {{
            white-space: pre-wrap;
            word-wrap: break-word;
            background-color: #0d1117;
            padding: 25px;
            border-radius: 6px;
            border: 1px solid #21262d;
            overflow-x: auto;
        }}
        
        /* Custom scrollbar */
        .content::-webkit-scrollbar {{
            width: 12px;
        }}
        
        .content::-webkit-scrollbar-track {{
            background: #161b22;
        }}
        
        .content::-webkit-scrollbar-thumb {{
            background: #30363d;
            border-radius: 6px;
        }}
        
        .content::-webkit-scrollbar-thumb:hover {{
            background: #484f58;
        }}
        
        /* Make the output more readable */
        .content span {{
            text-shadow: 0 0 2px rgba(0, 0, 0, 0.5);
        }}
        
        /* Print styles */
        @media print {{
            body {{
                background-color: white;
                color: black;
            }}
            .container {{
                background-color: white;
                border: 1px solid #ccc;
                box-shadow: none;
            }}
            .content {{
                background-color: #f8f9fa;
                border: 1px solid #dee2e6;
            }}
        }}
        
        /* Mobile responsiveness */
        @media (max-width: 768px) {{
            body {{
                margin: 10px;
                padding: 10px;
            }}
            .container {{
                padding: 15px;
            }}
            .content {{
                padding: 15px;
                font-size: 12px;
            }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🔍 LinPEAS Security Analysis Report</h1>
            <p>Generated from: {filename}</p>
            <p>Converted on: {timestamp}</p>
        </div>
        <div class="content">{content}</div>
    </div>
    
    <script>
        // Add some interactivity
        document.addEventListener('DOMContentLoaded', function() {{
            // Add click to copy functionality for code blocks
            const content = document.querySelector('.content');
            content.addEventListener('dblclick', function() {{
                if (navigator.clipboard) {{
                    navigator.clipboard.writeText(this.textContent);
                    // Visual feedback
                    const originalBg = this.style.backgroundColor;
                    this.style.backgroundColor = '#1a472a';
                    setTimeout(() => {{
                        this.style.backgroundColor = originalBg;
                    }}, 200);
                }}
            }});
        }});
    </script>
</body>
</html>"""
    
    import os
    from datetime import datetime
    
    filename = os.path.basename(file_path)
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    html_output = html_template.format(
        filename=filename,
        timestamp=timestamp,
        content=html_content
    )
    
    # Save HTML file
    output_file = file_path.replace('.ansi', '.html')
    if output_file == file_path:  # If no .ansi extension, add .html
        output_file = file_path + '.html'
    
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(html_output)
    
    # Get file size for user info
    file_size = os.path.getsize(output_file)
    if file_size < 1024:
        size_str = f"{file_size} bytes"
    elif file_size < 1024 * 1024:
        size_str = f"{file_size // 1024}KB"
    else:
        size_str = f"{file_size // (1024 * 1024)}MB"
    
    print(f"HTML conversion completed!")
    print(f"Output saved to: {output_file}")
    print(f"File size: {size_str}")
    print(f"You can open it in any web browser to view the formatted LinPEAS output.")
    print(f"Double-click the content area to copy all text to clipboard.")
    
    # Ask user if they want to open the HTML file
    try:
        response = input("\nWould you like to open the HTML file in your browser? (y/n): ").strip().lower()
        if response in ['y', 'yes']:
            import subprocess
            subprocess.run(['xdg-open', output_file], check=False)
            print("Opening HTML file in default browser...")
    except KeyboardInterrupt:
        print("\nSkipping browser open.")
    except Exception as e:
        if DEBUG:
            print(f"[DEBUG] Error opening browser: {e}")
        print("Could not open browser automatically. You can manually open the HTML file.")
    
    return output_file

def terminal_extraction_mode(file_path, red_only=False):
    """Terminal extraction mode - display and save findings"""
    findings = extract_red_yellow_with_context(file_path, red_only)
    grouped_findings = group_findings_by_context(findings)
    
    marker_type = "red-only" if red_only else "red/yellow"
    print(f"\nFound {len(findings)} {marker_type} marked lines grouped by context:\n")
    
    # Display grouped findings
    for context, context_findings in grouped_findings.items():
        print("=" * 80)
        if context != "No Context":
            print(f"{context}")
        else:
            print("General Findings")
        print("=" * 80)
        
        for finding in context_findings:
            # Debug: show what words were extracted
            if DEBUG:
                print(f"[DEBUG] Highlighted words: {finding['highlighted_words']}")
            
            # Print the raw line with original ANSI colors
            print(f">>> {finding['raw_line']}")
            
        print("\n")
    
    # Also save to file with .ansi extension to preserve color codes
    suffix = '_red_only_extracted.ansi' if red_only else '_red_yellow_extracted.ansi'
    output_file = file_path.replace('.ansi', suffix)
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(f"LinPEAS {marker_type.title()} Findings Extraction\n")
        f.write(f"Source: {file_path}\n")
        f.write(f"Total findings: {len(findings)}\n")
        f.write("=" * 80 + "\n\n")
        
        # Write grouped findings to file
        for context, context_findings in grouped_findings.items():
            f.write("=" * 80 + "\n")
            if context != "No Context":
                f.write(f"{context}\n")
            else:
                f.write("General Findings\n")
            f.write("=" * 80 + "\n")
            
            for finding in context_findings:
                # Write the raw line with original ANSI codes to preserve colors in output file
                f.write(f">>> {finding['raw_line']}\n")
                
            f.write("\n\n")
    
    print(f"Results also saved to: {output_file}")

def html_extraction_mode(file_path, red_only=False):
    """HTML extraction mode - convert extracted findings to HTML"""
    findings = extract_red_yellow_with_context(file_path, red_only)
    grouped_findings = group_findings_by_context(findings)
    
    marker_type = "red-only" if red_only else "red/yellow"
    print(f"Converting {len(findings)} {marker_type} findings to HTML format...")
    
    # Build content for HTML
    content_lines = []
    content_lines.append(f"LinPEAS {marker_type.title()} Findings Extraction")
    content_lines.append(f"Source: {file_path}")
    content_lines.append(f"Total findings: {len(findings)}")
    content_lines.append("=" * 80)
    content_lines.append("")
    
    for context, context_findings in grouped_findings.items():
        content_lines.append("=" * 80)
        if context != "No Context":
            content_lines.append(f"{context}")
        else:
            content_lines.append("General Findings")
        content_lines.append("=" * 80)
        
        for finding in context_findings:
            content_lines.append(f">>> {finding['raw_line']}")
        
        content_lines.append("")
        content_lines.append("")
    
    # Convert to HTML
    content = '\n'.join(content_lines)
    html_content = ansi_to_html(content)
    
    import os
    from datetime import datetime
    
    filename = os.path.basename(file_path)
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    marker_title = marker_type.title()
    
    # Create HTML document  
    html_template = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>LinPEAS {marker_title} Findings - {filename}</title>
    <style>
        body {{
            background-color: #0d1117;
            color: #c9d1d9;
            font-family: 'Consolas', 'Monaco', 'Courier New', monospace;
            font-size: 14px;
            line-height: 1.4;
            margin: 20px;
            padding: 20px;
        }}
        
        .container {{
            max-width: 1200px;
            margin: 0 auto;
            background-color: #161b22;
            padding: 30px;
            border-radius: 8px;
            border: 1px solid #30363d;
            box-shadow: 0 8px 24px rgba(0, 0, 0, 0.3);
        }}
        
        .header {{
            text-align: center;
            margin-bottom: 30px;
            padding-bottom: 20px;
            border-bottom: 2px solid #21262d;
        }}
        
        .header h1 {{
            color: #58a6ff;
            margin: 0;
            font-size: 2.2em;
            text-shadow: 0 0 10px rgba(88, 166, 255, 0.3);
        }}
        
        .header p {{
            color: #8b949e;
            margin: 10px 0 0 0;
            font-style: italic;
        }}
        
        .content {{
            white-space: pre-wrap;
            word-wrap: break-word;
            background-color: #0d1117;
            padding: 25px;
            border-radius: 6px;
            border: 1px solid #21262d;
            overflow-x: auto;
        }}
        
        /* Custom scrollbar */
        .content::-webkit-scrollbar {{
            width: 12px;
        }}
        
        .content::-webkit-scrollbar-track {{
            background: #161b22;
        }}
        
        .content::-webkit-scrollbar-thumb {{
            background: #30363d;
            border-radius: 6px;
        }}
        
        .content::-webkit-scrollbar-thumb:hover {{
            background: #484f58;
        }}
        
        /* Print styles */
        @media print {{
            body {{
                background-color: white;
                color: black;
            }}
            .container {{
                background-color: white;
                border: 1px solid #ccc;
                box-shadow: none;
            }}
            .content {{
                background-color: #f8f9fa;
                border: 1px solid #dee2e6;
            }}
        }}
        
        /* Mobile responsiveness */
        @media (max-width: 768px) {{
            body {{
                margin: 10px;
                padding: 10px;
            }}
            .container {{
                padding: 15px;
            }}
            .content {{
                padding: 15px;
                font-size: 12px;
            }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🔍 LinPEAS {marker_title} Findings Report</h1>
            <p>Generated from: {filename}</p>
            <p>Converted on: {timestamp}</p>
        </div>
        <div class="content">{html_content}</div>
    </div>
    
    <script>
        // Add some interactivity
        document.addEventListener('DOMContentLoaded', function() {{
            // Add click to copy functionality for code blocks
            const content = document.querySelector('.content');
            content.addEventListener('dblclick', function() {{
                if (navigator.clipboard) {{
                    navigator.clipboard.writeText(this.textContent);
                    // Visual feedback
                    const originalBg = this.style.backgroundColor;
                    this.style.backgroundColor = '#1a472a';
                    setTimeout(() => {{
                        this.style.backgroundColor = originalBg;
                    }}, 200);
                }}
            }});
        }});
    </script>
</body>
</html>"""
    
    html_output = html_template
    
    # Save HTML file
    suffix = '_red_only_findings.html' if red_only else '_red_yellow_findings.html'
    output_file = file_path.replace('.ansi', suffix)
    if output_file == file_path:  # If no .ansi extension, add suffix
        output_file = file_path + suffix
    
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(html_output)
    
    # Get file size for user info
    file_size = os.path.getsize(output_file)
    if file_size < 1024:
        size_str = f"{file_size} bytes"
    elif file_size < 1024 * 1024:
        size_str = f"{file_size // 1024}KB"
    else:
        size_str = f"{file_size // (1024 * 1024)}MB"
    
    print(f"HTML conversion completed!")
    print(f"Output saved to: {output_file}")
    print(f"File size: {size_str}")
    print(f"You can open it in any web browser to view the {marker_type} findings.")
    print(f"Double-click the content area to copy all text to clipboard.")
    
    # Ask user if they want to open the HTML file
    try:
        response = input("\nWould you like to open the HTML file in your browser? (y/n): ").strip().lower()
        if response in ['y', 'yes']:
            import subprocess
            subprocess.run(['xdg-open', output_file], check=False)
            print("Opening HTML file in default browser...")
    except KeyboardInterrupt:
        print("\nSkipping browser open.")
    except Exception as e:
        if DEBUG:
            print(f"[DEBUG] Error opening browser: {e}")
        print("Could not open browser automatically. You can manually open the HTML file.")

def main():
    parser = argparse.ArgumentParser(
        description='LinPEAS Output Processor - Extract findings or convert to HTML',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python3 linpeas_extractor.py                          Show this help menu
  python3 linpeas_extractor.py -yr output.ansi            Extract red/yellow findings to terminal and .ansi file
  python3 linpeas_extractor.py -r output.ansi             Extract red-only findings to terminal and .ansi file
  python3 linpeas_extractor.py --html output.ansi         Convert complete LinPEAS to HTML
  python3 linpeas_extractor.py --html -yr output.ansi     Convert red/yellow findings to HTML
  python3 linpeas_extractor.py --html -r output.ansi      Convert red-only findings to HTML
        """)
    
    parser.add_argument('file', nargs='?', help='LinPEAS output file (usually .ansi)')
    parser.add_argument('-yr', action='store_true', 
                       help='Extract red/yellow highlighted lines (high priority findings)')
    parser.add_argument('-r', action='store_true',
                       help='Extract red-only lines (medium priority findings)')
    parser.add_argument('--html', action='store_true',
                       help='Output in HTML format instead of terminal/ansi')
    parser.add_argument('--debug', action='store_true', 
                       help='Enable debug output')
    
    args = parser.parse_args()
    
    # If no file provided or no arguments, show help
    if not args.file or (not args.yr and not args.r and not args.html):
        parser.print_help()
        return
    
    # Check for mutually exclusive extraction options
    if args.yr and args.r:
        print("Error: -yr and -r cannot be used together")
        sys.exit(1)
    
    global DEBUG
    DEBUG = args.debug
    
    try:
        # Determine mode
        if args.html:
            # HTML mode
            if args.yr:
                # HTML red/yellow extraction
                html_extraction_mode(args.file, red_only=False)
            elif args.r:
                # HTML red-only extraction  
                html_extraction_mode(args.file, red_only=True)
            else:
                # Complete HTML conversion
                convert_to_html(args.file)
        else:
            # Terminal mode
            if args.yr:
                # Terminal red/yellow extraction
                terminal_extraction_mode(args.file, red_only=False)
            elif args.r:
                # Terminal red-only extraction
                terminal_extraction_mode(args.file, red_only=True)
            else:
                # Should not reach here due to earlier check
                parser.print_help()
                return
        
    except FileNotFoundError:
        print(f"Error: File '{args.file}' not found.")
        sys.exit(1)
    except Exception as e:
        print(f"Error processing file: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
