# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Development Commands

### Setup
```bash
# Clone repository and set up environment
git clone <repository-url>
cd "ai project"
python -m venv .venv
# Windows:
.venv\Scripts\activate
# Unix/Linux/macOS:
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Edit .env to add your API keys
```

### Running the Application
```bash
# Start the Streamlit dashboard
streamlit run app.py

# Run with specific configuration via sidebar:
# - Enter GitHub repository URL
# - Select LLM provider (openai/anthropic)
# - Adjust max files/chunks to scan
# - Optional: Enter GitHub token for PR posting
```

### Testing
```bash
# Run unit tests (currently only parser tests)
pytest tests/

# Run with verbose output
pytest -v
```

### Code Quality
```bash
# No formal linting setup currently, but you can use:
pip install flake8 black
flake8 src/
black src/
```

## Code Architecture

### High-Level Structure
The application follows a layered monolithic architecture with clear separation of concerns:

```
ai project/
├── app.py                 # Streamlit dashboard (presentation layer)
├── requirements.txt       # Python dependencies
├── src/
│   ├── ingestion/         # Repository cloning (GitPython)
│   │   └── clone_repo.py
│   ├── parsing/           # AST parsing and code chunking
│   │   └── ast_parser.py  # Python AST + tree-sitter for JS/TS
│   ├── review/            # LLM interaction and prompt engineering
│   │   ├── llm_client.py  # OpenAI/Abstraction layer
│   │   └── prompts.py     # Review prompt templates
│   ├── pipeline/          # Orchestration layer
│   │   └── orchestrator.py # Coordinates clone→parse→review
│   ├── models/            # Data contracts and validation
│   │   └── schemas.py     # Pydantic models: CodeChunk, ReviewComment, etc.
│   └── output/            # Export formats and GitHub integration
│       ├── markdown.py    # Markdown report generation
│       └── github_pr.py   # GitHub PR comment posting
└── tests/                 # Unit tests
    └── test_parser.py     # AST parsing tests
```

### Data Flow
1. **User Input**: GitHub URL entered in Streamlit UI (`app.py`)
2. **Orchestration**: `ReviewPipeline` coordinates the workflow (`src/pipeline/orchestrator.py`)
3. **Ingestion**: Shallow clone repository into temp directory (`src/ingestion/clone_repo.py`)
4. **Parsing**: Extract code chunks using AST/tree-sitter (`src/parsing/ast_parser.py`)
5. **Review**: Send chunks to LLM for structured feedback (`src/review/llm_client.py` + `src/review/prompts.py`)
6. **Validation**: Parse and validate LLM responses into `ReviewComment` objects
7. **Output**: Display results in UI, export as Markdown/JSON, or post to GitHub PR

### Key Components
- **Presentation Layer** (`app.py`): Streamlit UI, session state, user controls
- **Application Orchestration** (`src/pipeline/orchestrator.py`: Manages workflow, error handling, progress reporting
- **Domain Models** (`src/models/schemas.py`): Pydantic schemas ensuring type safety and validation
- **Configuration**: Environment variables via `.env` file:
  - `LLM_PROVIDER`: `openai` or `anthropic`
  - API keys for selected provider
  - `GITHUB_TOKEN`: Optional, for PR posting

### Extensibility Points
As outlined in ARCHITECTURE.md, future enhancements could include:
- Background job queue for asynchronous processing
- Persistent storage for review history
- Advanced caching by commit SHA
- Private repository support
- Multi-language tree-sitter grammars

### Dependencies
Core dependencies listed in `requirements.txt`:
- Streamlit: Web dashboard framework
- GitPython: Git repository cloning
- OpenAI/Anthropic SDKs: LLM provider interfaces
- Pydantic: Data validation and settings management
- python-dotenv: Environment variable loading
- PyGithub: GitHub API integration for PR posting
- tree-sitter: Incremental parsing for JS/TS
- pytest: Testing framework

### Development Notes
- All layers communicate via well-defined domain objects (`CodeChunk`, `ReviewComment`, `ReviewBatch`)
- Streamlit should contain only presentation logic; business logic resides in `src/`
- Error handling is designed to be resilient: chunk-level failures don't stop the entire pipeline
- Confidence scoring (0-100%) helps users identify which findings need verification
- Demo mode allows UI exploration without API keys using mock data