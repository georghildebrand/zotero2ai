# Implementation Checklist

Use this checklist to track progress on each improvement.

## Phase 1: Critical Fixes (Week 1)

### Issue #2: Fix Pagination & Limits
- [ ] **handlers.js**: Update `handleGetCollections()`
  - [ ] Add `limit`, `start`, `sort` parameters
  - [ ] Implement sorting logic
  - [ ] Apply pagination to results
  - [ ] Add pagination metadata to response
- [ ] **server.py**: Update `list_collections()` tool
  - [ ] Add pagination parameters
  - [ ] Add logging for truncation warnings
- [ ] **Testing**
  - [ ] Test with collection containing 100+ items
  - [ ] Test pagination with different limits
  - [ ] Verify all items are accessible
- [ ] **Documentation**
  - [ ] Update API docs with pagination params
  - [ ] Add examples

**Estimated Time**: 4-6 hours

### Issue #5: Standardize Error Handling
- [ ] **handlers.js**: Add error-safe wrappers
  - [ ] Implement `_safeGetTags()`
  - [ ] Implement `_safeGetField()`
  - [ ] Implement `_safeGetCreators()`
  - [ ] Implement `_safeGetAttachments()`
- [ ] **handlers.js**: Update `formatItems()`
  - [ ] Use safe wrappers
  - [ ] Add error collection
  - [ ] Add warnings to response
- [ ] **handlers.js**: Update `handleGetTags()`
  - [ ] Add try-catch per library
  - [ ] Return empty array on failure
  - [ ] Add warnings for failed libraries
- [ ] **Testing**
  - [ ] Test with malformed items
  - [ ] Test with missing tags
  - [ ] Verify partial data returned
- [ ] **Documentation**
  - [ ] Document warning format
  - [ ] Add troubleshooting guide

**Estimated Time**: 6-8 hours

---

## Phase 2: Navigation Improvements (Week 2)

### Issue #1: Add `list_collection_children` Tool
- [ ] **handlers.js**: Implement handler
  - [ ] Add `handleGetCollectionChildren()`
  - [ ] Find collection by key
  - [ ] Get immediate children only
  - [ ] Format collections and items
  - [ ] Add route in `handle()` method
- [ ] **server.py**: Add MCP tool
  - [ ] Implement `list_collection_children()`
  - [ ] Add docstring with examples
  - [ ] Add error handling
- [ ] **Testing**
  - [ ] Test with nested collections
  - [ ] Test with empty collections
  - [ ] Measure token usage reduction
- [ ] **Documentation**
  - [ ] Add API endpoint docs
  - [ ] Add MCP tool docs
  - [ ] Add usage examples

**Estimated Time**: 4-6 hours

### Issue #3: Improve Search Scoring
- [ ] **utils.js**: Add fuzzy matching
  - [ ] Implement `fuzzyMatchScore()`
  - [ ] Add exact match detection
  - [ ] Add token-based matching
  - [ ] Add path inclusion scoring
- [ ] **handlers.js**: Update search handler
  - [ ] Update `handleSearchCollections()`
  - [ ] Apply scoring to results
  - [ ] Add `matchScore` to results
  - [ ] Add `minScore` parameter
  - [ ] Sort by score
- [ ] **Testing**
  - [ ] Test with various query patterns
  - [ ] Test "2023-11 Blog Posts" query
  - [ ] Verify score accuracy
  - [ ] Test path matching
- [ ] **Documentation**
  - [ ] Document scoring algorithm
  - [ ] Add search best practices

**Estimated Time**: 6-8 hours

---

## Phase 3: Performance Optimization (Week 3)

### Issue #4: Implement Collection Hierarchy Caching
- [ ] **cache.js**: Create cache module (NEW FILE)
  - [ ] Implement `MCPCache` class
  - [ ] Add `refresh()` method
  - [ ] Add `get()` method
  - [ ] Add `isValid()` method
  - [ ] Add `invalidate()` method
  - [ ] Add `search()` method
  - [ ] Add `findByKey()` method
  - [ ] Add `getChildren()` method
- [ ] **handlers.js**: Integrate cache
  - [ ] Add cache initialization in constructor
  - [ ] Add `handleRefreshCache()`
  - [ ] Update `handleGetCollections()` to use cache
  - [ ] Update `handleSearchCollections()` to use cache
  - [ ] Add fallback to direct API
  - [ ] Add route for cache refresh
- [ ] **server.py**: Add cache tool
  - [ ] Implement `refresh_cache()` tool
  - [ ] Add auto-refresh logic
- [ ] **Testing**
  - [ ] Test cache refresh
  - [ ] Test cache expiration
  - [ ] Measure response time improvement
  - [ ] Test cache invalidation
  - [ ] Test fallback behavior
- [ ] **Documentation**
  - [ ] Document caching behavior
  - [ ] Add cache management guide

**Estimated Time**: 8-10 hours

---

## Final Steps

### Integration Testing
- [ ] Test all improvements together
- [ ] Run end-to-end agent workflow
- [ ] Measure overall performance improvement
- [ ] Test with real Zotero library (1000+ items)
- [ ] Verify no regressions

### Documentation
- [ ] Update main README
- [ ] Update CHANGELOG
- [ ] Create migration guide
- [ ] Add troubleshooting section
- [ ] Update API reference

### Deployment
- [ ] Create release branch
- [ ] Update version number
- [ ] Build plugin XPI
- [ ] Test installation
- [ ] Create GitHub release
- [ ] Update MCP server package

---

## Time Estimates

| Phase | Estimated Time | Buffer | Total |
|-------|---------------|--------|-------|
| Phase 1 | 10-14 hours | 4 hours | 18 hours |
| Phase 2 | 10-14 hours | 4 hours | 18 hours |
| Phase 3 | 8-10 hours | 4 hours | 14 hours |
| Final | 6-8 hours | 2 hours | 10 hours |
| **Total** | **34-46 hours** | **14 hours** | **60 hours** |

**Recommended Schedule**: 3 weeks at 20 hours/week

---

## Success Criteria Checklist

After implementation, verify these metrics:

- [ ] **Token Usage**: 70% reduction for navigation tasks
- [ ] **Connection Resets**: 0 in 100 consecutive operations
- [ ] **Collection Completeness**: 100% of collections visible
- [ ] **Search Accuracy**: 95%+ success rate for fuzzy searches
- [ ] **Cached Response Time**: <100ms
- [ ] **Error Rate**: <1% for common operations
- [ ] **Backward Compatibility**: All existing tools work unchanged

---

## Rollback Plan

If issues arise:

1. **Phase 3 Rollback**
   - [ ] Disable caching via feature flag
   - [ ] Revert to direct API calls

2. **Phase 2 Rollback**
   - [ ] Remove new `list_collection_children` endpoint
   - [ ] Revert search scoring to simple contains match

3. **Phase 1 Rollback**
   - [ ] Revert pagination changes
   - [ ] Revert error handling to original

Each phase is independent and can be rolled back without affecting others.

---

## Notes

- Keep old code commented as `// LEGACY:` for reference
- Add feature flags for gradual rollout
- Monitor error logs during deployment
- Collect user feedback after each phase
- Update this checklist as you progress

**Last Updated**: 2026-01-10
