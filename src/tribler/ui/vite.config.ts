import path from "path"
import react from "@vitejs/plugin-react"
import tailwindcss from '@tailwindcss/vite'
import { defineConfig } from "vite"

const basenameProd = ''

export default defineConfig(({ command }) => {
  const isProd = command === 'build'

  return {
    base: isProd ? basenameProd : '',
    plugins: [react(), tailwindcss()],
    resolve: {
      alias: {
        "@": path.resolve(__dirname, "./src"),
      },
    },
  }
})