# Code Review Checklist

## Security
- [ ] No hardcoded secrets or API keys
- [ ] Input validation at system boundaries
- [ ] SQL queries use parameterized statements
- [ ] No command injection via user input

## Error Handling
- [ ] Errors are caught at appropriate levels
- [ ] Error messages don't leak internal details
- [ ] Resources are cleaned up (files, connections)

## Testing
- [ ] New code has corresponding tests
- [ ] Edge cases are covered
- [ ] Tests are deterministic (no flaky timing)
