# Passport Specification

A passport is the machine-readable description of a contour's interface. It is the foundation of the melting contract system.

## Registration format

Sent by a contour to `POST /register`:

```json
{
  "name": "string (required, unique)",
  "address": "string (required, base URL e.g. http://host:port)",
  "description": "string (required, non-empty, human-readable purpose)",
  "endpoints": [
    {
      "path": "string (required, URL path e.g. /action)",
      "method": "string (required, HTTP method e.g. POST)",
      "description": "string (required, non-empty, what this endpoint does)",
      "accepts": "object or null (JSON-schema-style request body description)",
      "returns": "object or null (JSON-schema-style response body description)"
    }
  ]
}
```

### Validation rules

- `name` must be non-empty
- `address` must be a valid URL
- `description` must be non-empty (whitespace-only is rejected)
- `endpoints` must contain at least one entry
- Every endpoint must have a non-empty `description`
- Duplicate names update the existing registration in place

### Address field

The `address` is used internally by MCGK for routing. It is **never exposed** to other contours through discovery, system map, or any other response.

## Discovery format

Returned by `GET /discover/{name}`:

```json
{
  "name": "string",
  "description": "string",
  "endpoints": [
    {
      "path": "/action",
      "method": "POST",
      "description": "What this endpoint does",
      "accepts": {"type": "object", "properties": {"input": {"type": "string"}}},
      "returns": {"type": "object", "properties": {"result": {"type": "string"}}}
    }
  ],
  "status": "available | unreachable"
}
```

Note: no `address` field. The caller uses `POST /route/{name}/{path}` to reach the contour.

## Schema conventions

The `accepts` and `returns` fields use JSON Schema-like notation by convention:

```json
{
  "type": "object",
  "properties": {
    "text": {"type": "string"},
    "count": {"type": "integer"}
  },
  "required": ["text"]
}
```

MCGK does not validate request/response bodies against these schemas. They exist for the caller to understand the interface and adapt (melt) accordingly. Use whatever level of detail is helpful — from a simple `{"type": "object"}` to a full JSON Schema.

For non-JSON endpoints:

```json
{
  "accepts": {"type": "multipart/form-data", "fields": {"file": "binary"}},
  "returns": {"type": "binary", "description": "Raw file bytes"}
}
```

## Lifecycle

1. Contour registers → passport stored in SQLite
2. Contour goes down → passport remains available, status becomes `unreachable`
3. Discovery on a dead contour → returns full passport + `"status": "unreachable"`
4. Contour comes back → health check detects recovery, status returns to `available`
5. Contour re-registers → passport updated in place, no restart needed
