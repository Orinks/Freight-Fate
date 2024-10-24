# NVGT Coding Guidelines for LLMs

## Core Requirements
1. Every script must have a `void main()` function as the entry point unless it's an include script
2. Always use proper error handling with try/catch blocks
3. Follow consistent indentation style
4. Use descriptive variable and function names

## Required Includes
- For menus: Always use `#include "menu.nvgt"`
- For forms: Use `#include "form.nvgt"` 
- For speech: Use `#include "speech.nvgt"`
- For number speaking: Use `#include "number_speaker.nvgt"`

## Memory Management
1. Use reference counting (@) for object handles
2. Clean up resources properly
3. Avoid circular references
4. Use handles (@) for object references

## Sound Guidelines
1. Use sound class for audio
2. Set properties before playing
3. Clean up sound objects
4. Consider sound pools for multiple sounds
5. Use `sound_default_pack` for pack files

## Menu Implementation Rules
1. ALWAYS use menu.nvgt include
2. Implement keyboard navigation
3. Add descriptive items
4. Include sound feedback
5. Handle selection/cancellation

## Error Handling Requirements
1. Use try/catch blocks
2. Provide user feedback
3. Log errors appropriately
4. Handle unexpected conditions

## File Operations
1. Check for errors on open/read
2. Close files when done
3. Use pack files for resources
4. Handle paths cross-platform

## Text-to-Speech Rules
1. Use speech.nvgt include
2. Allow interruption where needed
3. Set speech parameters
4. Consider screen readers

## Threading Guidelines
1. Prefer async<T> for concurrency
2. Be careful with shared state
3. Use proper synchronization
4. Consider using coroutines

## UI Requirements
1. Clear audio feedback
2. Full keyboard navigation
3. Screen reader friendly
4. Consistent sound schemes

## Best Practices
1. Single-purpose functions
2. Meaningful names
3. Comment complex logic
4. Handle errors
5. Clean up resources
6. Consider cross-platform
7. Use appropriate includes

## Anti-Patterns to Avoid
1. Excessive global variables
2. Deep nesting
3. Ignored errors
4. Uncleaned resources
5. Tight coupling

## Testing Requirements
1. Test screen readers
2. Verify sounds
3. Test error cases
4. Verify cleanup
5. Test keyboard nav

## Documentation Rules
1. Comment complex logic
2. Document parameters
3. Explain non-obvious behavior
4. List dependencies

## Performance Guidelines
1. Use appropriate data structures
2. Clean up unused resources
3. Monitor memory usage
4. Profile when needed

## Security Requirements
1. Validate all input
2. Safe file operations
3. Access control for network
4. Use encryption appropriately

## Compilation Guidelines
1. Test debug/release builds
2. Handle errors
3. Cross-platform compatible
4. Use pragmas as needed

This document should be used alongside the full NVGT documentation.
