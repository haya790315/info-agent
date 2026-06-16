# Build Your Own PDF Search Engine with Django

## Project Goal

Build a simple PDF Knowledge Base system that allows users to:

1. Upload PDF files
2. Extract text from PDFs
3. Split text into chunks
4. Generate embeddings for each chunk
5. Store embeddings in PostgreSQL using pgvector
6. Search documents semantically

The purpose of this project is to understand the Retrieval part of RAG without involving any LLMs yet.

---

# Scope

## Included

- PDF Upload
- PDF Text Extraction
- Chunking
- Embedding Generation
- Vector Storage
- Semantic Search
- Search Result Display

## Not Included (for now)

- OpenAI
- Ollama
- LLM
- Chat Interface
- Agent
- Function Calling
- MCP
- Multi-user Support
- Authentication
- Permissions
- GitHub Integration
- Code Review Features

---

# System Architecture

```text
PDF Upload
    ↓
Extract Text
    ↓
Chunking
    ↓
Embedding
    ↓
PostgreSQL + pgvector
    ↓
Semantic Search
    ↓
Relevant Chunks
```

---

# Tech Stack

## Backend

- Django

## Frontend

- HTMX

## Database

- PostgreSQL
- pgvector

## PDF Processing

- PyMuPDF

## Embedding Model

- sentence-transformers
- all-MiniLM-L6-v2

---

# Why No LLM Yet?

The goal is to focus on learning:

- Chunking
- Embedding
- Vector Search
- Retrieval

These are the core building blocks of any RAG system.

Before introducing an LLM, we should first understand how information is retrieved.

---

# Data Flow

## Step 1: Upload PDF

User uploads a PDF.

```text
example.pdf
```

Store file metadata.

---

## Step 2: Extract Text

Use PyMuPDF to extract text.

```text
PDF
↓
Raw Text
```

---

## Step 3: Chunking

Split large text into smaller chunks.

Example:

```text
Chunk 1
Chunk 2
Chunk 3
...
```

Initial implementation:

```python
chunk_size = 1000
```

Simple fixed-size chunking is sufficient for version 1.

---

## Step 4: Generate Embeddings

Convert each chunk into a vector.

```text
Chunk
↓
Embedding
↓
Vector
```

Example model:

```python
all-MiniLM-L6-v2
```

---

## Step 5: Store in Database

Store:

- Chunk Content
- Embedding Vector

---

## Step 6: Semantic Search

User enters a question:

```text
What is Django ORM?
```

Workflow:

```text
Question
↓
Embedding
↓
Vector Search
↓
Top 5 Relevant Chunks
```

Display the most relevant chunks.

---

# Django Models

## Document

```python
class Document(models.Model):
    filename = models.CharField(max_length=255)
    uploaded_at = models.DateTimeField(auto_now_add=True)
```

---

## Chunk

```python
class Chunk(models.Model):
    document = models.ForeignKey(
        Document,
        on_delete=models.CASCADE,
        related_name="chunks"
    )

    content = models.TextField()

    embedding = VectorField()
```

---

# Pages

## 1. Upload Page

Purpose:

- Upload PDF

Features:

- File Upload Form

---

## 2. Document Detail Page

Purpose:

- View document information

Features:

- File Name
- Upload Time
- Number of Chunks
- Processing Status

---

## 3. Search Page

Purpose:

- Search knowledge base

Features:

- Search Input
- Search Button
- Search Results

---

# Search Workflow

```text
User Question
      ↓
Create Question Embedding
      ↓
pgvector Similarity Search
      ↓
Retrieve Top Chunks
      ↓
Display Results
```

---

# Learning Objectives

By completing this project, understand:

## PDF Processing

- Text Extraction
- Document Parsing

## Chunking

- Why chunking exists
- Chunk Size Considerations

## Embeddings

- What embeddings are
- Why embeddings are useful

## Vector Search

- Semantic Search
- Similarity Matching
- Cosine Distance

## PostgreSQL Vector Storage

- pgvector
- Vector Indexing

---

# Future Expansion

## Phase 2

Add LLM Integration

```text
Search
↓
Retrieved Chunks
↓
LLM
↓
Answer
```

---

## Phase 3

Multiple Document Knowledge Base

```text
Many PDFs
↓
Unified Search
↓
Knowledge Base
```

---

## Phase 4

Repository Search

Replace:

```text
PDF Files
```

with:

```text
Source Code Files
```

---

## Phase 5

AI Code Review Platform

```text
Repository
↓
Chunking
↓
Embeddings
↓
Knowledge Retrieval
↓
Code Review
```

---

# Blog Series

## Part 1

Why I Built My Own PDF Search Engine

Topics:

- Learning RAG Fundamentals
- Why Avoid Paid APIs Initially

---

## Part 2

How PDFs Become Searchable Data

Topics:

```text
PDF
↓
Text
↓
Chunks
```

---

## Part 3

What Is an Embedding?

Topics:

- Semantic Meaning
- Vector Representation
- Similarity Search

---

## Part 4

Building Vector Search with PostgreSQL and pgvector

Topics:

- Vector Storage
- Similarity Search
- Cosine Distance

---

## Part 5

Building a Local PDF Knowledge Base with Django

Topics:

```text
Upload
↓
Extract
↓
Chunk
↓
Embed
↓
Store
↓
Search
```

Complete walkthrough of the project.

---

# Final Goal

This project is not a chatbot.

This project is not an AI assistant.

This project is a Retrieval System.

The objective is to fully understand:

```text
Document
↓
Chunk
↓
Embedding
↓
Vector Search
↓
Knowledge Retrieval
```

Once this foundation is solid, adding an LLM later becomes straightforward.
