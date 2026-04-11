// Test setup — extend vitest matchers with @testing-library/jest-dom
import "@testing-library/jest-dom";

// jsdom doesn't implement scrollIntoView — mock it globally
Element.prototype.scrollIntoView = () => {};
