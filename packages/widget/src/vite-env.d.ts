/// <reference types="vite/client" />

// Vite ?inline CSS imports — returns the stylesheet as a string
declare module "*.css?inline" {
  const content: string;
  export default content;
  export const widgetCss: string;
}
