import type { Preview } from "@storybook/react-vite";

import "@fontsource-variable/manrope";
import "maplibre-gl/dist/maplibre-gl.css";
import "../src/styles.css";

const preview: Preview = {
  parameters: {
    a11y: { test: "error" },
    backgrounds: { default: "sand" },
    controls: { expanded: true },
  },
};

export default preview;
