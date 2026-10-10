/**
 * Re-export of the time formatters used by the steps UI.
 *
 * The implementation lives in `./steps` so the pure helpers sit together and can
 * be imported by tests without pulling in Vite-only modules.
 */
export { formatDuration, formatElapsed } from './steps';
