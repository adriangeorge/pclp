# PCLP Test Generator

A comprehensive Python-based test generation system that creates professional academic tests from a structured question bank with support for multiple variants, PDF output, and Romanian language content.

## 🌟 Features

- **Professional PDF Output**: A4 format with proper typography and formatting
- **Romanian Character Support**: Full Unicode support with proper encoding
- **Multiple Test Variants**: Generate different versions with variant numbering
- **Math Formula Rendering**: LaTeX to Unicode conversion for mathematical content
- **Visual Answer Boxes**: Automatically sized answer spaces based on question type
- **Difficulty-Based Sorting**: Questions ordered from easiest to hardest
- **Logo Integration**: Support for institution branding
- **Answer Keys**: Automatic generation of answer sheets
- **Duplicate Management**: Intelligent handling of questions with same content but different types

## 📁 File Structure

```
scripts/
├── generate_test.py          # Main test generation engine
├── run_test_generator.py     # Simple runner script
├── test_config.yaml          # Configuration file
├── rehash_questions.py       # Question hash management utility
├── encrypt_questions.py      # Question bank encryption utility
├── decrypt_questions.py      # Question bank decryption utility
├── test_crypto.py            # Encryption/decryption test script
├── out/                      # Generated test files
│   ├── test_laborator_variant_1.pdf
│   ├── test_laborator_variant_1_answers.pdf
│   ├── test_laborator_variant_2.pdf
│   └── ... (additional variants)
└── README.md                 # This documentation

../questions/                 # Question database
├── cat_Basic_Math.csv
├── cat_String_Manipulation.csv
├── cat_Logic_and_Control_Flow.csv
├── cat_Data_Types_and_Variables.csv
├── cat_Math_Module.csv
├── cat_Python_Basics.csv
├── cat_Bitwise_Operations.csv
├── cat_General.csv
└── mappings.yaml             # Category and difficulty mappings
```

## 🚀 Quick Start

### Prerequisites

**Basic functionality:**
```bash
pip install pandas pyyaml reportlab markdown2
```

**For question bank encryption (optional):**
```bash
pip install cryptography
```

### Basic Usage

```bash
# Generate tests with default configuration
cd scripts
python run_test_generator.py

# Use custom configuration file
python run_test_generator.py custom_config.yaml
```

## ⚙️ Configuration

The system is configured through `test_config.yaml`. Here's the current structure:

### Test Settings

```yaml
test_settings:
  title: "Test de laborator PCLP"
  subtitle: ""
  time_limit_minutes: 90
  total_points: 100
  bonus_points: 20
  
  # Output options
  output_format: "both"  # markdown, pdf, both
  output_filename: "test_laborator.md"
  output_directory: "out"
  include_answers: true
  shuffle_questions: false  # Keep difficulty-based sorting
  shuffle_options: true     # Randomize multiple choice options
```

### Question Selection

```yaml
question_selection:
  categories:
    - basic_math
    - "*"  # Include all categories
  
  # Question type preferences (to handle duplicates)
  preferred_question_types:
    - multiple_choice
    - short_answer
    - free_text
    - code
    - essay
  
  # Direct difficulty distribution (simplified approach)
  difficulty_config:
    difficulty_distribution:
      Trivial: 5        # Number of questions
      Easy: 7
      Medium: 8
      Hard: 2
      Very Hard: 2
    
    points_per_question: 5  # All questions worth same points
```

### Advanced Features

```yaml
advanced:
  random_seed: 1                    # For reproducible tests
  allow_duplicates: false
  min_category_spacing: 2           # Spread similar questions apart
  
  # Multiple test variants
  generate_variants: true
  num_variants: 3
  variant_suffix: "_variant_{n}"    # Results in _variant_1, _variant_2, etc.
  
  paper_size: "A4"
  generate_openbook_cheat_sheets: true
```

## 📝 Question Types Supported

1. **multiple_choice** - Questions with a/b/c/d options
2. **short_answer** - Brief open-ended responses (2cm answer box)
3. **free_text** - Longer text responses (4cm answer box)
4. **code** - Programming questions (3cm answer box)
5. **essay** - Extended responses (3cm answer box)

## 🎯 Current Output

When you run the generator, you get:

### Generated Files (with variants enabled)
- `test_laborator_variant_1.pdf` / `.md`
- `test_laborator_variant_1_answers.pdf` / `.md`
- `test_laborator_variant_2.pdf` / `.md`
- `test_laborator_variant_2_answers.pdf` / `.md`
- `test_laborator_variant_3.pdf` / `.md`
- `test_laborator_variant_3_answers.pdf` / `.md`

### Sample Output Statistics
```
📊 Test Statistics:
   Total questions: 24
   Total points: 120
   Difficulty breakdown:
     Trivial: 5 questions, 25 points
     Easy: 7 questions, 35 points
     Medium: 8 questions, 40 points
     Hard: 2 questions, 10 points
     Very Hard: 2 questions, 10 points
```

## 🔧 Key Features Explained

