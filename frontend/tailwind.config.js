export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        paper: "#F1F3EE", ink: "#17302B", moss: "#2F5A4F", brass: "#B08330",
        line: "#D5DBD2", danger: "#A63D2F",
      },
      fontFamily: {
        display: ["Fraunces", "Georgia", "serif"],
        sans: ["Hanken Grotesk", "system-ui", "sans-serif"],
      },
    },
  },
};
