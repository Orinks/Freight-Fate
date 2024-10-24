# NVGT Development Rules

## Include Usage
- Always use menu.nvgt for menu interfaces and menu handling
- Include speech.nvgt for text-to-speech functionality
- Use form.nvgt for auditory user interface components
- Use bgt_compat.nvgt only when absolutely necessary for BGT compatibility

## Sound Management
- Use sound_pool for managing multiple sound instances
- Set sound_default_pack when using pack files
- Always check sound.loaded property before playing
- Use mixer class for complex sound mixing operations

## Threading & Concurrency 
- Prefer async<T> over raw threads when possible
- Always yield() in coroutines
- Avoid sharing state between threads
- Use proper synchronization primitives when thread sharing is necessary

## File Operations
- Use datastream for file I/O operations
- Check file existence before operations
- Use proper UTF-8 handling for filenames
- Properly close files/streams after use

## Memory Management
- Use handles (@) for object references
- Be careful with global variables
- Clean up resources in proper order
- Use reference counting appropriately

## Error Handling
- Check return values of critical operations
- Use try/catch blocks for exception handling
- Provide meaningful error messages
- Log errors appropriately

## Best Practices
- Follow consistent naming conventions
- Document code with clear comments
- Use const when appropriate
- Break complex operations into smaller functions
- Test thoroughly before deployment

## Game Loop Structure
- Implement proper game loop with timing
- Handle input events appropriately
- Update game state consistently
- Render/output at appropriate intervals

## User Interface
- Use screen reader functions appropriately
- Provide clear audio feedback
- Support keyboard navigation
- Make interfaces intuitive for non-visual use

## Performance
- Profile code for bottlenecks
- Optimize resource usage
- Cache frequently used values
- Use appropriate data structures

## Security
- Validate all user input
- Sanitize file paths
- Use secure random number generation
- Protect sensitive data appropriately