### PDF Generation
- **A4 Format**: Professional layout with 2cm margins
- **Typography**: Times New Roman for readability
- **Romanian Characters**: Full Unicode support (ă, â, î, ș, ț)
- **Math Formulas**: LaTeX symbols converted to Unicode
- **Visual Answer Boxes**: Bordered tables with appropriate sizing
- **Logo Support**: Institution branding integration

### Variant System
- Each variant has different question selection
- Consistent naming with `_variant_N` suffix
- Maintains same difficulty distribution across variants
- Each variant includes both test and answer key

### Duplicate Handling
- Questions with same content but different types are deduplicated
- Priority given to `preferred_question_types` order
- Ensures exact point totals match configuration

### Question Database
- 129 total questions across 8 categories
- Questions stored in CSV format with hash-based identification
- Categories: Basic Math, String Manipulation, Logic & Control Flow, Data Types, Math Module, Python Basics, Bitwise Operations, General

## 🛠️ Utilities

### Question Hash Management

```bash
# Regenerate consistent hashes for all questions
python rehash_questions.py
```

This utility ensures all questions have consistent MD5-based identifiers.

### Python Cheatsheet Generator

Generate a comprehensive Python reference that fits on a single A4 page:

```bash
# Generate cheatsheet from all files in cheatsheets/ folder
python scripts/generate_cheatsheet.py
```

**Features:**
- Combines all cheatsheet markdown files into one PDF
- Optimized layout for single A4 page
- Includes: operators, built-in functions, type casting, string methods, math module
- Compact tables with proper formatting
- Professional layout with clear sections

**Output:** `Python_Cheatsheet.pdf` in the root directory

### Question Bank Security

#### Encryption

```bash
# Encrypt question bank with password
python encrypt_questions.py

# Encrypt in-place (replaces original files)
python encrypt_questions.py --in-place

# Encrypt with specific password (not recommended for production)
python encrypt_questions.py --password "your_password"

# Encrypt to specific directory
python encrypt_questions.py --output-dir "secure_backup"

# Include mappings.yaml file
python encrypt_questions.py --include-mappings
```

#### Decryption

```bash
# Decrypt encrypted question bank
python decrypt_questions.py

# Decrypt in-place (replaces encrypted files with originals)
python decrypt_questions.py --in-place

# Decrypt to specific directory
python decrypt_questions.py --output-dir "../questions_restored"

# Overwrite existing files
python decrypt_questions.py --overwrite
```

#### Security Features

- **AES Encryption**: Uses Fernet (AES 128) for strong encryption
- **Password-Based Key Derivation**: PBKDF2 with 100,000 iterations
- **Unique Salt Per File**: Each file gets a random 16-byte salt
- **Tamper Detection**: Incorrect passwords are detected automatically

#### Testing Encryption

```bash
# Test the encryption/decryption workflow
python test_crypto.py --test

# Show usage examples
python test_crypto.py
```

**Prerequisites for encryption:**

```bash
pip install cryptography
```

## 📋 Example Configuration

For a typical exam setup:

```yaml
test_settings:
  title: "Examen PCLP - Programarea Calculatoarelor și Limbaje de Programare"
  time_limit_minutes: 120
  output_format: "both"
  
question_selection:
  categories: ["*"]  # All categories
  difficulty_config:
    difficulty_distribution:
      Trivial: 8
      Easy: 10
      Medium: 6
      Hard: 3
      Very Hard: 1
    points_per_question: 5

advanced:
  generate_variants: true
  num_variants: 5
  random_seed: null  # Different questions each run
```

## 🚨 Troubleshooting

### Common Issues

**"Selected 24 questions" instead of 26**
- This was caused by duplicate questions being removed
- Fixed by implementing preferred question type handling

**Romanian characters not displaying**
- Ensure your system supports UTF-8 encoding
- PDF generation includes proper Unicode font mapping

**PDF generation fails**
- Install required dependencies: `pip install reportlab markdown2`
- Check that you have write permissions to output directory

**Missing questions for difficulty level**
- Verify question database has questions at requested difficulty
- Check that difficulty names match exactly (case sensitive)

### Dependencies

**Required:**
```bash
pip install pandas pyyaml
```

**For PDF output:**
```bash
pip install reportlab markdown2
```

## 🔄 Recent Updates

- ✅ Fixed points calculation discrepancy
- ✅ Added variant suffix to first variant for consistency
- ✅ Implemented duplicate question handling
- ✅ Enhanced PDF formatting with visual answer boxes
- ✅ Added Romanian character support
- ✅ Simplified configuration structure

## 📚 Question Bank Structure

Questions are stored in CSV files with columns:
- `category` - Question category
- `hash` - Unique identifier (MD5-based)
- `type` - Question type (multiple_choice, short_answer, etc.)
- `difficulty` - Difficulty level (trivial, easy, medium, hard, very_hard)
- `question` - Question text (supports Markdown and LaTeX)
- `options` - JSON array for multiple choice (optional)
- `correct_answer` - Correct answer (optional, for answer keys)

## 🎓 Academic Integration

This system is designed for academic environments and supports:
- Institution branding and headers
- Professional formatting standards
- Multiple test sessions with variants
- Comprehensive answer key generation
- Romanian language academic content
- Mathematical notation in Computer Science contexts