/**
 * Simulation History.
 *
 * The implementation moved into the shared `StudyListPage` when My Studies,
 * Patient Assessments and Research Designs were added: they are four filtered
 * views of the same stored records, so they are one component rather than four
 * near-identical pages that would drift apart.
 *
 * This module remains so existing imports and tests keep resolving.
 */

export { default } from './StudyLists';
