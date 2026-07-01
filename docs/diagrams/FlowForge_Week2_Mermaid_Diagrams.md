# B2B AI Order Processing Agent — Mermaid Diagram Sources

These editable Mermaid definitions correspond to the visual diagrams included in the Week 2 design document.

## 1A. Automated Order Processing Pipeline

```mermaid
flowchart TB
  subgraph O[Outlook Inbox]
    A[New email received] --> B[Email Monitoring Service]
  end
  subgraph P[Backend Processing]
    B --> C[Store email, metadata and attachments]
    C --> D[Classify email]
    D --> E{Is it an order?}
    E -->|No| F[Archive / mark non-order]
    E -->|Yes| G[Detect client]
    G --> H[Load client prompt, rules and templates]
    H --> I[Process email body and multiple attachments]
  end
  subgraph AI[OCR / AI Extraction]
    I --> J{Scanned PDF or image?}
    J -->|Yes| K[OCR Service]
    J -->|No| L[Prepared content]
    K --> L
    L --> M[AI Extraction Engine]
    M --> N[Structured header and item fields + source + confidence]
  end
  subgraph V[Validation and Decision]
    N --> O1[Validation Engine]
    O1 --> P1[Decision Engine]
    P1 --> Q{Result}
    Q -->|All valid| R[OK]
    Q -->|Manual review| S[Human in the Loop]
    Q -->|Missing customer data| T[Waiting for Reply]
    Q -->|Technical error| U[Failed]
  end
  DB[(PostgreSQL)]
  C -.-> DB
  H -.-> DB
  N -.-> DB
  P1 -.-> DB
```

## 1B. Dashboard and Human Review Workflow

```mermaid
flowchart TB
  subgraph D[Operator Dashboard]
    A[Open order] --> B[View original email and attachments]
    B --> C[See source and confidence for each field]
    C --> D1[Correct header and item fields]
    D1 --> E{Operator action}
    E -->|Report issue| F[Feedback & Issues]
    E -->|Reject| G[Reject order]
  end
  subgraph R[Waiting for Reply]
    E -->|Missing information| H[Select template for missing field]
    H --> I[Prepare Mail To or sender recipient]
    I --> J[Operator reviews and clicks Send]
    J --> K[Waiting for Reply]
    K --> L[Customer reply received in same thread]
    L --> M[Match to existing order]
    M --> N[Process new content and validate same order]
    N --> A
  end
  subgraph X[XML / ERP]
    E -->|Approve| O[Generate Header XML]
    O --> P[Generate Items XML]
    P --> Q[ERP Ready]
    Q --> R1[Operator reviews XML status]
    R1 --> S{Corrections needed?}
    S -->|Yes| D1
    S -->|No| T[Operator clicks Send XMLs]
    T --> U[ERP System]
    U --> V[XMLs Sent]
  end
```

## 2. Compact Component Architecture

```mermaid
flowchart TB
  subgraph E[External Systems]
    OUTLOOK[Microsoft Outlook]
    AIAPI[OpenAI API]
    ERP[ERP System]
  end
  subgraph F[Frontend]
    UI[React + TypeScript Dashboard]
  end
  subgraph A[FastAPI Application]
    AUTH[Authentication]
    DASH[Dashboard and Order API]
    CLIENTS[Client Configuration]
    REPORTS[Reports and Data Export]
    FEEDBACK[Feedback and Issues]
  end
  subgraph P[Automated Processing]
    ORCH[Processing Orchestrator] --> EMAIL[Email Monitoring and Classification]
    EMAIL --> CLIENT[Client Detection]
    CLIENT --> DOCS[Document Processing and OCR]
    DOCS --> EXTRACT[AI Extraction]
    EXTRACT --> VALIDATE[Validation and Decision]
  end
  subgraph O[Order Management]
    ORDER[Order Review and Lifecycle]
    REPLY[Clarification Email]
    XML[Header + Items XML]
    SEND[Manual XML Transmission]
  end
  subgraph D[Data]
    DB[(PostgreSQL)]
    FILES[(Local File Storage)]
  end
  UI --> AUTH & DASH & CLIENTS & REPORTS & FEEDBACK
  OUTLOOK --> EMAIL
  EXTRACT --> AIAPI
  VALIDATE --> ORDER
  DASH --> ORDER
  ORDER --> REPLY --> OUTLOOK
  ORDER --> XML --> SEND --> ERP
  A --- DB
  P --- DB
  O --- DB
  EMAIL --- FILES
  DOCS --- FILES
  XML --- FILES
```

