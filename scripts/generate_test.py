#!/usr/bin/env python3
"""
Test Generator Script
Generates tests from the question bank according to test_config.yaml
"""

import os
import sys
import yaml
import pandas as pd
import json
import random
import math
import re
from pathlib import Path
from typing import Dict, List, Tuple, Any


# PDF generation imports
try:
    from reportlab.pdfgen import canvas
    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak, Image, Table, TableStyle
    from reportlab.platypus.flowables import HRFlowable
    from reportlab.lib.units import inch, cm
    import markdown2
    PDF_AVAILABLE = True
except ImportError:
    PDF_AVAILABLE = False

class TestGenerator:
    def __init__(self, config_path: str = "test_config.yaml"):
        """Initialize the test generator with configuration."""
        self.config_path = config_path
        self.config = self.load_config()
        self.questions_df = None
        self.mappings = None
        self.setup_random_seed()
        
    def load_config(self) -> Dict:
        """Load the test configuration from YAML file."""
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f)
        except FileNotFoundError:
            print(f"Error: Configuration file '{self.config_path}' not found.")
            sys.exit(1)
        except yaml.YAMLError as e:
            print(f"Error parsing YAML configuration: {e}")
            sys.exit(1)
    
    def setup_random_seed(self):
        """Set up random seed for reproducibility."""
        seed = self.config.get('advanced', {}).get('random_seed')
        if seed is not None:
            random.seed(seed)
            
    def load_questions(self) -> pd.DataFrame:
        """Load all questions from CSV files."""
        questions_dir = Path("../questions")
        if not questions_dir.exists():
            questions_dir = Path("questions")
            
        if not questions_dir.exists():
            raise FileNotFoundError("Questions directory not found. Expected '../questions' or 'questions'")
            
        # Load mappings
        mappings_path = questions_dir / "mappings.yaml"
        with open(mappings_path, 'r', encoding='utf-8') as f:
            self.mappings = yaml.safe_load(f)
            
        # Load all question CSV files
        all_questions = []
        for csv_file in questions_dir.glob("cat_*.csv"):
            df = pd.read_csv(csv_file, encoding='utf-8')
            all_questions.append(df)
            
        if not all_questions:
            raise FileNotFoundError("No question CSV files found in questions directory")
            
        self.questions_df = pd.concat(all_questions, ignore_index=True)
        print(f"Loaded {len(self.questions_df)} questions from {len(all_questions)} categories")
        
        return self.questions_df
    
    def get_difficulty_distribution(self) -> Dict[str, Tuple[int, int]]:
        """
        Get question counts and points for each difficulty level from config.
        Returns: Dict[difficulty, (count, points_per_question)]
        """
        difficulty_config = self.config['question_selection']['difficulty_config']
        
        # Get points per question (same for all difficulties)
        points_per_question = difficulty_config.get('points_per_question', 5)
        
        # Use difficulty distribution directly from config
        distribution = difficulty_config['difficulty_distribution']
        return {diff: (count, points_per_question) 
               for diff, count in distribution.items()}
    
    def filter_questions_by_categories(self, df: pd.DataFrame) -> pd.DataFrame:
        """Filter questions based on selected categories."""
        categories = self.config['question_selection']['categories']
        
        if "*" in categories:
            return df  # Return all questions
        
        # Convert category names to snake_case if needed
        snake_case_categories = []
        for cat in categories:
            if cat in self.mappings['categories'].values():
                # Find the snake_case key for this human-readable value
                for key, value in self.mappings['categories'].items():
                    if value == cat:
                        snake_case_categories.append(key)
                        break
            else:
                snake_case_categories.append(cat)
        
        return df[df['category'].isin(snake_case_categories)]
    
    def select_questions(self) -> List[Dict]:
        """Select questions according to difficulty distribution and preferences."""
        if self.questions_df is None:
            self.load_questions()
            
        # Filter by categories
        filtered_df = self.filter_questions_by_categories(self.questions_df)
        
        # Apply question type preferences to avoid duplicates
        preferred_types = self.config.get('question_selection', {}).get('preferred_question_types', 
                                                                        ['multiple_choice', 'short_answer', 'free_text', 'code', 'essay'])
        
        # For each unique hash, keep only the most preferred type
        unique_questions = []
        seen_hashes = set()
        
        for preferred_type in preferred_types:
            type_questions = filtered_df[filtered_df['type'] == preferred_type]
            for _, question in type_questions.iterrows():
                if question['hash'] not in seen_hashes:
                    unique_questions.append(question)
                    seen_hashes.add(question['hash'])
        
        # Convert back to DataFrame
        filtered_df = pd.DataFrame(unique_questions)
        
        # Get difficulty distribution from config
        difficulty_dist = self.get_difficulty_distribution()
        
        selected_questions = []
        
        for difficulty, (count, points) in difficulty_dist.items():
            # Convert difficulty to lowercase for matching
            diff_lower = difficulty.lower().replace(' ', '_')
            
            # Filter questions by difficulty
            difficulty_questions = filtered_df[
                filtered_df['difficulty'].str.lower().str.replace(' ', '_') == diff_lower
            ].copy()
            
            if len(difficulty_questions) == 0:
                print(f"Warning: No questions found for difficulty '{difficulty}'")
                continue
                
            if len(difficulty_questions) < count:
                print(f"Warning: Only {len(difficulty_questions)} questions available for "
                      f"difficulty '{difficulty}', requested {count}")
                count = len(difficulty_questions)
            
            # Sample questions
            sampled = difficulty_questions.sample(n=count).to_dict('records')
            
            # Add calculated points to each question
            for question in sampled:
                question['calculated_points'] = points
                question['original_difficulty'] = difficulty
                
            selected_questions.extend(sampled)
        
        # Sort questions by difficulty (easiest to hardest) if not shuffling
        if not self.config['test_settings'].get('shuffle_questions', False):
            # Define difficulty order (easiest to hardest)
            difficulty_order = {
                'trivial': 1,
                'easy': 2, 
                'medium': 3,
                'hard': 4,
                'very hard': 5,
                'very_hard': 5  # Handle both formats
            }
            
            # Sort questions by difficulty order
            selected_questions.sort(key=lambda q: difficulty_order.get(
                q.get('original_difficulty', '').lower().replace(' ', '_'), 999
            ))
        else:
            # Shuffle questions if requested
            random.shuffle(selected_questions)
            
        return selected_questions
    
    def format_question(self, question: Dict, question_num: int) -> str:
        """Format a single question for output."""
        format_config = self.config['question_format']
        
        # Question numbering
        numbering_style = format_config.get('numbering_style', 'numeric')
        if numbering_style == 'numeric':
            num_str = f"{question_num}."
        elif numbering_style == 'alphabetic':
            num_str = f"{chr(ord('a') + question_num - 1)})"
        elif numbering_style == 'roman':
            # Simple roman numerals for small numbers
            roman_nums = ['i', 'ii', 'iii', 'iv', 'v', 'vi', 'vii', 'viii', 'ix', 'x']
            num_str = f"{roman_nums[min(question_num - 1, 9)]}"
        else:
            num_str = f"{question_num}."
        
        # Build question text
        question_text = f"{num_str} {question['question']}"
        
        # Add labels if requested
        labels = []
        if format_config.get('include_difficulty_label', False):
            labels.append(f"[{question['original_difficulty']}]")
        if format_config.get('include_category_label', False):
            category_name = self.mappings['categories'].get(question['category'], question['category'])
            labels.append(f"[{category_name}]")
        
        if labels:
            question_text += f" {' '.join(labels)}"
            
        # Add points
        question_text += f" **({question['calculated_points']} puncte)**"
        
        # Handle multiple choice options
        if question['type'] == 'multiple_choice' and question.get('options'):
            try:
                options_data = question['options']
                if isinstance(options_data, str):
                    options = json.loads(options_data)
                    if self.config['test_settings'].get('shuffle_options', False):
                        random.shuffle(options)
                        
                    question_text += "\n\n"
                    for i, option in enumerate(options):
                        question_text += f"   {chr(ord('a') + i)}) {option}\n"
                else:
                    # Skip if options is not a string (might be NaN/float)
                    pass
            except (json.JSONDecodeError, TypeError, ValueError):
                print(f"Warning: Could not parse options for question {question['hash']}")
        
        return question_text
    
    def generate_test_content(self, questions: List[Dict]) -> str:
        """Generate the complete test content."""
        content = []
        
        # Add header
        if self.config.get('header', {}).get('include', False):
            header_content = self.config['header'].get('content', '')
            content.append(header_content)
            content.append("")
        
        # Add title and subtitle
        title = self.config['test_settings'].get('title', 'Test')
        subtitle = self.config['test_settings'].get('subtitle', '')
        time_limit = self.config['test_settings'].get('time_limit_minutes', 60)
        total_points = sum(q['calculated_points'] for q in questions)
        
        content.append(f"# {title}")
        if subtitle:
            content.append(f"## {subtitle}")
        content.append(f"**Timp de lucru:** {time_limit} minute     **Total puncte:** {total_points}")
        content.append("")
        content.append("---")
        content.append("")
        
        # Add questions
        for i, question in enumerate(questions, 1):
            formatted_question = self.format_question(question, i)
            content.append(formatted_question)
            content.append("")
        
        # Add footer
        if self.config.get('footer', {}).get('include', False):
            footer_content = self.config['footer'].get('content', '')
            content.append(footer_content)
        
        return "\n".join(content)
    
    def generate_answer_key(self, questions: List[Dict]) -> str:
        """Generate answer key for the test."""
        content = []
        content.append("# Answer Key")
        content.append("")
        
        for i, question in enumerate(questions, 1):
            answer_text = f"{i}. "
            
            if question['type'] == 'multiple_choice':
                correct = question.get('correct_answer', 'N/A')
                try:
                    options_data = question['options']
                    if isinstance(options_data, str):
                        options = json.loads(options_data)
                    else:
                        # Handle case where options is already parsed or is NaN/float
                        options = []
                    if correct in options:
                        answer_index = options.index(correct)
                        answer_text += f"{chr(ord('a') + answer_index)}) {correct}"
                    else:
                        answer_text += str(correct)
                except (json.JSONDecodeError, TypeError, ValueError):
                    answer_text += str(question.get('correct_answer', 'N/A'))
            else:
                correct_answer = question.get('correct_answer', 'Open answer')
                answer_text += str(correct_answer) if correct_answer is not None else 'Open answer'
            
            answer_text += f" ({question['calculated_points']} puncte)"
            content.append(answer_text)
        
        return "\n".join(content)
    
    def generate_pdf_content(self, questions: List[Dict]) -> str:
        """Generate HTML content suitable for PDF conversion."""
        content = []
        
        # Add CSS for PDF formatting
        content.append("""
        <style>
        @page {
            size: A4;
            margin: 2cm;
        }
        body {
            font-family: 'Times New Roman', Times, serif;
            font-size: 12pt;
            line-height: 1.4;
            color: #000;
        }
        h1 {
            font-size: 18pt;
            text-align: center;
            margin-bottom: 10pt;
            border-bottom: 2px solid #000;
            padding-bottom: 5pt;
        }
        h2 {
            font-size: 14pt;
            text-align: center;
            margin-bottom: 8pt;
        }
        .header-info {
            text-align: center;
            margin-bottom: 20pt;
            font-weight: bold;
        }
        .student-info {
            border: 1px solid #000;
            padding: 10pt;
            margin-bottom: 20pt;
        }
        .question {
            margin-bottom: 15pt;
            page-break-inside: avoid;
        }
        .question-number {
            font-weight: bold;
        }
        .points {
            font-weight: bold;
        }
        .options {
            margin-left: 20pt;
            margin-top: 5pt;
        }
        .option {
            margin-bottom: 3pt;
        }
        code {
            font-family: 'Courier New', Courier, monospace;
            background-color: #f5f5f5;
            padding: 2pt;
            border-radius: 3pt;
        }
        .footer {
            margin-top: 30pt;
            border-top: 1px solid #000;
            padding-top: 10pt;
        }
        </style>
        """)
        
        # Add header
        if self.config.get('header', {}).get('include', False):
            header_content = self.config['header'].get('content', '')
            # Convert markdown header to HTML
            header_html = markdown2.markdown(header_content)
            content.append(f'<div class="student-info">{header_html}</div>')
        
        # Add title and test info
        title = self.config['test_settings'].get('title', 'Test')
        subtitle = self.config['test_settings'].get('subtitle', '')
        time_limit = self.config['test_settings'].get('time_limit_minutes', 60)
        total_points = sum(q['calculated_points'] for q in questions)
        
        content.append(f'<h1>{title}</h1>')
        if subtitle:
            content.append(f'<h2>{subtitle}</h2>')
        
        content.append('<div class="header-info">')
        content.append(f'<p><strong>Timp de lucru:</strong> {time_limit} minute   <strong>Total puncte:</strong> {total_points}</p>')
        content.append('</div>')
        
        content.append('<hr>')
        
        # Add questions
        for i, question in enumerate(questions, 1):
            content.append('<div class="question">')
            
            # Question text with formatting
            question_text = self.format_question_for_pdf(question, i)
            content.append(question_text)
            
            content.append('</div>')
        
        # Add footer
        if self.config.get('footer', {}).get('include', False):
            footer_content = self.config['footer'].get('content', '')
            footer_html = markdown2.markdown(footer_content)
            content.append(f'<div class="footer">{footer_html}</div>')
        
        return '\n'.join(content)
    
    def format_question_for_pdf(self, question: Dict, question_num: int) -> str:
        """Format a single question for PDF output."""
        format_config = self.config['question_format']
        
        # Question numbering
        numbering_style = format_config.get('numbering_style', 'numeric')
        if numbering_style == 'numeric':
            num_str = f"{question_num}."
        elif numbering_style == 'alphabetic':
            num_str = f"{chr(ord('a') + question_num - 1)})"
        elif numbering_style == 'roman':
            roman_nums = ['i', 'ii', 'iii', 'iv', 'v', 'vi', 'vii', 'viii', 'ix', 'x']
            num_str = f"{roman_nums[min(question_num - 1, 9)]}"
        else:
            num_str = f"{question_num}."
        
        # Build question text
        question_text = question['question']
        
        # Convert markdown formatting to HTML
        # Handle code blocks
        question_text = re.sub(r'`([^`]+)`', r'<code>\1</code>', question_text)
        
        # Add labels if requested
        labels = []
        if format_config.get('include_difficulty_label', False):
            labels.append(f"[{question['original_difficulty']}]")
        if format_config.get('include_category_label', False):
            category_name = self.mappings['categories'].get(question['category'], question['category'])
            labels.append(f"[{category_name}]")
        
        label_text = f" {' '.join(labels)}" if labels else ""
        
        # Build HTML
        html_parts = []
        html_parts.append(f'<p><span class="question-number">{num_str}</span> {question_text}{label_text} ')
        html_parts.append(f'<span class="points">({question["calculated_points"]} <strong>puncte</strong>)</span></p>')
        
        # Handle multiple choice options
        if question['type'] == 'multiple_choice' and question.get('options'):
            try:
                options_data = question['options']
                if isinstance(options_data, str):
                    options = json.loads(options_data)
                    if self.config['test_settings'].get('shuffle_options', False):
                        random.shuffle(options)
                    
                    html_parts.append('<div class="options">')
                    for i, option in enumerate(options):
                        option_text = re.sub(r'`([^`]+)`', r'<code>\1</code>', str(option))
                        html_parts.append(f'<div class="option">{chr(ord("a") + i)}) {option_text}</div>')
                    html_parts.append('</div>')
            except (json.JSONDecodeError, TypeError, ValueError):
                pass
        
        return ''.join(html_parts)
    
    def convert_math_formulas(self, text: str) -> str:
        """Convert LaTeX math expressions to readable text format for PDF."""
        if not text:
            return text
        
        # Common LaTeX mathematical symbol replacements
        math_replacements = {
            r'\\pm': '±',
            r'\\mp': '∓', 
            r'\\times': '×',
            r'\\div': '÷',
            r'\\cdot': '·',
            r'\\sqrt{([^}]+)}': r'√(\1)',
            r'\\frac{([^}]+)}{([^}]+)}': r'(\1)/(\2)',
            r'\\Delta': 'Δ',
            r'\\delta': 'δ',
            r'\\alpha': 'α',
            r'\\beta': 'β',
            r'\\gamma': 'γ',
            r'\\theta': 'θ',
            r'\\pi': 'π',
            r'\\sigma': 'σ',
            r'\\omega': 'ω',
            r'\\lambda': 'λ',
            r'\\mu': 'μ',
            r'\\epsilon': 'ε',
            r'\\sum': 'Σ',
            r'\\prod': 'Π',
            r'\\int': '∫',
            r'\\infty': '∞',
            r'\\le': '≤',
            r'\\ge': '≥',
            r'\\ne': '≠',
            r'\\approx': '≈',
            r'\\equiv': '≡',
            r'\\subset': '⊂',
            r'\\supset': '⊃',
            r'\\in': '∈',
            r'\\notin': '∉',
            r'\\cup': '∪',
            r'\\cap': '∩',
            r'\\emptyset': '∅',
            r'\\partial': '∂',
            r'\\nabla': '∇',
            r'\\to': '→',
            r'\\rightarrow': '→',
            r'\\leftarrow': '←',
            r'\\leftrightarrow': '↔',
            r'\\uparrow': '↑',
            r'\\downarrow': '↓',
        }
        
        # Process inline math expressions $...$ 
        def replace_inline_math(match):
            math_content = match.group(1)
            # Apply symbol replacements
            for latex_symbol, unicode_symbol in math_replacements.items():
                math_content = re.sub(latex_symbol, unicode_symbol, math_content)
            
            # Handle power notation
            math_content = re.sub(r'\^{([^}]+)}', r'^(\1)', math_content)
            math_content = re.sub(r'\^([a-zA-Z0-9])', r'^(\1)', math_content)
            
            # Handle subscript notation  
            math_content = re.sub(r'_{([^}]+)}', r'_(\1)', math_content)
            math_content = re.sub(r'_([a-zA-Z0-9])', r'_(\1)', math_content)
            
            # Clean up extra backslashes and braces
            math_content = re.sub(r'\\([a-zA-Z])', r'\1', math_content)
            math_content = re.sub(r'[{}]', '', math_content)
            
            return math_content
        
        # Replace $...$ with processed math
        text = re.sub(r'\$([^$]+)\$', replace_inline_math, text)
        
        # Process display math expressions $$...$$ 
        def replace_display_math(match):
            math_content = match.group(1)
            # Apply same transformations as inline math
            for latex_symbol, unicode_symbol in math_replacements.items():
                math_content = re.sub(latex_symbol, unicode_symbol, math_content)
            
            math_content = re.sub(r'\^{([^}]+)}', r'^(\1)', math_content)
            math_content = re.sub(r'\^([a-zA-Z0-9])', r'^(\1)', math_content)
            math_content = re.sub(r'_{([^}]+)}', r'_(\1)', math_content)
            math_content = re.sub(r'_([a-zA-Z0-9])', r'_(\1)', math_content)
            math_content = re.sub(r'\\([a-zA-Z])', r'\1', math_content)
            math_content = re.sub(r'[{}]', '', math_content)
            
            return f"\n{math_content}\n"
        
        # Replace $$...$$ with processed math
        text = re.sub(r'\$\$([^$]+)\$\$', replace_display_math, text)
        
        return text
    
    def save_pdf(self, html_content: str, filename: str, questions: List[Dict] = None) -> str:
        """Save HTML content as PDF using ReportLab."""
        if not PDF_AVAILABLE:
            print("Warning: PDF libraries not available. Cannot generate PDF.")
            return ""
        
        try:
            # Create PDF using ReportLab directly with output directory support
            output_dir = self.config['test_settings'].get('output_directory', 'out')
            pdf_filename = filename.replace('.md', '.pdf')
            pdf_path = Path(output_dir) / pdf_filename
            pdf_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Create PDF using ReportLab with UTF-8 support
            doc = SimpleDocTemplate(str(pdf_path), pagesize=A4,
                                  rightMargin=2*cm, leftMargin=2*cm,
                                  topMargin=2*cm, bottomMargin=2*cm)
            
            styles = getSampleStyleSheet()
            
            # Create custom styles with UTF-8 font support
            from reportlab.lib.fonts import addMapping
            from reportlab.pdfbase import pdfmetrics
            from reportlab.pdfbase.ttfonts import TTFont
            
            # Try to register a Unicode-capable font for Romanian characters
            font_name = 'Helvetica'
            try:
                # Try to register DejaVu Sans which has full Romanian character support
                import os
                possible_fonts = [
                    'C:/Windows/Fonts/DejaVuSans.ttf',
                    'C:/Windows/Fonts/Arial.ttf',
                    'C:/Windows/Fonts/calibri.ttf',
                    '/System/Library/Fonts/Arial.ttf',  # macOS
                    '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'  # Linux
                ]
                
                font_registered = False
                for font_path in possible_fonts:
                    if os.path.exists(font_path):
                        try:
                            pdfmetrics.registerFont(TTFont('UnicodeFont', font_path))
                            font_name = 'UnicodeFont'
                            font_registered = True
                            break
                        except:
                            continue
                
                if not font_registered:
                    print("Warning: Could not register Unicode font, using Helvetica with character replacement")
            except Exception as e:
                print(f"Warning: Font registration failed: {e}, using Helvetica")
            
            title_style = ParagraphStyle(
                'CustomTitle',
                parent=styles['Heading1'],
                fontSize=18,
                fontName=font_name,
                spaceAfter=12,
                alignment=1,  # Center
                borderWidth=2,
                borderColor=colors.black,
                borderPadding=5
            )
            
            subtitle_style = ParagraphStyle(
                'CustomSubtitle',
                parent=styles['Heading2'],
                fontSize=14,
                fontName=font_name,
                spaceAfter=8,
                alignment=1  # Center
            )
            
            question_style = ParagraphStyle(
                'Question',
                parent=styles['Normal'],
                fontSize=12,
                fontName=font_name,
                spaceAfter=10,
                spaceBefore=5
            )
            
            option_style = ParagraphStyle(
                'Option',
                parent=styles['Normal'],
                fontSize=11,
                fontName=font_name,
                leftIndent=20,
                spaceAfter=3
            )
            
            header_style = ParagraphStyle(
                'Header',
                parent=styles['Normal'],
                fontSize=11,
                fontName=font_name,
                spaceAfter=6,
                alignment=1  # Center
            )
            
            # Build story (content for PDF)
            story : list[Paragraph | Spacer | HRFlowable] = []
            
            # Define safe_encode function for use throughout PDF generation
            def safe_encode(text):
                """Safely encode text for PDF, preserving Romanian characters when possible."""
                if not text:
                    return ""
                
                # If we have Unicode font registered, use text as-is
                if font_name == 'UnicodeFont':
                    return text
                
                # Otherwise, fall back to character replacement for compatibility
                romanian_chars = {
                    'ă': 'a', 'â': 'a', 'î': 'i', 'ș': 's', 'ț': 't',
                    'Ă': 'A', 'Â': 'A', 'Î': 'I', 'Ș': 'S', 'Ț': 'T',
                    'ţ': 't', 'Ţ': 'T', 'ş': 's', 'Ş': 'S'  # Alternative forms
                }
                
                # Replace Romanian characters with ASCII equivalents only as fallback
                result = text
                for romanian, replacement in romanian_chars.items():
                    result = result.replace(romanian, replacement)
                
                return result
            
            # Add logo and student info in the same row
            try:
                logo_path = Path(__file__).parent.parent / "assets" / "PCLP1.png"
                if logo_path.exists():
                    # Create a table with logo on left and student info on right
                    logo = Image(str(logo_path))
                    # Better proportions for the logo
                    logo.drawHeight = 1*inch
                    logo.drawWidth = 2*inch
                    
                    # Student info for the right side
                    name_field = safe_encode("Nume și Prenume:")
                    group_field = safe_encode("Grupă:")
                    date_field = safe_encode("Data:")
                    
                    # Create student info as separate paragraphs to avoid HTML parsing issues
                    student_info_lines = [
                        f"<b>{name_field}</b> {'_' * 30}",
                        "",  # Empty line
                        f"<b>{group_field}</b> {'_' * 15}  <b>{date_field}</b> {'_' * 15}"
                    ]
                    
                    # Create a single paragraph with proper line breaks
                    student_info_text = "<br/>".join(student_info_lines)
                    student_info_para = Paragraph(student_info_text, header_style)
                    
                    # Create table with logo and student info
                    header_data = [[logo, student_info_para]]
                    header_table = Table(header_data, colWidths=[6*cm, 11*cm])
                    header_table.setStyle(TableStyle([
                        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                        ('LEFTPADDING', (0, 0), (0, 0), 0),
                        ('RIGHTPADDING', (1, 0), (1, 0), 0),
                        ('TOPPADDING', (0, 0), (-1, -1), 0),
                        ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
                    ]))
                    story.append(header_table)
                else:
                    # Fallback if no logo - just student info
                    name_field = safe_encode("Nume și Prenume:")
                    group_field = safe_encode("Grupă:")
                    date_field = safe_encode("Data:")
                    
                    story.append(Paragraph(f"<b>{name_field}</b> {'_' * 50}", header_style))
                    story.append(Spacer(1, 8))
                    story.append(Paragraph(f"<b>{group_field}</b> {'_' * 20}    <b>{date_field}</b> {'_' * 20}", header_style))
                    story.append(Spacer(1, 12))
            except Exception as e:
                print(f"Note: Could not add header with logo: {e}")
                # Simple fallback
                name_field = safe_encode("Nume și Prenume:")
                group_field = safe_encode("Grupă:")
                date_field = safe_encode("Data:")
                
                story.append(Paragraph(f"<b>{name_field}</b> {'_' * 50}", header_style))
                story.append(Spacer(1, 8))
                story.append(Paragraph(f"<b>{group_field}</b> {'_' * 20}    <b>{date_field}</b> {'_' * 20}", header_style))
                story.append(Spacer(1, 12))
            
            # Add university header ONCE, below the logo/student info
            university_header = safe_encode("Universitatea Politehnica București")
            faculty_header = safe_encode("Facultatea de Automatică și Calculatoare")
            
            # story.append(Paragraph(f"<b>{university_header}</b>", header_style))
            # story.append(Paragraph(f"<b>{faculty_header}</b>", header_style))
            story.append(HRFlowable(width="100%"))
            story.append(Spacer(1, 12))
            
            # Parse the markdown content to extract title, questions, etc.
            lines = html_content.split('\n')
            # Use provided questions or select new ones if not provided
            if questions is None:
                questions = self.select_questions()  # Get questions for processing
            
            # Add header info
            if self.config.get('header', {}).get('include', False):
                header_content = self.config['header'].get('content', '')
                # Convert markdown to simple text for PDF with proper encoding
                header_lines = header_content.split('\n')
                for line in header_lines:
                    if line.strip():
                        # Remove markdown formatting for PDF and handle Romanian characters
                        clean_line = re.sub(r'\*\*(.*?)\*\*', r'\1', line)
                        clean_line = re.sub(r'---', '', clean_line)
                        if clean_line.strip():
                            # Ensure proper encoding for Romanian characters
                            try:
                                story.append(Paragraph(clean_line.strip(), header_style))
                            except Exception as e:
                                # Fallback: replace problematic characters
                                safe_line = clean_line.encode('ascii', 'ignore').decode('ascii')
                                story.append(Paragraph(safe_line.strip(), header_style))
                story.append(Spacer(1, 6))  # Reduced from 12
            
            # Add title with proper encoding
            title = self.config['test_settings'].get('title', 'Test')
            try:
                story.append(Paragraph(title, title_style))
            except:
                # Fallback for problematic characters
                safe_title = title.encode('ascii', 'ignore').decode('ascii')
                story.append(Paragraph(safe_title, title_style))
            
            subtitle = self.config['test_settings'].get('subtitle', '')
            if subtitle:
                try:
                    story.append(Paragraph(subtitle, subtitle_style))
                except:
                    safe_subtitle = subtitle.encode('ascii', 'ignore').decode('ascii')
                    story.append(Paragraph(safe_subtitle, subtitle_style))
            
            # Add test info
            time_limit = self.config['test_settings'].get('time_limit_minutes', 60)
            total_points = sum(q['calculated_points'] for q in questions)
            
            story.append(Paragraph(f"<b>Timp de lucru:</b> {time_limit} minute", header_style))
            story.append(Paragraph(f"<b>Total puncte:</b> {total_points}", header_style))
            story.append(HRFlowable(width="100%"))
            story.append(Spacer(1, 6))  # Reduced from 12
            
            # Add questions
            for i, question in enumerate(questions, 1):
                # Question number and text with proper encoding
                question_text = question['question']
                
                question_text = safe_encode(question_text)
                
                # Convert LaTeX math expressions to readable format
                question_text = self.convert_math_formulas(question_text)
                
                # Convert markdown code to basic formatting
                question_text = re.sub(r'`([^`]+)`', r'<font name="Courier">\1</font>', question_text)
                
                # Add labels if requested
                format_config = self.config['question_format']
                labels = []
                if format_config.get('include_difficulty_label', False):
                    labels.append(f"[{question['original_difficulty']}]")
                if format_config.get('include_category_label', False):
                    category_name = self.mappings['categories'].get(question['category'], question['category'])
                    labels.append(f"[{category_name}]")
                
                label_text = f" {' '.join(labels)}" if labels else ""
                points_text = f" <b>({question['calculated_points']} puncte)</b>"
                
                full_question = f"{i}. {question_text}{label_text}{points_text}"
                
                try:
                    story.append(Paragraph(full_question, question_style))
                except Exception as e:
                    # Fallback with safe encoding
                    safe_question = safe_encode(full_question)
                    story.append(Paragraph(safe_question, question_style))
                
                # Add multiple choice options with improved styling
                if question['type'] == 'multiple_choice' and question.get('options'):
                    try:
                        options_data = question['options']
                        if isinstance(options_data, str):
                            options = json.loads(options_data)
                            if self.config['test_settings'].get('shuffle_options', False):
                                random.shuffle(options)
                            
                            # Add spacing before options
                            story.append(Spacer(1, 4))  # Reduced from 8
                            
                            # Add each option with simple formatting
                            for j, option in enumerate(options):
                                option_text = safe_encode(str(option))
                                
                                # Escape HTML entities to prevent parsing issues
                                option_text = option_text.replace('&', '&amp;')
                                option_text = option_text.replace('<', '&lt;')
                                option_text = option_text.replace('>', '&gt;')
                                
                                # Convert markdown code to basic formatting
                                option_text = re.sub(r'`([^`]+)`', r'<font name="Courier">\1</font>', option_text)
                                
                                # Clean option layout without checkbox
                                option_line = f"{chr(ord('a') + j)}) {option_text}"
                                story.append(Paragraph(option_line, option_style))
                                story.append(Spacer(1, 2))  # Reduced from 4
                    except (json.JSONDecodeError, TypeError, ValueError):
                        pass
                
                # Add answer space for non-multiple choice questions
                elif question['type'] in ['short_answer', 'essay', 'code', 'free_text', 'free_text_answer']:
                    # Add specific instructions based on question type
                    if question['type'] == 'code':
                        instruction_text = "<b>Răspuns:</b> <i>Scrie codul pentru rezolvarea exercițiului</i>"
                    elif question['type'] in ['free_text', 'free_text_answer']:
                        instruction_text = "<b>Răspuns:</b> <i>Scrie în propriile cuvinte (sau cod) cum ai rezolva exercițiul</i>"
                    else:
                        instruction_text = "<b>Răspuns:</b>"
                    
                    story.append(Paragraph(instruction_text, question_style))
                    story.append(Spacer(1, 3))  # Reduced from 6
                    
                    # Create visual answer boxes based on question type
                    if question['type'] in ['free_text', 'free_text_answer']:
                        # Large square for free text answers (about 6cm x 6cm)
                        box_width = 15*cm
                        box_height = 6*cm
                        
                        # Create a table with a single bordered cell as the answer box
                        answer_box_data = [[""]]  # Empty cell for writing
                        answer_table = Table(answer_box_data, colWidths=[box_width], rowHeights=[box_height])
                        answer_table.setStyle(TableStyle([
                            ('BOX', (0, 0), (-1, -1), 1, colors.black),
                            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                            ('LEFTPADDING', (0, 0), (-1, -1), 6),
                            ('RIGHTPADDING', (0, 0), (-1, -1), 6),
                            ('TOPPADDING', (0, 0), (-1, -1), 6),
                            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
                        ]))
                        story.append(answer_table)
                        
                    elif question['type'] == 'short_answer':
                        # Larger rectangle for short answers (about 3cm height)
                        box_width = 15*cm
                        box_height = 1.5*cm
                        
                        # Create a table with a single bordered cell as the answer box
                        answer_box_data = [[""]]  # Empty cell for writing
                        answer_table = Table(answer_box_data, colWidths=[box_width], rowHeights=[box_height])
                        answer_table.setStyle(TableStyle([
                            ('BOX', (0, 0), (-1, -1), 1, colors.black),
                            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                            ('LEFTPADDING', (0, 0), (-1, -1), 6),
                            ('RIGHTPADDING', (0, 0), (-1, -1), 6),
                            ('TOPPADDING', (0, 0), (-1, -1), 6),
                            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
                        ]))
                        story.append(answer_table)
                        
                    else:  # code, essay, or other types
                        # Large size for code/essay (about 5cm height)
                        box_width = 15*cm
                        box_height = 5*cm
                        
                        # Create a table with a single bordered cell as the answer box
                        answer_box_data = [[""]]  # Empty cell for writing
                        answer_table = Table(answer_box_data, colWidths=[box_width], rowHeights=[box_height])
                        answer_table.setStyle(TableStyle([
                            ('BOX', (0, 0), (-1, -1), 1, colors.black),
                            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                            ('LEFTPADDING', (0, 0), (-1, -1), 6),
                            ('RIGHTPADDING', (0, 0), (-1, -1), 6),
                            ('TOPPADDING', (0, 0), (-1, -1), 6),
                            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
                        ]))
                        story.append(answer_table)
                
                story.append(Spacer(1, 6))  # Reduced space between questions
            
            # Add footer
            if self.config.get('footer', {}).get('include', False):
                footer_content = self.config['footer'].get('content', '')
                story.append(HRFlowable(width="100%"))
                story.append(Spacer(1, 12))
                
                footer_lines = footer_content.split('\n')
                for line in footer_lines:
                    if line.strip():
                        clean_line = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', line)
                        clean_line = re.sub(r'---', '', clean_line)
                        if clean_line.strip():
                            try:
                                story.append(Paragraph(clean_line.strip(), header_style))
                            except:
                                safe_line = safe_encode(clean_line.strip())
                                story.append(Paragraph(safe_line, header_style))
            
            # Build PDF
            doc.build(story)
            print(f"✅ PDF generated: {pdf_path}")
            return str(pdf_path)
            
        except Exception as e:
            print(f"Error generating PDF: {e}")
            return ""
    
    def save_test(self, content: str, filename: str = None) -> str:
        """Save the test content to a file."""
        if filename is None:
            filename = self.config['test_settings'].get('output_filename', 'test.md')
        
        # Create output directory if it doesn't exist
        output_dir = self.config['test_settings'].get('output_directory', 'out')
        output_path = Path(output_dir) / filename
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(content)
            
        return str(output_path)
    
    def generate_test(self) -> Dict[str, str]:
        """Generate the complete test and return file paths."""
        print("Generating test...")
        
        # Select questions
        questions = self.select_questions()
        print(f"Selected {len(questions)} questions")
        
        # Get output format
        output_format = self.config['test_settings'].get('output_format', 'markdown').lower()
        output_filename = self.config['test_settings'].get('output_filename', 'test.md')
        
        results = {}
        
        # Generate markdown content (always needed as base)
        test_content = self.generate_test_content(questions)
        
        # Check if variants are being generated to determine naming
        base_name = output_filename.replace('.md', '')
        generate_variants = self.config.get('advanced', {}).get('generate_variants', False)
        
        if generate_variants:
            # If generating variants, add suffix to the first variant too
            suffix_template = self.config['advanced'].get('variant_suffix', '_variant_{n}')
            variant_suffix = suffix_template.format(n=1)
            
            # Save markdown if requested
            if output_format in ['markdown', 'both', 'md']:
                variant_filename = f"{base_name}{variant_suffix}.md"
                test_path = self.save_test(test_content, variant_filename)
                results['variant_1_md'] = test_path
                
            # Generate PDF if requested
            if output_format in ['pdf', 'both'] and PDF_AVAILABLE:
                variant_pdf_filename = f"{base_name}{variant_suffix}.pdf"
                pdf_path = self.save_pdf(test_content, variant_pdf_filename, questions)
                if pdf_path:
                    results['variant_1_pdf'] = pdf_path
            elif output_format in ['pdf', 'both'] and not PDF_AVAILABLE:
                print("⚠️  Warning: PDF output requested but PDF libraries not available")
                print("   Falling back to markdown output only")
                if 'variant_1_md' not in results:
                    variant_filename = f"{base_name}{variant_suffix}.md"
                    test_path = self.save_test(test_content, variant_filename)
                    results['variant_1_md'] = test_path
            
            # Generate answer key if requested
            if self.config['test_settings'].get('include_answers', False):
                answer_content = self.generate_answer_key(questions)
                
                # Markdown answer key
                if output_format in ['markdown', 'both', 'md']:
                    variant_answer_filename = f"{base_name}{variant_suffix}_answers.md"
                    answer_path = self.save_test(answer_content, variant_answer_filename)
                    results['variant_1_answers_md'] = answer_path
                
                # PDF answer key
                if output_format in ['pdf', 'both'] and PDF_AVAILABLE:
                    variant_pdf_answer_filename = f"{base_name}{variant_suffix}_answers.pdf"
                    pdf_answer_path = self.save_pdf(answer_content, variant_pdf_answer_filename, questions)
                    if pdf_answer_path:
                        results['variant_1_answers_pdf'] = pdf_answer_path
        else:
            # Original naming when not generating variants
            # Save markdown if requested
            if output_format in ['markdown', 'both', 'md']:
                test_path = self.save_test(test_content, output_filename)
                results['test_md'] = test_path
                
            # Generate PDF if requested
            if output_format in ['pdf', 'both'] and PDF_AVAILABLE:
                pdf_filename = output_filename.replace('.md', '.pdf')
                pdf_path = self.save_pdf(test_content, pdf_filename, questions)
                if pdf_path:
                    results['test_pdf'] = pdf_path
            elif output_format in ['pdf', 'both'] and not PDF_AVAILABLE:
                print("⚠️  Warning: PDF output requested but PDF libraries not available")
                print("   Falling back to markdown output only")
                if 'test_md' not in results:
                    test_path = self.save_test(test_content, output_filename)
                    results['test_md'] = test_path
            
            # Generate answer key if requested
            if self.config['test_settings'].get('include_answers', False):
                answer_content = self.generate_answer_key(questions)
                
                # Markdown answer key
                if output_format in ['markdown', 'both', 'md']:
                    answer_filename = output_filename.replace('.md', '_answers.md')
                    answer_path = self.save_test(answer_content, answer_filename)
                    results['answers_md'] = answer_path
                
                # PDF answer key
                if output_format in ['pdf', 'both'] and PDF_AVAILABLE:
                    pdf_answer_filename = output_filename.replace('.md', '_answers.pdf')
                    pdf_answer_path = self.save_pdf(answer_content, pdf_answer_filename, questions)
                    if pdf_answer_path:
                        results['answers_pdf'] = pdf_answer_path
        
        # Generate variants if requested
        if self.config.get('advanced', {}).get('generate_variants', False):
            num_variants = self.config['advanced'].get('num_variants', 3)
            suffix_template = self.config['advanced'].get('variant_suffix', '_variant_{n}')
            
            for variant_num in range(2, num_variants + 1):
                # Re-select questions for each variant
                variant_questions = self.select_questions()
                variant_content = self.generate_test_content(variant_questions)
                
                # Generate variant filename
                base_name = output_filename.replace('.md', '')
                variant_suffix = suffix_template.format(n=variant_num)
                
                # Markdown variant
                if output_format in ['markdown', 'both', 'md']:
                    variant_filename = f"{base_name}{variant_suffix}.md"
                    variant_path = self.save_test(variant_content, variant_filename)
                    results[f'variant_{variant_num}_md'] = variant_path
                
                # PDF variant
                if output_format in ['pdf', 'both'] and PDF_AVAILABLE:
                    variant_pdf_filename = f"{base_name}{variant_suffix}.pdf"
                    variant_pdf_path = self.save_pdf(variant_content, variant_pdf_filename)
                    if variant_pdf_path:
                        results[f'variant_{variant_num}_pdf'] = variant_pdf_path
                
                # Generate answer key for variant if requested
                if self.config['test_settings'].get('include_answers', False):
                    variant_answer_content = self.generate_answer_key(variant_questions)
                    
                    # Markdown variant answers
                    if output_format in ['markdown', 'both', 'md']:
                        variant_answer_filename = f"{base_name}{variant_suffix}_answers.md"
                        variant_answer_path = self.save_test(variant_answer_content, variant_answer_filename)
                        results[f'variant_{variant_num}_answers_md'] = variant_answer_path
                    
                    # PDF variant answers
                    if output_format in ['pdf', 'both'] and PDF_AVAILABLE:
                        variant_pdf_answer_filename = f"{base_name}{variant_suffix}_answers.pdf"
                        variant_pdf_answer_path = self.save_pdf(variant_answer_content, variant_pdf_answer_filename)
                        if variant_pdf_answer_path:
                            results[f'variant_{variant_num}_answers_pdf'] = variant_pdf_answer_path
        
        return results

def main():
    """Main function to run the test generator."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Generate tests from question bank')
    parser.add_argument('--config', '-c', default='test_config.yaml',
                        help='Path to test configuration file')
    parser.add_argument('--output-dir', '-o', default='../tests',
                        help='Output directory for generated tests')
    
    args = parser.parse_args()
    
    # Change to output directory
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    os.chdir(output_dir)
    
    # Generate test
    generator = TestGenerator(args.config)
    
    try:
        results = generator.generate_test()
        
        print("\n✅ Test generation completed successfully!")
        print("\nGenerated files:")
        for file_type, file_path in results.items():
            print(f"  {file_type}: {file_path}")
            
    except Exception as e:
        print(f"\n❌ Error generating test: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()