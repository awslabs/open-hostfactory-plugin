# 🌐 API Layer - REST Interface (Future Implementation)

## 📋 OVERVIEW
This API layer contains REST handlers for future HTTP/REST API implementation. Currently, the system uses the CLI interface layer (`src/interface/`) for all user interactions.

## 🎯 PURPOSE
- **Current Status:** NOT ACTIVELY USED
- **Future Purpose:** HTTP REST API endpoints
- **Architecture Role:** Presentation Layer (REST interface)

## 📁 STRUCTURE

### **REST Handlers (Future Use):**
- `GetAvailableTemplatesRESTHandler` - GET /templates endpoint
- `RequestMachinesRESTHandler` - POST /requests endpoint  
- `GetRequestStatusRESTHandler` - GET /requests/{id}/status endpoint
- `GetReturnRequestsRESTHandler` - GET /return-requests endpoint
- `RequestReturnMachinesRESTHandler` - POST /return-requests endpoint

### **Base Infrastructure:**
- `BaseAPIHandler` - Base class for all REST handlers
- `APIHandlerFactory` - Factory for creating REST handlers

## 🏗️ ARCHITECTURE ALIGNMENT

### **Clean Architecture Layers:**
```
┌─────────────────────────────────────┐
│ PRESENTATION LAYER                  │
├─────────────────────────────────────┤
│ CLI Interface    │ REST API (Future)│
│ (Active)         │ (Planned)        │
├─────────────────────────────────────┤
│ APPLICATION LAYER                   │
│ (Shared by both interfaces)         │
├─────────────────────────────────────┤
│ DOMAIN LAYER                        │
│ (Core business logic)               │
├─────────────────────────────────────┤
│ INFRASTRUCTURE LAYER                │
│ (Data access, external services)    │
└─────────────────────────────────────┘
```

### **Handler Naming Convention:**
- **CLI Handlers:** `*CLIHandler` (Interface layer)
- **REST Handlers:** `*RESTHandler` (API layer) 
- **Query Handlers:** `*QueryHandler` (Application layer)
- **Command Handlers:** `*CommandHandler` (Application layer)

## 🚀 FUTURE IMPLEMENTATION PLAN

### **Phase 1: Basic REST Endpoints**
- Implement HTTP server (Flask/FastAPI)
- Add request/response serialization
- Implement authentication/authorization
- Add OpenAPI/Swagger documentation

### **Phase 2: Advanced Features**
- Rate limiting and throttling
- Request validation and sanitization
- Error handling and status codes
- Monitoring and metrics collection

### **Phase 3: Production Readiness**
- Load balancing support
- Caching strategies
- Security hardening
- Performance optimization

## 🔧 CURRENT USAGE

### **How to Use (When Implemented):**
```python
# Example future usage:
from src.api.handlers.get_available_templates_handler import GetAvailableTemplatesRESTHandler

# Create handler
handler = GetAvailableTemplatesRESTHandler(application_service)

# Handle HTTP request
response = handler.handle(http_request)
```

### **Current Alternative (CLI):**
```python
# Current CLI usage:
from src.interface.command_handlers import GetAvailableTemplatesCLIHandler

handler = GetAvailableTemplatesCLIHandler(application_service)
result = handler.handle(cli_command)
```

## IMPORTANT NOTES

1. **Not Currently Used:** These handlers are not called by any active code paths
2. **Future Implementation:** Designed for upcoming REST API feature
3. **Shared Logic:** Business logic is handled by Application layer (shared with CLI)
4. **Testing:** Handlers are tested but not integrated into main application flow

## 📚 RELATED DOCUMENTATION
- [Interface Layer (CLI)](../interface/README.md) - Current active interface
- [Application Layer](../application/README.md) - Shared business logic
- [Architecture Overview](../../docs/architecture.md) - System architecture

---

*Status: FUTURE IMPLEMENTATION*  
*Last Updated: 2025-07-01*  
*Phase 1 Step 3: API Layer Documentation Complete*
