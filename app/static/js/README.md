# JavaScript Architecture for CineTagIt

## Overview

The JavaScript codebase for CineTagIt follows a modular, namespace-based architecture that provides a clean, 
organized structure for all frontend functionality. This architecture makes the code more maintainable, reusable, 
and easier to understand.

## Namespace Structure

All JavaScript functionality is organized under the global `window.CineTagIt` namespace with the following structure:

- `CineTagIt.Utils`: Utility functions for common tasks
  - CSRF token handling
  - Email deobfuscation
  - Other helper functions

- `CineTagIt.UI`: UI-related functionality
  - Message display system
  - Mobile menu handling
  - Touch-friendly hover effects
  - Other UI components

- `CineTagIt.Events`: Event handlers and initialization
  - Confirmation buttons
  - POST request buttons
  - Email deobfuscation
  - Clipboard functionality

## Key Files

- **base.js**: Core functionality and namespace definition
  - Defines the CineTagIt namespace and its structure
  - Contains utility functions, UI components, and event handlers
  - Handles initialization of the application

- **calendar.js**: Calendar-specific functionality
  - Implements the event calendar using FullCalendar library
  - Configures calendar display options

- **movies.js**: Movie listing and interaction functionality
  - Fetches and renders movie data
  - Handles movie decision interactions (approve/maybe/disapprove)
  - Manages movie filtering and display

## Usage Examples

### Getting CSRF Token

```javascript
// Get the CSRF token
const csrfToken = CineTagIt.Utils.getCsrfToken();
```

### Displaying Messages

```javascript
// Display a success message
CineTagIt.UI.displayMessage('Operation completed successfully', 'success');

// Display an error message
CineTagIt.UI.displayMessage('An error occurred', 'danger');
```

## Best Practices

When adding new JavaScript functionality:

1. Place utility functions in `CineTagIt.Utils`
2. Place UI-related functionality in `CineTagIt.UI`
3. Place event handlers in `CineTagIt.Events`
4. Initialize your functionality in the DOMContentLoaded event or add it to `CineTagIt.init()`
5. Use JSDoc comments to document your functions
6. Use optional chaining (`?.`) when accessing the CineTagIt namespace to ensure graceful degradation