## 3. Core ER Diagram

```mermaid
erDiagram
  USERS ||--o{ ORDERS : approves
  USERS ||--o{ GENERATED_XMLS : manages
  USERS ||--o{ FEEDBACK_ISSUES : reports
  CLIENTS ||--o{ CLIENT_PROMPTS : has
  CLIENTS ||--o{ EMAIL_TEMPLATES : defines
  CLIENTS ||--o{ EMAILS : identified_from
  CLIENTS ||--o{ ORDERS : places
  EMAILS ||--o{ ATTACHMENTS : contains
  EMAILS ||--o| ORDERS : creates
  EMAILS ||--o{ PROCESSING_LOGS : records
  ORDERS ||--o{ ORDER_ITEMS : contains
  ORDERS ||--o{ EXTRACTED_FIELDS : stores
  ORDERS ||--o{ VALIDATION_ISSUES : produces
  ORDERS ||--o{ GENERATED_XMLS : generates
  ORDERS ||--o{ FEEDBACK_ISSUES : receives
  ORDERS ||--o{ PROCESSING_LOGS : tracks
  ORDER_ITEMS ||--o{ EXTRACTED_FIELDS : has
```

## 4. Sequence Diagram

```mermaid
sequenceDiagram
  autonumber
  actor Customer
  participant Outlook
  participant Backend as Processing Orchestrator
  participant Extractor as Document/OCR/AI
  participant Validator as Validation/Decision
  actor Operator
  participant Dashboard
  participant XML
  participant ERP
  Customer->>Outlook: Send order email and attachments
  Outlook->>Backend: New email
  Backend->>Backend: Store, classify and detect client
  Backend->>Extractor: Process content and extract fields
  Extractor-->>Backend: Structured data + sources + confidence
  Backend->>Validator: Validate order
  Validator-->>Backend: State and issues
  Backend->>Dashboard: Display order
  alt Waiting for Reply
    Operator->>Dashboard: Review and send clarification
    Dashboard->>Outlook: Send employee-approved email
    Customer->>Outlook: Reply in same thread
    Outlook->>Backend: Match reply to existing order
    Backend->>Extractor: Update extraction
    Backend->>Validator: Validate same order again
    Validator-->>Dashboard: Update order
  end
  Operator->>Dashboard: Approve order
  Dashboard->>XML: Generate Header and Items XML
  XML-->>Dashboard: ERP Ready
  Operator->>Dashboard: Click Send XMLs
  Dashboard->>XML: Authorize transmission
  XML->>ERP: Send both XMLs
  ERP-->>Dashboard: Transmission result
```

## 5. Dashboard Navigation

```mermaid
flowchart TB
  LOGIN[Login] --> OVERVIEW[Overview]
  OVERVIEW --> ORDERS[Orders]
  OVERVIEW --> CLIENTS[Clients]
  OVERVIEW --> EXPORT[Data Export]
  OVERVIEW --> FEEDBACK[Feedback & Issues]
  OVERVIEW --> USERS[Users]
  OVERVIEW --> SETTINGS[Settings]
  ORDERS --> FILTERS[Search, filters and status tabs]
  FILTERS --> DETAIL[Order Details]
  DETAIL --> REVIEW[Email, attachments, source, confidence and validation]
  REVIEW --> ACTION{Operator action}
  ACTION -->|Edit| DETAIL
  ACTION -->|Approve| XML[Generate two XML files]
  XML --> READY[ERP Ready] --> SEND[Click Send XMLs] --> SENT[XMLs Sent]
  ACTION -->|Missing information| REPLY[Review and send clarification]
  REPLY --> DETAIL
  ACTION -->|Reject / issue| ISSUE[Reject or report issue]
  CLIENTS --> CONFIG[Prompt, rules and templates]
  EXPORT --> EXCEL[Generate Excel report]
```
