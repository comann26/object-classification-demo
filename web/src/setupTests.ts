import '@testing-library/jest-dom/vitest'
import { afterEach } from 'vitest'
import { cleanup } from '@testing-library/react'

// vitest.config.ts doesn't set `test.globals`, so @testing-library/react's
// own auto-cleanup (which detects a global `afterEach`) never registers.
// Do it here once for every test file instead of per-file.
afterEach(cleanup)
